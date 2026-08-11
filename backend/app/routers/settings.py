import shutil
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AppSetting, PublishingAccount
from app.schemas import ConnectionToggle, SettingUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def masked(value: str | None) -> str | None:
    if not value: return None
    return f"••••{value[-4:]}" if len(value) > 4 else "••••"


def connection_states(db: Session):
    accounts = {a.platform: a for a in db.scalars(select(PublishingAccount)).all()}
    return [
        {"id": "youtube_discovery", "name": "YouTube Discovery", "configured": bool(settings.youtube_api_key), "enabled": accounts.get("youtube_discovery").enabled if accounts.get("youtube_discovery") else bool(settings.youtube_api_key), "credential": masked(settings.youtube_api_key), "testable": True},
        {"id": "youtube_publishing", "name": "YouTube Publishing", "configured": bool(settings.youtube_publishing_client_id), "enabled": bool(accounts.get("youtube") and accounts["youtube"].enabled), "credential": masked(settings.youtube_publishing_client_id), "testable": False},
        {"id": "tiktok", "name": "TikTok", "configured": bool(settings.tiktok_client_key), "enabled": bool(accounts.get("tiktok") and accounts["tiktok"].enabled), "credential": masked(settings.tiktok_client_key), "testable": False},
        {"id": "instagram", "name": "Instagram", "configured": bool(settings.instagram_app_id), "enabled": bool(accounts.get("instagram") and accounts["instagram"].enabled), "credential": masked(settings.instagram_app_id), "testable": False},
        {"id": "ai", "name": f"AI provider · {settings.analysis_provider}", "configured": settings.analysis_provider == "mock" or bool(settings.openai_api_key), "enabled": True, "credential": "Local fallback" if settings.analysis_provider == "mock" else masked(settings.openai_api_key), "testable": False},
    ]


@router.patch("/connections/{connection_id}")
def toggle_connection(connection_id: str, payload: ConnectionToggle, db: Session = Depends(get_db)):
    allowed = {"youtube_discovery", "youtube_publishing", "tiktok", "instagram", "ai"}
    if connection_id not in allowed: raise HTTPException(404, "Connection not found")
    account = db.scalar(select(PublishingAccount).where(PublishingAccount.platform == connection_id))
    if not account:
        account = PublishingAccount(platform=connection_id, account_name=connection_id.replace("_", " ").title(), configured=False, enabled=payload.enabled)
        db.add(account)
    else: account.enabled = payload.enabled
    db.commit(); db.refresh(account)
    return {"id": connection_id, "enabled": account.enabled}


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    records = db.scalars(select(AppSetting).order_by(AppSetting.section, AppSetting.key)).all()
    grouped: dict[str, list] = {}
    for record in records:
        value = "••••••••" if record.is_secret and record.value else record.value
        grouped.setdefault(record.section, []).append({"key": record.key, "value": value, "description": record.description})
    checklist = [
        {"label": "YouTube Discovery API", "ok": bool(settings.youtube_api_key), "optional": True},
        {"label": "AI provider", "ok": settings.analysis_provider == "mock" or bool(settings.openai_api_key), "optional": True},
        {"label": "Media storage", "ok": settings.media_root.exists() or settings.media_root.parent.exists(), "optional": False},
        {"label": "FFmpeg", "ok": bool(shutil.which(settings.ffmpeg_binary)), "optional": False},
    ]
    return {"sections": grouped, "connections": connection_states(db), "checklist": checklist, "runtime": {"environment": settings.app_env, "demo_mode": settings.demo_mode, "media_root": str(settings.media_root), "upload_max_mb": settings.upload_max_mb, "output": f"{settings.output_width}×{settings.output_height}", "transcription_provider": settings.transcription_provider, "analysis_provider": settings.analysis_provider}}


@router.put("")
def set_setting(payload: SettingUpdate, db: Session = Depends(get_db)):
    record = db.scalar(select(AppSetting).where(AppSetting.key == payload.key))
    if record:
        record.value, record.section, record.description = payload.value, payload.section, payload.description
    else:
        record = AppSetting(**payload.model_dump()); db.add(record)
    db.commit(); db.refresh(record); return record


@router.post("/connections/{connection_id}/test")
def test_connection(connection_id: str, db: Session = Depends(get_db)):
    if connection_id != "youtube_discovery": raise HTTPException(501, "Connection test becomes available after the official OAuth adapter is installed")
    if not settings.youtube_api_key: raise HTTPException(409, "YouTube Discovery is not configured")
    try:
        response = httpx.get("https://www.googleapis.com/youtube/v3/videos", params={"key": settings.youtube_api_key, "part": "id", "chart": "mostPopular", "maxResults": 1}, timeout=10)
        response.raise_for_status()
    except Exception as exc: raise HTTPException(502, f"Connection failed: {exc}") from exc
    return {"ok": True, "tested_at": datetime.now(timezone.utc), "message": "YouTube Data API responded successfully"}
