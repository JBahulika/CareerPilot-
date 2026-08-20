"""Job scraping and match retrieval endpoints."""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from agents.scraper_agent import JobScraperAgent
from agents.job_sources.registry import list_sources, list_sources_with_health
from core.config import settings
from core.logging import get_logger
from database.repositories import (
    get_latest_profile,
    get_match_detail,
    get_matches_for_run,
    get_profile,
    get_run,
    upsert_jobs,
)
from services.source_health import get_source_health_registry

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)
_scraper = JobScraperAgent()


@router.get("/sources")
def job_sources() -> dict:
    return {"sources": list_sources_with_health()}


@router.get("/sources/health")
def job_sources_health() -> dict:
    """Per-source health: ok | rate_limited | captcha_blocked | disabled | error."""
    ids = [s["id"] for s in list_sources() if s["id"] != "all"]
    return {
        "cooldown_seconds": settings.scrape_health_cooldown_seconds,
        "sources": get_source_health_registry().list_all(ids),
    }

@router.post("/scrape")
def scrape_jobs(
    limit: int = Query(100, ge=1, le=settings.scrape_limit_max),
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
    min_score: Optional[int] = Query(
        None,
        ge=0,
        le=100,
        description="Minimum match score to include (e.g. 1 for all weak matches).",
    ),
) -> dict:
    """Paginated match results for a pipeline run."""
    size = page_size or top_n or settings.display_page_size
    size = min(size, settings.max_page_size)
    offset = (page - 1) * size

    matches, total = get_matches_for_run(
        run_id, offset=offset, limit=size, min_score=min_score
    )
    total_pages = max(1, math.ceil(total / size)) if total else 1

    return {
        "run_id": run_id,
        "total": total,
        "page": page,
        "page_size": size,
        "total_pages": total_pages,
        "min_score": min_score,
        "matches": matches,
    }


def _profile_for_run(run_id: int):
    run = get_run(run_id)
    if run and run.get("profile_id"):
        profile = get_profile(int(run["profile_id"]))
        if profile is not None:
            return profile
    latest = get_latest_profile()
    return latest[1] if latest else None


@router.get("/matches/{run_id}/{match_id}/skills-gap")
def skills_gap_for_match(run_id: int, match_id: int) -> dict:
    """Skills gap for a user-selected match. Never auto-applies."""
    detail = get_match_detail(run_id, match_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Match not found for this run.")
    from services.job_assist import build_skills_gap

    profile = _profile_for_run(run_id)
    gap = build_skills_gap(detail, profile)
    gap["run_id"] = run_id
    return gap


@router.post("/matches/{run_id}/{match_id}/cover-letter")
def cover_letter_for_match(run_id: int, match_id: int) -> dict:
    """Draft a cover letter via Ollama for a user-selected match. Never sends/applies."""
    detail = get_match_detail(run_id, match_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Match not found for this run.")
    profile = _profile_for_run(run_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Upload a resume / profile first.")
    from services.job_assist import draft_cover_letter

    try:
        result = draft_cover_letter(profile, detail)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Cover letter draft failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"Could not draft cover letter (is Ollama running?): {exc}",
        ) from exc
    result["run_id"] = run_id
    return result
