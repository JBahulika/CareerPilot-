"""Aggregate scraper — fetches from every registered job source.

API (HTTP) sources are fetched concurrently for speed; browser-based scrape
sources run sequentially to stay thread-safe with Playwright's sync API.
Results are merged, de-duplicated, and ranked best-first by relevance.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)

_MAX_WORKERS = 6


class AggregateSource:
    name = "all"

    def __init__(self, sources: list) -> None:
        self._sources = sources

    def _methods(self) -> dict[str, str]:
        from agents.job_sources.registry import POPULAR_JOB_SITES

        return {site["id"]: site["method"] for site in POPULAR_JOB_SITES}

    def fetch(
        self,
        profile: UserProfile,
        limit: int,
        *,
        allow_stretch: bool = False,
        flex_years: int | None = None,
    ) -> list[JobListing]:
        per_source = max(20, limit // max(len(self._sources), 1))
        methods = self._methods()

        def _run(source):
            batch = source.fetch(
                profile, per_source, allow_stretch=allow_stretch, flex_years=flex_years
            )
            logger.info(f"Aggregate: {source.name} contributed {len(batch)} jobs")
            return batch

        api_sources = [s for s in self._sources if methods.get(s.name) == "api"]
        scrape_sources = [s for s in self._sources if methods.get(s.name) != "api"]

        all_jobs: list[JobListing] = []
        seen: set[str] = set()

        def _collect(batch: list[JobListing]) -> None:
            for job in batch:
                if job.content_hash in seen:
                    continue
                seen.add(job.content_hash)
                all_jobs.append(job)

        # API sources: run concurrently (I/O bound HTTP calls).
        if api_sources:
            with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(api_sources))) as pool:
                futures = {pool.submit(_run, s): s for s in api_sources}
                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        _collect(future.result())
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Aggregate: {source.name} failed: {exc}")

        # Browser scrape sources: sequential (Playwright sync API isn't thread-safe).
        for source in scrape_sources:
            try:
                _collect(_run(source))
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Aggregate: {source.name} failed: {exc}")

        all_jobs.sort(
            key=lambda j: (
                j.relevance_score,
                j.posted_at or j.scraped_at or datetime.min,
            ),
            reverse=True,
        )
        return all_jobs[:limit]
