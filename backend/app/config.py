from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    app_name: str = "AFTER OURS API"
    app_env: str = "development"
    demo_mode: bool = False
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://after_ours:change-this-password@localhost:5432/after_ours"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] | str = ["http://localhost:3200"]
    media_root: Path = Path("./media")
    upload_max_mb: int = 2048
    allowed_video_extensions: str = ".mp4,.mov,.mkv,.webm,.m4v"
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    output_width: int = 1080
    output_height: int = 1920
    output_video_codec: str = "libx264"
    output_audio_codec: str = "aac"
    youtube_api_key: str | None = None
    openai_api_key: str | None = None
    transcription_provider: str = "mock"
    analysis_provider: str = "mock"
    youtube_publishing_client_id: str | None = None
    youtube_publishing_client_secret: str | None = None
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    instagram_app_id: str | None = None
    instagram_app_secret: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def allowed_extensions(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_video_extensions.split(",")}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

