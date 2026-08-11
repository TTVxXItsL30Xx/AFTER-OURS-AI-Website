import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Creator, DiscoveredVideo
from app.schemas import CreatorUpdate

router = APIRouter(prefix="/creators", tags=["creators"])


@router.get("")
def list_creators(enabled: bool | None = None, q: str | None = None, db: Session = Depends(get_db)):
    query = select(Creator)
    if enabled is not None: query = query.where(Creator.enabled == enabled)
    if q: query = query.where(Creator.name.ilike(f"%{q}%"))
    creators = db.scalars(query.order_by(Creator.created_at.desc())).all()
    return [{**{column.name: getattr(creator, column.name) for column in Creator.__table__.columns}, "discovery_count": db.scalar(select(func.count()).select_from(DiscoveredVideo).where(DiscoveredVideo.creator_id == creator.id)) or 0} for creator in creators]


@router.get("/{creator_id}")
def creator_detail(creator_id: uuid.UUID, db: Session = Depends(get_db)):
    creator = db.get(Creator, creator_id)
    if not creator: raise HTTPException(404, "Creator not found")
    videos = db.scalars(select(DiscoveredVideo).where(DiscoveredVideo.creator_id == creator.id).order_by(DiscoveredVideo.published_at.desc()).limit(20)).all()
    return {"creator": creator, "recent_discoveries": videos}


@router.patch("/{creator_id}")
def update_creator(creator_id: uuid.UUID, payload: CreatorUpdate, db: Session = Depends(get_db)):
    creator = db.get(Creator, creator_id)
    if not creator: raise HTTPException(404, "Creator not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(creator, key, value)
    db.commit(); db.refresh(creator); return creator


@router.delete("/{creator_id}", status_code=204)
def remove_creator(creator_id: uuid.UUID, db: Session = Depends(get_db)):
    creator = db.get(Creator, creator_id)
    if not creator: raise HTTPException(404, "Creator not found")
    db.delete(creator); db.commit()

