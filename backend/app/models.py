import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Creator(TimestampMixin, Base):
    __tablename__ = "creators"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_creator_platform_external"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    profile_url: Mapped[str | None] = mapped_column(Text)
    follower_count: Mapped[int | None] = mapped_column(BigInteger)
    baseline_views: Mapped[float | None] = mapped_column(Float)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    discovery_frequency: Mapped[str] = mapped_column(String(32), default="daily")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    source_permission: Mapped[str] = mapped_column(String(32), default="unknown")
    videos: Mapped[list["DiscoveredVideo"]] = relationship(back_populates="creator")


class DiscoveryRule(TimestampMixin, Base):
    __tablename__ = "discovery_rules"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(180))
    query: Mapped[str] = mapped_column(String(500), index=True)
    rule_type: Mapped[str] = mapped_column(String(32), default="topic")
    provider: Mapped[str] = mapped_column(String(32), default="youtube")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    schedule: Mapped[str] = mapped_column(String(64), default="0 */6 * * *")
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DiscoveredVideo(TimestampMixin, Base):
    __tablename__ = "discovered_videos"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_video_platform_external"),
        Index("ix_discovered_score_date", "opportunity_score", "published_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    creator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("creators.id", ondelete="SET NULL"), index=True)
    creator_external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    creator_name: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    views: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    views_per_hour: Mapped[float | None] = mapped_column(Float)
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="candidate", index=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    authorised_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    creator: Mapped[Creator | None] = relationship(back_populates="videos")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(40), default="local_upload", index=True)
    creator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("creators.id", ondelete="SET NULL"), index=True)
    media_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ingest_status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    permission_status: Mapped[str] = mapped_column(String(32), default="authorised", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Transcript(TimestampMixin, Base):
    __tablename__ = "transcripts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50), default="mock")
    language: Mapped[str] = mapped_column(String(16), default="en")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    text: Mapped[str | None] = mapped_column(Text)
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    source: Mapped[Source] = relationship(back_populates="transcripts")
    moments: Mapped[list["Moment"]] = relationship(back_populates="transcript", cascade="all, delete-orphan")


class Moment(TimestampMixin, Base):
    __tablename__ = "moments"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcripts.id", ondelete="CASCADE"), index=True)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float, index=True)
    title: Mapped[str] = mapped_column(String(300))
    hook: Mapped[str] = mapped_column(String(500))
    rationale: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[Transcript] = relationship(back_populates="moments")


class ClipProject(TimestampMixin, Base):
    __tablename__ = "clip_projects"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    moment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("moments.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    hook_text: Mapped[str | None] = mapped_column(String(500))
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16")
    caption_style: Mapped[str] = mapped_column(String(32), default="bold")
    subtitles_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    crop_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    rendered_clips: Mapped[list["RenderedClip"]] = relationship(back_populates="project")


class RenderedClip(TimestampMixin, Base):
    __tablename__ = "rendered_clips"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clip_projects.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str | None] = mapped_column(Text)
    subtitle_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    project: Mapped[ClipProject] = relationship(back_populates="rendered_clips")


class PublishingAccount(TimestampMixin, Base):
    __tablename__ = "publishing_accounts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    account_name: Mapped[str] = mapped_column(String(180))
    external_account_id: Mapped[str | None] = mapped_column(String(255))
    configured: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_reference: Mapped[str | None] = mapped_column(String(255))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connection_error: Mapped[str | None] = mapped_column(Text)


class PublishingJob(TimestampMixin, Base):
    __tablename__ = "publishing_jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rendered_clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rendered_clips.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publishing_accounts.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    caption: Mapped[str | None] = mapped_column(Text)
    target_platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class Publication(TimestampMixin, Base):
    __tablename__ = "publications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publishing_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publishing_jobs.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    account_name: Mapped[str | None] = mapped_column(String(180))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(String(300))
    caption: Mapped[str | None] = mapped_column(Text)
    external_post_id: Mapped[str | None] = mapped_column(String(255), index=True)
    external_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)


class AnalyticsSnapshot(TimestampMixin, Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (Index("ix_analytics_publication_captured", "publication_id", "captured_at"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    likes: Mapped[int] = mapped_column(BigInteger, default=0)
    comments: Mapped[int] = mapped_column(BigInteger, default=0)
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    watch_time_seconds: Mapped[float | None] = mapped_column(Float)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ProcessingJob(TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    value: Mapped[Any] = mapped_column(JSON)
    section: Mapped[str] = mapped_column(String(64), index=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
