import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Publication, PublishingAccount, PublishingJob, RenderedClip
from app.schemas import PublishingJobCreate, PublishingJobUpdate

queue_router = APIRouter(prefix="/queue", tags=["publishing queue"])
published_router = APIRouter(prefix="/published", tags=["publications"])


@queue_router.get("")
def list_queue(db: Session = Depends(get_db)):
    jobs = db.scalars(select(PublishingJob).order_by(PublishingJob.scheduled_at.asc().nulls_last(), PublishingJob.created_at.desc())).all()
    return jobs


@queue_router.post("", status_code=201)
def create_job(payload: PublishingJobCreate, db: Session = Depends(get_db)):
    clip = db.get(RenderedClip, payload.rendered_clip_id)
    if not clip or clip.status != "ready": raise HTTPException(409, "A completed rendered clip is required")
    job = PublishingJob(**payload.model_dump()); db.add(job); db.commit(); db.refresh(job); return job


@queue_router.patch("/{job_id}")
def update_job(job_id: uuid.UUID, payload: PublishingJobUpdate, db: Session = Depends(get_db)):
    job = db.get(PublishingJob, job_id)
    if not job: raise HTTPException(404, "Publishing job not found")
    if job.status in {"publishing", "published"}: raise HTTPException(409, "This job can no longer be edited")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(job, key, value)
    db.commit(); db.refresh(job); return job


@queue_router.post("/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(PublishingJob, job_id)
    if not job: raise HTTPException(404, "Publishing job not found")
    if job.status in {"publishing", "published"}: raise HTTPException(409, "Active or completed publication cannot be cancelled")
    job.status = "cancelled"; db.commit(); db.refresh(job); return job


@queue_router.post("/{job_id}/publish-now")
def publish_now(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(PublishingJob, job_id)
    if not job: raise HTTPException(404, "Publishing job not found")
    account = db.get(PublishingAccount, job.account_id) if job.account_id else None
    if not account or not account.configured or not account.enabled:
        raise HTTPException(409, "Publishing account is not configured. Connect an official platform API in Settings.")
    raise HTTPException(501, "Official platform upload adapter is not installed yet; no upload was attempted.")


@published_router.get("")
def list_publications(db: Session = Depends(get_db)):
    return db.scalars(select(Publication).order_by(Publication.published_at.desc().nulls_last(), Publication.created_at.desc())).all()

