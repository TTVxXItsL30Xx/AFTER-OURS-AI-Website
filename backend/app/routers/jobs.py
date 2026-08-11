from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProcessingJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(status: str | None = None, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    query = select(ProcessingJob)
    if status: query = query.where(ProcessingJob.status == status)
    return db.scalars(query.order_by(ProcessingJob.created_at.desc()).limit(limit)).all()

