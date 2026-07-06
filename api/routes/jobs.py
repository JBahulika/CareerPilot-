"""Job scraping and match retrieval endpoints."""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from agents.scraper_agent import JobScraperAgent
from agents.job_sources.registry import list_sources
from core.config import settings
from core.logging import get_logger
from database.repositories import (
    get_latest_profile,
    get_matches_for_run,
    upsert_jobs,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)
_scraper = JobScraperAgent()


@router.get("/sources")
def job_sources() -> dict:
    return {"sources": list_sources()}


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
def matches_for_run(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(None, ge=1, le=50),
    top_n: Optional[int] = Query(None, ge=1, le=50, deprecated=True),
) -> dict:
    """Paginated match results for a pipeline run."""
    size = page_size or top_n or settings.display_page_size
    size = min(size, settings.max_page_size)
    offset = (page - 1) * size

    matches, total = get_matches_for_run(run_id, offset=offset, limit=size)
    total_pages = max(1, math.ceil(total / size)) if total else 1

    return {
        "run_id": run_id,
        "total": total,
        "page": page,
        "page_size": size,
        "total_pages": total_pages,
        "matches": matches,
    }
