import uuid

from sqlalchemy.orm import Session

from app.models import ProcessingJob
from app.worker import celery_app


def enqueue(db: Session, task_name: str, job_type: str, entity_type: str, entity_id: uuid.UUID) -> ProcessingJob:
    job = ProcessingJob(job_type=job_type, entity_type=entity_type, entity_id=entity_id, status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        result = celery_app.send_task(task_name, args=[str(entity_id), str(job.id)])
        job.celery_task_id = result.id
        db.commit()
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Queue unavailable: {exc}"
        db.commit()
        raise
    return job

