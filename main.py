"""CareerPilot AI — FastAPI application entry point.

Run with: uvicorn main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.base import check_ollama_status
from api.routes import jobs, pipeline, resume
from core.config import settings
from core.logging import get_logger
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
    version="0.1.0",
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "scheduler": get_scheduler_status()}


@app.get("/ollama/status")
def ollama_status() -> dict:
    ok, message = check_ollama_status()
    return {"ok": ok, "message": message, "model": settings.ollama_model}


@app.get("/scheduler/status")
def scheduler_status() -> dict:
    from services.notifier import get_latest_notification_preview

    status = get_scheduler_status()
    status["notifier_backend"] = settings.notifier_backend
    status["whatsapp_configured"] = bool(
        settings.whatsapp_token and settings.whatsapp_phone_id and settings.whatsapp_recipient
    )
    status["latest_notification_preview"] = get_latest_notification_preview()
    return status
