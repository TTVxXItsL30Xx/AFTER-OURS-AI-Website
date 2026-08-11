import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.jobs import enqueue
from app.models import ClipProject, Moment, RenderedClip, Source, Transcript
from app.schemas import ClipProjectCreate, ClipProjectUpdate

router = APIRouter(prefix="/studio", tags=["studio"])


@router.get("")
def studio_workspace(source_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    sources = db.scalars(select(Source).where(Source.permission_status == "authorised").order_by(Source.created_at.desc())).all()
    projects = db.scalars(select(ClipProject).order_by(ClipProject.updated_at.desc()).limit(30)).all()
    active_id = source_id or (sources[0].id if sources else None)
    transcript = db.scalar(select(Transcript).where(Transcript.source_id == active_id).order_by(Transcript.created_at.desc())) if active_id else None
    moments = db.scalars(select(Moment).where(Moment.transcript_id == transcript.id).order_by(Moment.score.desc())).all() if transcript else []
    renders = db.scalars(select(RenderedClip).order_by(RenderedClip.created_at.desc()).limit(20)).all()
    return {"sources": sources, "active_source_id": active_id, "transcript": transcript, "moments": moments, "projects": projects, "renders": renders}


@router.post("/sources/{source_id}/transcribe", status_code=202)
def transcribe(source_id: uuid.UUID, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source: raise HTTPException(404, "Source not found")
    if source.permission_status != "authorised": raise HTTPException(403, "Source is not authorised for processing")
    return enqueue(db, "afterours.transcribe_source", "transcription", "source", source.id)


@router.post("/transcripts/{transcript_id}/analyse", status_code=202)
def analyse(transcript_id: uuid.UUID, db: Session = Depends(get_db)):
    transcript = db.get(Transcript, transcript_id)
    if not transcript or transcript.status != "completed": raise HTTPException(409, "A completed transcript is required")
    return enqueue(db, "afterours.analyse_transcript", "ai_analysis", "transcript", transcript.id)


@router.post("/projects", status_code=201)
def create_project(payload: ClipProjectCreate, db: Session = Depends(get_db)):
    source = db.get(Source, payload.source_id)
    if not source or source.permission_status != "authorised": raise HTTPException(403, "An authorised source is required")
    if source.duration_seconds and payload.end_seconds > source.duration_seconds + 0.5: raise HTTPException(400, "Clip range exceeds source duration")
    project = ClipProject(**payload.model_dump()); db.add(project); db.commit(); db.refresh(project); return project


@router.patch("/projects/{project_id}")
def update_project(project_id: uuid.UUID, payload: ClipProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(ClipProject, project_id)
    if not project: raise HTTPException(404, "Clip project not found")
    values = payload.model_dump(exclude_unset=True)
    start, end = values.get("start_seconds", project.start_seconds), values.get("end_seconds", project.end_seconds)
    if end <= start or end - start > 180: raise HTTPException(400, "Invalid clip range")
    for key, value in values.items(): setattr(project, key, value)
    db.commit(); db.refresh(project); return project


@router.post("/projects/{project_id}/render", status_code=202)
def render(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.get(ClipProject, project_id)
    if not project: raise HTTPException(404, "Clip project not found")
    project.status = "queued"; db.commit()
    return enqueue(db, "afterours.render_clip", "rendering", "clip_project", project.id)

