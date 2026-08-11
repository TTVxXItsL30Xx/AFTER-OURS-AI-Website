import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.routers import analytics, creators, discovery, health, jobs, overview, publishing, sources, studio
from app.routers import settings as settings_router

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="AFTER OURS API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["*"])

for router in [overview.router, discovery.router, creators.router, sources.router, studio.router, publishing.queue_router, publishing.published_router, analytics.router, settings_router.router, jobs.router]:
    app.include_router(router, prefix="/api/v1")
app.include_router(health.router)


@app.get("/api/v1/media/{kind}/{filename}")
def media(kind: str, filename: str):
    if kind not in {"uploads", "outputs"}: raise HTTPException(404, "Media not found")
    root = (settings.media_root / kind).resolve(); path = (root / Path(filename).name).resolve()
    if not path.is_relative_to(root) or not path.is_file(): raise HTTPException(404, "Media not found")
    return FileResponse(path, media_type="video/mp4" if path.suffix.lower() == ".mp4" else None, filename=path.name)


@app.get("/")
def root(): return {"name": settings.app_name, "version": "1.0.0", "docs": "/api/docs"}

