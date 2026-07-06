"""Job scraping and match retrieval endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from agents.scraper_agent import JobScraperAgent
from core.logging import get_logger
from database.repositories import (
    get_latest_profile,
    get_matches_for_run,
    upsert_jobs,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)
_scraper = JobScraperAgent()


@router.post("/scrape")
def scrape_jobs(
    limit: int = Query(100, ge=1, le=300),
    source: Optional[str] = Query(None, description="remotive | wellfound"),
) -> dict:
    result = get_latest_profile()
    if result is None:
        raise HTTPException(status_code=404, detail="Upload a resume first.")
    _, profile = result

    jobs = _scraper.run(profile, limit=limit, source_name=source)
    upsert_jobs(jobs)
    return {
        "count": len(jobs),
        "source": source or "default",
        "jobs": [j.model_dump(mode="json") for j in jobs],
    }


@router.get("/matches/{run_id}")
def matches_for_run(run_id: int, top_n: int = Query(10, ge=1, le=50)) -> dict:
    matches = get_matches_for_run(run_id)
    return {"run_id": run_id, "count": len(matches), "matches": matches[:top_n]}
