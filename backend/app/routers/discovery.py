import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSetting, Creator, DiscoveredVideo, DiscoveryRule, PublishingAccount
from app.schemas import DiscoveryRuleCreate, DiscoverySearch
from app.services.providers import YouTubeDiscoveryProvider
from app.services.scoring import calculate_opportunity_score

router = APIRouter(prefix="/discovery", tags=["discovery"])


def blacklist(db: Session) -> tuple[list[str], list[str]]:
    settings = db.scalars(select(AppSetting).where(AppSetting.key.in_(["discovery.blacklist_keywords", "discovery.blacklist_creators"]))).all()
    values = {item.key: item.value or [] for item in settings}
    return [str(v).lower() for v in values.get("discovery.blacklist_keywords", [])], [str(v).lower() for v in values.get("discovery.blacklist_creators", [])]


@router.get("")
def list_discoveries(
    q: str | None = None, status_filter: str | None = Query(None, alias="status"), saved: bool | None = None,
    platform: str | None = None, sort: str = "score", limit: int = Query(40, ge=1, le=100), db: Session = Depends(get_db),
):
    query = select(DiscoveredVideo).where(DiscoveredVideo.ignored.is_(False))
    if q: query = query.where(or_(DiscoveredVideo.title.ilike(f"%{q}%"), DiscoveredVideo.creator_name.ilike(f"%{q}%")))
    if status_filter: query = query.where(DiscoveredVideo.status == status_filter)
    if saved is not None: query = query.where(DiscoveredVideo.saved == saved)
    if platform: query = query.where(DiscoveredVideo.platform == platform)
    order = DiscoveredVideo.opportunity_score.desc() if sort == "score" else DiscoveredVideo.published_at.desc()
    return db.scalars(query.order_by(order).limit(limit)).all()


@router.post("/search", status_code=status.HTTP_201_CREATED)
def discover(payload: DiscoverySearch, db: Session = Depends(get_db)):
    connection = db.scalar(select(PublishingAccount).where(PublishingAccount.platform == "youtube_discovery"))
    if connection and not connection.enabled:
        raise HTTPException(status_code=409, detail="YouTube Discovery is disabled in Settings.")
    try:
        provider = YouTubeDiscoveryProvider()
        results = provider.search(payload.query, payload.max_results, payload.published_after)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"YouTube Discovery request failed: {exc}") from exc
    blocked_keywords, blocked_creators = blacklist(db)
    created, duplicates, blocked = [], 0, 0
    for result in results:
        if any(term in result.title.lower() for term in blocked_keywords) or any(term in result.creator_name.lower() for term in blocked_creators):
            blocked += 1; continue
        existing = db.scalar(select(DiscoveredVideo).where(DiscoveredVideo.platform == provider.name, DiscoveredVideo.external_id == result.external_id))
        score, breakdown = calculate_opportunity_score(published_at=result.published_at, views=result.views, likes=result.likes, comments=result.comments)
        age_hours = max(1, (datetime.now(timezone.utc) - result.published_at).total_seconds() / 3600) if result.published_at else None
        engagement = ((result.likes or 0) + (result.comments or 0)) / max(result.views or 0, 1)
        if existing:
            duplicates += 1
            existing.views, existing.likes, existing.comments = result.views, result.likes, result.comments
            existing.views_per_hour, existing.engagement_rate, existing.opportunity_score, existing.score_breakdown = (result.views or 0) / age_hours if age_hours else None, engagement, score, breakdown
            continue
        video = DiscoveredVideo(platform=provider.name, external_id=result.external_id, creator_external_id=result.creator_external_id, creator_name=result.creator_name, title=result.title, description=result.description, thumbnail_url=result.thumbnail_url, source_url=result.source_url, published_at=result.published_at, duration_seconds=result.duration_seconds, views=result.views, likes=result.likes, comments=result.comments, views_per_hour=(result.views or 0) / age_hours if age_hours else None, engagement_rate=engagement, opportunity_score=score, score_breakdown=breakdown)
        db.add(video); created.append(video)
    db.commit()
    return {"created": len(created), "duplicates": duplicates, "blocked": blocked, "results": created}


@router.patch("/{video_id}/{action}")
def update_discovery(video_id: uuid.UUID, action: str, db: Session = Depends(get_db)):
    video = db.get(DiscoveredVideo, video_id)
    if not video: raise HTTPException(404, "Discovery not found")
    if action == "save": video.saved, video.status = True, "saved"
    elif action == "ignore": video.ignored, video.status = True, "ignored"
    else: raise HTTPException(400, "Action must be save or ignore")
    db.commit(); db.refresh(video); return video


@router.post("/{video_id}/follow")
def follow_creator(video_id: uuid.UUID, db: Session = Depends(get_db)):
    video = db.get(DiscoveredVideo, video_id)
    if not video: raise HTTPException(404, "Discovery not found")
    creator = db.scalar(select(Creator).where(Creator.platform == video.platform, Creator.external_id == (video.creator_external_id or video.creator_name)))
    if not creator:
        creator = Creator(platform=video.platform, external_id=video.creator_external_id or video.creator_name, name=video.creator_name, monitored=True, enabled=True)
        db.add(creator); db.flush()
    creator.monitored, video.creator_id = True, creator.id
    db.commit(); db.refresh(creator); return creator


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)): return db.scalars(select(DiscoveryRule).order_by(DiscoveryRule.created_at.desc())).all()


@router.post("/rules", status_code=201)
def create_rule(payload: DiscoveryRuleCreate, db: Session = Depends(get_db)):
    rule = DiscoveryRule(**payload.model_dump()); db.add(rule); db.commit(); db.refresh(rule); return rule


@router.patch("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)):
    rule = db.get(DiscoveryRule, rule_id)
    if not rule: raise HTTPException(404, "Rule not found")
    rule.enabled = not rule.enabled; db.commit(); db.refresh(rule); return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)):
    rule = db.get(DiscoveryRule, rule_id)
    if not rule: raise HTTPException(404, "Rule not found")
    db.delete(rule); db.commit()
