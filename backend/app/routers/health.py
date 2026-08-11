import shutil

from fastapi import APIRouter
from redis import Redis
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.worker import celery_app

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live(): return {"status": "ok", "service": "api"}


@router.get("/api/v1/health")
def health():
    checks = {"api": {"status": "healthy"}}
    try:
        with engine.connect() as connection: connection.execute(text("SELECT 1"))
        checks["postgresql"] = {"status": "healthy"}
    except Exception as exc: checks["postgresql"] = {"status": "unhealthy", "detail": str(exc)}
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=1).ping(); checks["redis"] = {"status": "healthy"}
    except Exception as exc: checks["redis"] = {"status": "unhealthy", "detail": str(exc)}
    checks["ffmpeg"] = {"status": "healthy" if shutil.which(settings.ffmpeg_binary) else "unhealthy", "path": shutil.which(settings.ffmpeg_binary)}
    try:
        replies = celery_app.control.ping(timeout=0.5); checks["worker"] = {"status": "healthy" if replies else "unhealthy", "workers": len(replies)}
    except Exception as exc: checks["worker"] = {"status": "unhealthy", "detail": str(exc)}
    overall = "healthy" if all(value["status"] == "healthy" for value in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}

