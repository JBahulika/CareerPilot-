"""Job Scraper Agent (FR-3, FR-7).

Delegates to pluggable ``JobSource`` adapters in ``agents.job_sources``.
Use ``source_name='all'`` to aggregate from every popular job board.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agents.job_sources.common import sort_and_filter_recent
from agents.job_sources.registry import get_source, list_sources
from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)


class JobScraperAgent:
    def run(
        self,
        profile: UserProfile,
        limit: int = 100,
        source_name: str | None = None,
        allow_stretch: bool = False,
        flex_years: int | None = None,
        recent_days: int | None = None,
    ) -> list[JobListing]:
        source_name = source_name or settings.job_source
        flex = flex_years if flex_years is not None else settings.experience_flex_years
        source = get_source(source_name)
        logger.info(f"Scraping from source: {source.name}")

        jobs = source.fetch(
            profile,
            limit,
            allow_stretch=allow_stretch,
            flex_years=flex,
        )

        if not jobs and source_name not in ("all", "remotive"):
            logger.warning(f"'{source_name}' returned no jobs; falling back to aggregate.")
            jobs = get_source("all").fetch(
                profile, limit, allow_stretch=allow_stretch, flex_years=flex
            )

        jobs = self._dedup(jobs)
        days = recent_days if recent_days is not None else settings.recent_jobs_days
        jobs = sort_and_filter_recent(jobs, recent_days=days)
        self._snapshot(jobs, source_name)
        return jobs

    @staticmethod
    def available_sources() -> list[dict[str, str]]:
        return list_sources()

    @staticmethod
    def _dedup(jobs: list[JobListing]) -> list[JobListing]:
        seen: set[str] = set()
        unique: list[JobListing] = []
        for job in jobs:
            if job.content_hash in seen:
                continue
            seen.add(job.content_hash)
            unique.append(job)
        return unique

    @staticmethod
    def _snapshot(jobs: list[JobListing], source_name: str) -> None:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = Path(settings.jobs_dir) / f"{source_name}_{stamp}.json"
        try:
            path.write_text(
                json.dumps([j.model_dump(mode="json") for j in jobs], indent=2),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not write job snapshot: {exc}")
