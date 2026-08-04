"""Job Scraper Agent (FR-3, FR-7).

Delegates to pluggable ``JobSource`` adapters in ``agents.job_sources``.
Use ``source_name='all'`` to aggregate from every popular job board.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from agents.job_sources.common import sort_and_filter_recent
from agents.job_sources.registry import get_source, list_sources
from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)


class JobScraperAgent:
    def __init__(self) -> None:
        self.last_scrape_report: dict = {}

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
        source_report = list(getattr(source, "last_fetch_report", None) or [])

        if not jobs and source_name not in ("all", "remotive"):
            logger.warning(f"'{source_name}' returned no jobs; falling back to aggregate.")
            agg = get_source("all")
            jobs = agg.fetch(
                profile, limit, allow_stretch=allow_stretch, flex_years=flex
            )
            source_report = list(getattr(agg, "last_fetch_report", None) or [])
            source_name = "all"

        if not source_report:
            source_report = [
                {
                    "id": getattr(source, "name", source_name or "unknown"),
                    "status": "ok" if jobs else "empty",
                    "requested": limit,
                    "returned": len(jobs),
                    "detail": "" if jobs else "0 jobs returned",
                    "sample_titles": [j.title for j in jobs[:5]],
                }
            ]

        jobs = self._dedup(jobs)
        days = recent_days if recent_days is not None else settings.recent_jobs_days
        before_recency = len(jobs)
        jobs = sort_and_filter_recent(jobs, recent_days=days)

        kept_by_source = Counter(j.source for j in jobs)
        for row in source_report:
            row["kept_after_recency"] = int(kept_by_source.get(row["id"], 0))

        failed = [r["id"] for r in source_report if r.get("status") == "error"]
        empty = [
            r["id"]
            for r in source_report
            if r.get("status") in ("empty", "ok") and int(r.get("returned") or 0) == 0
        ]
        ok = [r["id"] for r in source_report if int(r.get("returned") or 0) > 0]

        self.last_scrape_report = {
            "mode": source_name,
            "per_source": source_report,
            "sources_with_jobs": ok,
            "sources_empty": empty,
            "sources_error": failed,
            "sources_skipped": [
                r["id"] for r in source_report if r.get("status") == "skipped"
            ],
            "jobs_before_recency": before_recency,
            "jobs_after_recency": len(jobs),
            "recent_days": days,
        }
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
