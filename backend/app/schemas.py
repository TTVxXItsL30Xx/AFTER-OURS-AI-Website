import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DiscoverySearch(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    search_type: Literal["topic", "keyword", "creator"] = "topic"
    max_results: int = Field(default=12, ge=1, le=50)
    published_after: datetime | None = None


class DiscoveryRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    query: str = Field(min_length=2, max_length=500)
    rule_type: Literal["topic", "keyword", "creator"] = "topic"
    provider: str = "youtube"
    schedule: str = "0 */6 * * *"
    filters: dict[str, Any] = Field(default_factory=dict)


class CreatorUpdate(BaseModel):
    monitored: bool | None = None
    enabled: bool | None = None
    discovery_frequency: str | None = Field(default=None, max_length=32)
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    source_permission: Literal["unknown", "authorised", "restricted", "revoked"] | None = None


class ClipProjectCreate(BaseModel):
    source_id: uuid.UUID
    moment_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=300)
    hook_text: str | None = Field(default=None, max_length=500)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    caption_style: Literal["bold", "minimal", "clean", "none"] = "bold"
    subtitles_enabled: bool = True
    crop_settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_range(self) -> "ClipProjectCreate":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        if self.end_seconds - self.start_seconds > 180:
            raise ValueError("V1 clips are limited to 180 seconds")
        return self


class ClipProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    hook_text: str | None = Field(default=None, max_length=500)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, gt=0)
    aspect_ratio: Literal["9:16", "1:1", "16:9"] | None = None
    caption_style: Literal["bold", "minimal", "clean", "none"] | None = None
    subtitles_enabled: bool | None = None
    crop_settings: dict[str, Any] | None = None


class PublishingJobCreate(BaseModel):
    rendered_clip_id: uuid.UUID
    account_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=300)
    caption: str | None = Field(default=None, max_length=5000)
    target_platforms: list[Literal["youtube", "tiktok", "instagram"]] = Field(min_length=1)
    scheduled_at: datetime | None = None
    status: Literal["draft", "awaiting_approval", "approved", "scheduled"] = "draft"


class PublishingJobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    caption: str | None = Field(default=None, max_length=5000)
    scheduled_at: datetime | None = None
    status: Literal["draft", "awaiting_approval", "approved", "scheduled", "cancelled"] | None = None


class SettingUpdate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_.-]+$", max_length=180)
    value: Any
    section: Literal["general", "discovery", "ai", "video", "publishing", "storage", "workers"]
    description: str | None = Field(default=None, max_length=1000)


class ConnectionToggle(BaseModel):
    enabled: bool


class ApiMessage(BaseModel):
    message: str
