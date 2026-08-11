from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Creator, DiscoveredVideo, ProcessingJob, Publication, PublishingJob, RenderedClip, Source

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("")
def overview(db: Session = Depends(get_db)):
    def count(model, *criteria):
        return db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0

    stats = {
        "discoveries": count(DiscoveredVideo),
        "candidates": count(DiscoveredVideo, DiscoveredVideo.status == "candidate", DiscoveredVideo.ignored.is_(False)),
        "clips_ready": count(RenderedClip, RenderedClip.status == "ready"),
        "queued_posts": count(PublishingJob, PublishingJob.status.in_(["awaiting_approval", "approved", "scheduled", "processing", "publishing"])),
        "published_posts": count(Publication, Publication.status == "published"),
        "creators": count(Creator),
        "sources": count(Source),
        "processing_jobs": count(ProcessingJob, ProcessingJob.status.in_(["queued", "processing"])),
    }
    discoveries = db.scalars(select(DiscoveredVideo).where(DiscoveredVideo.ignored.is_(False)).order_by(DiscoveredVideo.created_at.desc()).limit(5)).all()
    clips = db.scalars(select(RenderedClip).order_by(RenderedClip.created_at.desc()).limit(4)).all()
    publishing = db.scalars(select(PublishingJob).order_by(PublishingJob.updated_at.desc()).limit(5)).all()
    jobs = db.scalars(select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(8)).all()
    return {"stats": stats, "recent_discoveries": discoveries, "recent_clips": clips, "publishing_status": publishing, "activity": jobs}
