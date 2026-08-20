"""Pipeline trigger and status endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agents.orchestrator import run_pipeline
from core.config import settings
from core.logging import get_logger
from database.repositories import (
    create_run,
    get_profile,
    get_run,
    list_runs,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = get_logger(__name__)


class RunRequest(BaseModel):
    profile_id: int
    top_n: int = settings.top_n_jobs
    source: Optional[str] = None
    scrape_limit: int = Field(default=100, ge=1, le=settings.scrape_limit_max)
    exclude_internships: bool = False
    strict_experience: bool = True
    allow_stretch: bool = False
    flex_years: Optional[int] = None
    recent_days: Optional[int] = None
    location: Optional[str] = None
    include_remote: Optional[bool] = None
    min_match_score: Optional[int] = None  # per-run override; None = profile/default
    focus_field: Optional[str] = None  # per-run override; None = use profile
    # None = use profile.notify_on_manual_run; True/False = force for this run
    send_digest: Optional[bool] = None


@router.post("/run")
def start_pipeline(request: RunRequest, background_tasks: BackgroundTasks) -> dict:
    profile = get_profile(request.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    if request.focus_field is not None:
        from services.skills import normalize_focus_field

        profile = profile.model_copy(
            update={"focus_field": normalize_focus_field(request.focus_field)}
        )

    from services.notify_config import resolve_send_digest

    send_digest = resolve_send_digest(
        request_send_digest=request.send_digest,
        profile=profile,
    )

    run_id = create_run(request.profile_id)
    background_tasks.add_task(
        run_pipeline,
        run_id=run_id,
        profile=profile,
        top_n=request.top_n,
        source=request.source,
        scrape_limit=request.scrape_limit,
        exclude_internships=request.exclude_internships,
        strict_experience=request.strict_experience,
        allow_stretch=request.allow_stretch,
        flex_years=request.flex_years,
        recent_days=request.recent_days,
        location=request.location,
        include_remote=request.include_remote,
        min_match_score=request.min_match_score,
        send_digest=send_digest,
    )
    return {"run_id": run_id, "status": "pending", "send_digest": send_digest}


@router.get("/runs")
def get_runs(limit: int = 20) -> dict:
    return {"runs": list_runs(limit=limit)}


@router.get("/runs/{run_id}")
def run_status(run_id: int) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
