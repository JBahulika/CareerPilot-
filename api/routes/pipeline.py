"""Pipeline trigger and status endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

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
    scrape_limit: int = 100
    exclude_internships: bool = False
    strict_experience: bool = True
    allow_stretch: bool = False
    flex_years: Optional[int] = None
    location: Optional[str] = None
    include_remote: Optional[bool] = None


@router.post("/run")
def start_pipeline(request: RunRequest, background_tasks: BackgroundTasks) -> dict:
    profile = get_profile(request.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

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
        location=request.location,
        include_remote=request.include_remote,
    )
    return {"run_id": run_id, "status": "pending"}


@router.get("/runs")
def get_runs(limit: int = 20) -> dict:
    return {"runs": list_runs(limit=limit)}


@router.get("/runs/{run_id}")
def run_status(run_id: int) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
