import hashlib
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.jobs import enqueue
from app.models import Source

router = APIRouter(prefix="/sources", tags=["sources"])
CHUNK_SIZE = 1024 * 1024


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    return db.scalars(select(Source).order_by(Source.created_at.desc())).all()


@router.get("/{source_id}")
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source: raise HTTPException(404, "Source not found")
    return source


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_source(file: UploadFile = File(...), title: str | None = Form(None), creator_id: uuid.UUID | None = Form(None), permission_confirmed: bool = Form(...), db: Session = Depends(get_db)):
    if not permission_confirmed: raise HTTPException(400, "You must confirm permission to process this media")
    original = Path(file.filename or "upload").name
    suffix = Path(original).suffix.lower()
    if suffix not in settings.allowed_extensions: raise HTTPException(415, f"Unsupported video type. Allowed: {', '.join(sorted(settings.allowed_extensions))}")
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(original).stem).strip("-.")[:120] or "media"
    upload_dir = settings.media_root / "uploads"; upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid.uuid4()}-{safe_stem}{suffix}"
    digest, size, max_bytes = hashlib.sha256(), 0, settings.upload_max_mb * 1024 * 1024
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes: raise HTTPException(413, f"Upload exceeds {settings.upload_max_mb} MB limit")
                digest.update(chunk); output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True); raise
    finally:
        await file.close()
    checksum = digest.hexdigest()
    duplicate = db.scalar(select(Source).where(Source.checksum == checksum))
    if duplicate:
        destination.unlink(missing_ok=True)
        raise HTTPException(409, detail={"message": "Duplicate source", "source_id": str(duplicate.id)})
    source = Source(title=(title or Path(original).stem)[:500], filename=original, source_type="local_upload", creator_id=creator_id, media_path=str(destination), mime_type=file.content_type, size_bytes=size, checksum=checksum, permission_status="authorised", ingest_status="uploaded", processing_status="queued")
    db.add(source); db.commit(); db.refresh(source)
    try:
        job = enqueue(db, "afterours.ingest_source", "source_ingest", "source", source.id)
        return {"source": source, "job": job}
    except Exception as exc:
        source.processing_status = "queue_failed"; source.error_message = str(exc); db.commit()
        return {"source": source, "job": None, "warning": "Source saved, but the worker queue is unavailable."}


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source: raise HTTPException(404, "Source not found")
    path = Path(source.media_path)
    try:
        if path.exists() and path.resolve().is_relative_to(settings.media_root.resolve()): path.unlink()
    except OSError as exc:
        raise HTTPException(500, f"Could not remove media file: {exc}") from exc
    db.delete(source); db.commit()

