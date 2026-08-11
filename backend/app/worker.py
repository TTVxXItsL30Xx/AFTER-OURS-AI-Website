import uuid
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import ClipProject, DiscoveredVideo, DiscoveryRule, Moment, ProcessingJob, PublishingAccount, PublishingJob, RenderedClip, Source, Transcript
from app.services.providers import TranscriptResult, YouTubeDiscoveryProvider, get_analysis_provider, get_transcription_provider
from app.services.scoring import calculate_opportunity_score
from app.services.video import probe_media, render_vertical_clip, write_srt

celery_app = Celery("after_ours", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_track_started=True, result_expires=86400, task_serializer="json", accept_content=["json"], result_serializer="json", timezone="UTC")
celery_app.conf.beat_schedule = {
    "run-enabled-discovery-rules": {"task": "afterours.dispatch_discovery_rules", "schedule": 600.0},
    "dispatch-due-publications": {"task": "afterours.dispatch_due_publications", "schedule": 60.0},
    "refresh-connected-analytics": {"task": "afterours.refresh_analytics", "schedule": 21600.0},
}


def update_job(db, job_id: str, **values) -> ProcessingJob:
    job = db.get(ProcessingJob, uuid.UUID(job_id))
    if not job: raise RuntimeError("Processing job not found")
    for key, value in values.items(): setattr(job, key, value)
    db.commit()
    return job


@celery_app.task(name="afterours.ingest_source")
def ingest_source(source_id: str, job_id: str):
    with SessionLocal() as db:
        try:
            update_job(db, job_id, status="processing", progress=10, started_at=datetime.now(timezone.utc), message="Inspecting media")
            source = db.get(Source, uuid.UUID(source_id))
            if not source: raise RuntimeError("Source not found")
            info = probe_media(Path(source.media_path))
            source.duration_seconds, source.size_bytes = info["duration"], info["size"]
            source.ingest_status, source.processing_status = "ready", "ready"
            update_job(db, job_id, status="completed", progress=100, completed_at=datetime.now(timezone.utc), message="Source ready")
            return info
        except Exception as exc:
            source = db.get(Source, uuid.UUID(source_id))
            if source: source.ingest_status, source.processing_status, source.error_message = "failed", "failed", str(exc)
            update_job(db, job_id, status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc))
            raise


@celery_app.task(name="afterours.transcribe_source")
def transcribe_source(source_id: str, job_id: str):
    with SessionLocal() as db:
        try:
            update_job(db, job_id, status="processing", progress=10, started_at=datetime.now(timezone.utc), message="Transcribing source")
            source = db.get(Source, uuid.UUID(source_id))
            if not source: raise RuntimeError("Source not found")
            transcript = Transcript(source_id=source.id, provider=settings.transcription_provider, status="processing")
            db.add(transcript); db.commit(); db.refresh(transcript)
            result = get_transcription_provider().transcribe(Path(source.media_path), source.duration_seconds)
            transcript.text, transcript.segments, transcript.language, transcript.status = result.text, result.segments, result.language, "completed"
            source.processing_status = "transcribed"
            update_job(db, job_id, status="completed", progress=100, completed_at=datetime.now(timezone.utc), message=f"Transcript ready via {transcript.provider}")
            return str(transcript.id)
        except Exception as exc:
            update_job(db, job_id, status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc)); raise


@celery_app.task(name="afterours.analyse_transcript")
def analyse_transcript(transcript_id: str, job_id: str):
    with SessionLocal() as db:
        try:
            update_job(db, job_id, status="processing", progress=15, started_at=datetime.now(timezone.utc), message="Finding candidate moments")
            transcript = db.get(Transcript, uuid.UUID(transcript_id))
            if not transcript: raise RuntimeError("Transcript not found")
            source = db.get(Source, transcript.source_id)
            result = TranscriptResult(text=transcript.text or "", segments=transcript.segments, language=transcript.language)
            suggestions = get_analysis_provider().suggest_moments(result, source.duration_seconds if source else None)
            db.query(Moment).filter(Moment.transcript_id == transcript.id).delete()
            for item in suggestions: db.add(Moment(transcript_id=transcript.id, **item))
            if source: source.processing_status = "analysed"
            update_job(db, job_id, status="completed", progress=100, completed_at=datetime.now(timezone.utc), message=f"{len(suggestions)} moments ready")
            return len(suggestions)
        except Exception as exc:
            update_job(db, job_id, status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc)); raise


@celery_app.task(name="afterours.render_clip")
def render_clip(project_id: str, job_id: str):
    with SessionLocal() as db:
        rendered = None
        try:
            update_job(db, job_id, status="processing", progress=5, started_at=datetime.now(timezone.utc), message="Preparing render")
            project = db.get(ClipProject, uuid.UUID(project_id))
            if not project: raise RuntimeError("Clip project not found")
            source = db.get(Source, project.source_id)
            if not source or source.permission_status != "authorised": raise RuntimeError("An authorised source is required")
            output_dir = settings.media_root / "outputs"; output_dir.mkdir(parents=True, exist_ok=True)
            output = output_dir / f"{project.id}.mp4"; subtitle = output_dir / f"{project.id}.srt"
            rendered = RenderedClip(project_id=project.id, file_path=str(output), subtitle_path=str(subtitle) if project.subtitles_enabled else None, status="processing")
            db.add(rendered); project.status = "rendering"; db.commit(); db.refresh(rendered)
            transcript = db.query(Transcript).filter(Transcript.source_id == source.id, Transcript.status == "completed").order_by(Transcript.created_at.desc()).first()
            if project.subtitles_enabled and transcript: write_srt(transcript.segments, project.start_seconds, project.end_seconds, subtitle)
            update_job(db, job_id, progress=25, message="FFmpeg is rendering")
            info = render_vertical_clip(source=Path(source.media_path), output=output, subtitle=subtitle if project.subtitles_enabled else None, start=project.start_seconds, end=project.end_seconds)
            rendered.status, rendered.duration_seconds, rendered.size_bytes, rendered.width, rendered.height = "ready", info["duration"], info["size"], info.get("width"), info.get("height")
            project.status = "ready"
            update_job(db, job_id, status="completed", progress=100, completed_at=datetime.now(timezone.utc), message="Render validated and ready")
            return str(rendered.id)
        except Exception as exc:
            if rendered: rendered.status, rendered.error_message = "failed", str(exc)
            project = db.get(ClipProject, uuid.UUID(project_id))
            if project: project.status = "failed"
            update_job(db, job_id, status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc)); raise


@celery_app.task(name="afterours.dispatch_discovery_rules")
def dispatch_discovery_rules():
    with SessionLocal() as db:
        rules = db.scalars(select(DiscoveryRule).where(DiscoveryRule.enabled.is_(True))).all()
        dispatched = 0
        for rule in rules:
            latest = db.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.entity_type == "discovery_rule", ProcessingJob.entity_id == rule.id)
                .order_by(ProcessingJob.created_at.desc())
                .limit(1)
            )
            interval_hours = 6
            schedule_parts = rule.schedule.split()
            if len(schedule_parts) == 5 and schedule_parts[1].startswith("*/"):
                try:
                    interval_hours = max(1, int(schedule_parts[1][2:]))
                except ValueError:
                    interval_hours = 6
            if latest and (datetime.now(timezone.utc) - latest.created_at).total_seconds() < interval_hours * 3600:
                continue
            job = ProcessingJob(job_type="discovery", entity_type="discovery_rule", entity_id=rule.id, status="queued")
            db.add(job); db.commit(); db.refresh(job)
            result = celery_app.send_task("afterours.run_discovery", args=[str(rule.id), str(job.id)])
            job.celery_task_id = result.id; db.commit()
            dispatched += 1
        return dispatched


@celery_app.task(name="afterours.run_discovery")
def run_discovery(rule_id: str, job_id: str):
    with SessionLocal() as db:
        try:
            update_job(db, job_id, status="processing", progress=10, started_at=datetime.now(timezone.utc), message="Querying discovery provider")
            rule = db.get(DiscoveryRule, uuid.UUID(rule_id))
            if not rule: raise RuntimeError("Discovery rule not found")
            provider = YouTubeDiscoveryProvider()
            results = provider.search(rule.query, int(rule.filters.get("max_results", 12)))
            created = 0
            for result in results:
                existing = db.scalar(select(DiscoveredVideo).where(DiscoveredVideo.platform == provider.name, DiscoveredVideo.external_id == result.external_id))
                score, breakdown = calculate_opportunity_score(published_at=result.published_at, views=result.views, likes=result.likes, comments=result.comments)
                age_hours = max(1, (datetime.now(timezone.utc) - result.published_at).total_seconds() / 3600) if result.published_at else None
                if existing:
                    existing.views, existing.likes, existing.comments, existing.opportunity_score, existing.score_breakdown = result.views, result.likes, result.comments, score, breakdown
                    continue
                db.add(DiscoveredVideo(platform=provider.name, external_id=result.external_id, creator_external_id=result.creator_external_id, creator_name=result.creator_name, title=result.title, description=result.description, thumbnail_url=result.thumbnail_url, source_url=result.source_url, published_at=result.published_at, duration_seconds=result.duration_seconds, views=result.views, likes=result.likes, comments=result.comments, views_per_hour=(result.views or 0) / age_hours if age_hours else None, engagement_rate=((result.likes or 0) + (result.comments or 0)) / max(result.views or 0, 1), opportunity_score=score, score_breakdown=breakdown))
                created += 1
            update_job(db, job_id, status="completed", progress=100, completed_at=datetime.now(timezone.utc), message=f"{created} new discoveries")
            return created
        except Exception as exc:
            update_job(db, job_id, status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc)); raise


@celery_app.task(name="afterours.dispatch_due_publications")
def dispatch_due_publications():
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        jobs = db.scalars(select(PublishingJob).where(PublishingJob.status == "scheduled", PublishingJob.scheduled_at <= now)).all()
        dispatched = 0
        for job in jobs:
            account = db.get(PublishingAccount, job.account_id) if job.account_id else None
            if not account or not account.configured or not account.enabled:
                job.status = "failed"; job.error_message = "Scheduled publishing account is not configured"
                continue
            process = ProcessingJob(job_type="publishing", entity_type="publishing_job", entity_id=job.id, status="failed", progress=0, error_message="Official upload adapter is not installed")
            db.add(process); job.status = "failed"; job.error_message = process.error_message; dispatched += 1
        db.commit(); return dispatched


@celery_app.task(name="afterours.refresh_analytics")
def refresh_analytics():
    with SessionLocal() as db:
        # Provider adapters will populate snapshots here. V1 intentionally stores no fabricated metrics.
        connected = db.scalar(select(PublishingAccount.id).where(PublishingAccount.configured.is_(True), PublishingAccount.enabled.is_(True)).limit(1))
        return {"status": "not_configured" if not connected else "adapter_required", "snapshots_created": 0}
