"""CareerPilot AI — FastAPI application entry point.

Run with: uvicorn main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agents.base import check_ollama_status
from api.routes import jobs, pipeline, remote, resume
from core.config import settings
from core.logging import get_logger
from core.model_pins import pins_snapshot, read_version
from database.session import init_db
from services.scheduler import get_scheduler_status, start_daily_scan, stop_daily_scan

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CareerPilot AI")
    settings.ensure_directories()
    init_db()

    if settings.daily_scan_enabled:
        start_daily_scan(
            hour=settings.daily_scan_hour,
            minute=settings.daily_scan_minute,
        )
    else:
        logger.info("Daily scan disabled (DAILY_SCAN_ENABLED=false)")

    yield

    stop_daily_scan()
    logger.info("Shutting down CareerPilot AI")


app = FastAPI(
    title="CareerPilot AI",
    description="Autonomous AI job discovery and resume tailoring assistant.",
    version=read_version(),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-first single-user app
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router)
app.include_router(jobs.router)
app.include_router(pipeline.router)
app.include_router(remote.router)

_REMOTE_UI = Path(__file__).resolve().parent / "remote_ui"
if settings.remote_ui_enabled and _REMOTE_UI.is_dir():
    app.mount("/m", StaticFiles(directory=str(_REMOTE_UI), html=True), name="remote_ui")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": read_version(),
        "scheduler": get_scheduler_status(),
    }


@app.get("/meta/pins")
def meta_pins() -> dict:
    """Phase 7 — pinned defaults + live runtime values (``.env`` may override)."""
    snap = pins_snapshot()
    snap["runtime"] = {
        "ollama_model": settings.ollama_model,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "reranker_enabled": settings.reranker_enabled,
        "min_match_score": settings.min_match_score,
    }
    return snap


@app.get("/meta/remote")
def meta_remote() -> dict:
    """Phase 11 — phone remote connectivity (no token value; safe for Setup UI)."""
    from services.remote_setup import get_remote_setup_status

    return get_remote_setup_status()


@app.get("/ollama/status")
def ollama_status() -> dict:
    ok, message = check_ollama_status()
    return {"ok": ok, "message": message, "model": settings.ollama_model}


@app.get("/scheduler/status")
def scheduler_status() -> dict:
    from agents.whatsapp_agent import whatsapp_configured
    from services.email_notifier import email_configured
    from services.google_drive import drive_credentials_status
    from services.notifier import get_latest_notification_preview
    from services.notify_config import normalize_backend
    from database.repositories import get_latest_profile

    status = get_scheduler_status()
    latest = get_latest_profile()
    profile = latest[1] if latest else None
    from services.notify_config import resolve_notify_config

    cfg = resolve_notify_config(profile)
    status["notifier_backend"] = cfg.backend
    status["max_digest_jobs"] = settings.max_digest_jobs
    status["whatsapp_configured"] = whatsapp_configured(profile)
    status["email_configured"] = email_configured(profile)
    status["google_drive"] = drive_credentials_status()
    status["google_drive_enabled"] = bool(cfg.google_drive_enabled and cfg.google_drive_folder_id)
    status["latest_notification_preview"] = get_latest_notification_preview()
    status["human_in_the_loop"] = True
    status["auto_apply"] = False
    try:
        from services.proxies import proxy_status

        status["proxies"] = proxy_status()
    except Exception:  # noqa: BLE001
        status["proxies"] = {"enabled": False, "configured": False, "count": 0}
    try:
        from services.cookies import cookie_status

        status["cookies"] = cookie_status()
    except Exception:  # noqa: BLE001
        status["cookies"] = {"enabled": False, "configured": False, "count": 0}
    return status
