"""Phase 11 — authenticated phone remote control API.

All routes require ``REMOTE_API_TOKEN`` (Bearer or ``X-Remote-Token``).
Processing stays on the host; the phone only sends commands and reads status.
Never auto-applies. Never solves captchas.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agents.orchestrator import run_pipeline
from core.config import settings
from core.logging import get_logger
from core.model_pins import read_version
from core.remote_auth import RemoteAuth, remote_api_enabled
from database.repositories import (
    create_run,
    get_latest_profile,
    get_profile,
    get_run,
    list_runs,
)
from services.notify_config import resolve_send_digest
from services.remote_settings import apply_remote_settings, list_recent_digests
from services.scheduler import get_scheduler_status

router = APIRouter(prefix="/remote", tags=["remote"])
logger = get_logger(__name__)


class RemoteRunRequest(BaseModel):
    profile_id: Optional[int] = None  # default: latest profile
    top_n: int = Field(default=10, ge=1, le=50)
    scrape_limit: int = Field(default=80, ge=1, le=500)
    source: Optional[str] = None
    send_digest: Optional[bool] = None
    location: Optional[str] = None
    min_match_score: Optional[int] = Field(default=None, ge=0, le=100)


class RemoteSettingsPatch(BaseModel):
    daily_scan_enabled: Optional[bool] = None
    notifier_backend: Optional[str] = None  # local | whatsapp | email | both
    whatsapp_enabled: Optional[bool] = None
    notify_on_manual_run: Optional[bool] = None
    profile_id: Optional[int] = None


@router.get("/ping")
def remote_ping(_: RemoteAuth) -> dict:
    """Cheap auth check for the mobile UI."""
    return {
        "ok": True,
        "version": read_version(),
        "remote_enabled": remote_api_enabled(),
        "auto_apply": False,
        "captcha_solving": False,
    }


@router.get("/status")
def remote_status(_: RemoteAuth) -> dict:
    latest = get_latest_profile()
    profile_id = latest[0] if latest else None
    runs = list_runs(limit=5)
    sched = get_scheduler_status()
    return {
        "version": read_version(),
        "profile_id": profile_id,
        "has_profile": profile_id is not None,
        "scheduler": sched,
        "notifier_backend": settings.notifier_backend,
        "daily_scan_enabled": settings.daily_scan_enabled,
        "recent_runs": runs,
        "auto_apply": False,
        "note": "CareerPilot never auto-applies. Digests are for your review only.",
    }


@router.post("/pipeline/run")
def remote_pipeline_run(
    body: RemoteRunRequest, background_tasks: BackgroundTasks, _: RemoteAuth
) -> dict:
    profile_id = body.profile_id
    profile = get_profile(profile_id) if profile_id else None
    if profile is None:
        latest = get_latest_profile()
        if not latest:
            raise HTTPException(
                status_code=404,
                detail="No profile found. Upload a resume on the PC Streamlit UI first.",
            )
        profile_id, profile = latest

    send_digest = resolve_send_digest(
        request_send_digest=body.send_digest,
        profile=profile,
    )
    run_id = create_run(profile_id)
    background_tasks.add_task(
        run_pipeline,
        run_id=run_id,
        profile=profile,
        top_n=body.top_n,
        source=body.source,
        scrape_limit=body.scrape_limit,
        location=body.location,
        min_match_score=body.min_match_score,
        send_digest=send_digest,
    )
    logger.info(f"Remote pipeline started run_id={run_id} profile_id={profile_id}")
    return {
        "run_id": run_id,
        "status": "pending",
        "profile_id": profile_id,
        "send_digest": send_digest,
        "message": "Pipeline started on the host. Poll GET /remote/pipeline/runs/{run_id}.",
    }


@router.get("/pipeline/runs")
def remote_list_runs(_: RemoteAuth, limit: int = 10) -> dict:
    return {"runs": list_runs(limit=max(1, min(limit, 50)))}


@router.get("/pipeline/runs/{run_id}")
def remote_run_status(run_id: int, _: RemoteAuth) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@router.get("/digests/latest")
def remote_latest_digests(_: RemoteAuth, limit: int = 5) -> dict:
    return {"digests": list_recent_digests(limit=limit)}


@router.patch("/settings")
def remote_patch_settings(body: RemoteSettingsPatch, _: RemoteAuth) -> dict:
    if (
        body.daily_scan_enabled is None
        and body.notifier_backend is None
        and body.whatsapp_enabled is None
        and body.notify_on_manual_run is None
    ):
        raise HTTPException(status_code=400, detail="No settings fields provided.")
    try:
        result = apply_remote_settings(
            daily_scan_enabled=body.daily_scan_enabled,
            notifier_backend=body.notifier_backend,
            whatsapp_enabled=body.whatsapp_enabled,
            notify_on_manual_run=body.notify_on_manual_run,
            profile_id=body.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result, "scheduler": get_scheduler_status()}
