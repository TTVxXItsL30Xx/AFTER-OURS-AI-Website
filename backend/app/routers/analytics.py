from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AnalyticsSnapshot, Publication

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
def analytics(date_from: datetime | None = None, date_to: datetime | None = None, db: Session = Depends(get_db)):
    publication_filter = []
    if date_from: publication_filter.append(Publication.published_at >= date_from)
    if date_to: publication_filter.append(Publication.published_at <= date_to)
    publications = db.scalars(select(Publication).where(*publication_filter).order_by(Publication.published_at.desc().nulls_last())).all()
    ids = [item.id for item in publications]
    snapshots = db.scalars(select(AnalyticsSnapshot).where(AnalyticsSnapshot.publication_id.in_(ids)).order_by(AnalyticsSnapshot.captured_at.desc())).all() if ids else []
    latest = {}
    for snap in snapshots: latest.setdefault(snap.publication_id, snap)
    total_views = sum(item.views for item in latest.values()); total_likes = sum(item.likes for item in latest.values()); total_comments = sum(item.comments for item in latest.values())
    by_platform = {}
    for publication in publications:
        group = by_platform.setdefault(publication.platform, {"platform": publication.platform, "published": 0, "views": 0, "likes": 0, "comments": 0})
        group["published"] += 1
        snap = latest.get(publication.id)
        if snap:
            group["views"] += snap.views; group["likes"] += snap.likes; group["comments"] += snap.comments
    best = sorted(({"publication": publication, "snapshot": latest.get(publication.id)} for publication in publications), key=lambda item: item["snapshot"].views if item["snapshot"] else 0, reverse=True)[:8]
    return {"summary": {"published": len(publications), "views": total_views, "likes": total_likes, "comments": total_comments, "engagement_rate": round((total_likes + total_comments) / max(total_views, 1) * 100, 2)}, "by_platform": list(by_platform.values()), "best_clips": best, "has_real_data": bool(snapshots)}

