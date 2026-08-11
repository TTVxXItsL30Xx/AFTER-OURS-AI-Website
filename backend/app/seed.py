"""Explicit development-only seed command: DEMO_MODE=true python -m app.seed"""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.models import AnalyticsSnapshot, ClipProject, Creator, DiscoveredVideo, ProcessingJob, Publication, PublishingJob, RenderedClip, Source
from app.services.scoring import calculate_opportunity_score


def run() -> None:
    if not settings.demo_mode:
        raise SystemExit("Refusing to seed: set DEMO_MODE=true explicitly. Production data was not changed.")
    with SessionLocal() as db:
        if db.query(Creator).count():
            raise SystemExit("Seed skipped: the database already contains creators.")
        now = datetime.now(timezone.utc)
        creators = [
            Creator(platform="youtube", external_id="demo-lex", name="Lexine Studio", follower_count=184000, monitored=True, tags=["design", "creative work"], notes="Development seed data."),
            Creator(platform="youtube", external_id="demo-night", name="Night Shift Notes", follower_count=92000, monitored=True, tags=["business", "process"], notes="Development seed data."),
        ]
        db.add_all(creators); db.flush()
        samples = [("Why the best work happens after the brief", creators[0], 5, 18400, 1380, 94), ("The quiet system behind consistent output", creators[1], 21, 42300, 2100, 183), ("Stop polishing the wrong thirty seconds", creators[0], 49, 8100, 744, 52)]
        for index, (title, creator, hours, views, likes, comments) in enumerate(samples):
            published = now - timedelta(hours=hours); score, breakdown = calculate_opportunity_score(published_at=published, views=views, likes=likes, comments=comments, creator_baseline=12000)
            db.add(DiscoveredVideo(platform="youtube", external_id=f"demo-video-{index}", creator_id=creator.id, creator_external_id=creator.external_id, creator_name=creator.name, title=title, source_url="https://www.youtube.com/", published_at=published, duration_seconds=720 + index * 180, views=views, likes=likes, comments=comments, views_per_hour=views / hours, engagement_rate=(likes + comments) / views, opportunity_score=score, score_breakdown=breakdown, saved=index < 2, status="saved" if index < 2 else "candidate"))
        source = Source(title="Demo authorised interview", filename="demo-authorised.mp4", source_type="demo", media_path=str(settings.media_root / "uploads" / "demo-authorised.mp4"), duration_seconds=420, size_bytes=0, checksum="demo-explicit-seed-checksum", ingest_status="demo", processing_status="demo", permission_status="authorised")
        db.add(source); db.flush()
        project = ClipProject(source_id=source.id, title="The after-hours advantage", hook_text="The hour nobody schedules is the hour that changes the work.", start_seconds=42, end_seconds=79, status="demo")
        db.add(project); db.flush()
        clip = RenderedClip(project_id=project.id, status="demo", duration_seconds=37, width=1080, height=1920)
        db.add(clip); db.flush()
        queue = PublishingJob(rendered_clip_id=clip.id, title=project.title, caption="Explicit development seed item.", target_platforms=["youtube", "tiktok"], scheduled_at=now + timedelta(days=1), status="draft")
        db.add(queue); db.flush()
        publication = Publication(publishing_job_id=queue.id, platform="youtube", account_name="Demo account", published_at=now - timedelta(days=2), title="A demo performance snapshot", status="published", external_post_id="demo-only")
        db.add(publication); db.flush()
        db.add(AnalyticsSnapshot(publication_id=publication.id, captured_at=now, views=12600, likes=940, comments=72, shares=31, raw_data={"demo": True}))
        db.add(ProcessingJob(job_type="rendering", entity_type="clip_project", entity_id=project.id, status="completed", progress=100, message="Explicit demo render record"))
        db.commit()
    print("Explicit demo data created. No external platform action was performed.")


if __name__ == "__main__": run()

