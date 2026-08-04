"""Aggregate scraper — fetches from every registered job source."""

from __future__ import annotations

from core.logging import get_logger
from models.schemas import JobListing, UserProfile
from agents.job_sources.registry import resolve_enabled_sources

logger = get_logger(__name__)


class AggregateSource:
    name = "all"

    def __init__(self, sources: list) -> None:
        self._sources = sources
        self.last_fetch_report: list[dict] = []

    def fetch(
        self,
        profile: UserProfile,
        limit: int,
        *,
        allow_stretch: bool = False,
        flex_years: int | None = None,
    ) -> list[JobListing]:
        allowed = resolve_enabled_sources(profile)
        active = [s for s in self._sources if s.name in allowed]
        if not active:
            logger.warning("Aggregate: allowlist empty after resolve; using defaults")
            allowed = resolve_enabled_sources(None)
            active = [s for s in self._sources if s.name in allowed]

        per_source = max(10, limit // max(len(active), 1))
        all_jobs: list[JobListing] = []
        seen: set[str] = set()
        report: list[dict] = []

        enabled_names = {s.name for s in active}
        for source in self._sources:
            if source.name not in enabled_names:
                report.append(
                    {
                        "id": source.name,
                        "status": "skipped",
                        "requested": 0,
                        "returned": 0,
                        "detail": "not in profile allowlist / defaults",
                        "sample_titles": [],
                    }
                )

        for source in active:
            entry: dict = {
                "id": source.name,
                "status": "ok",
                "requested": per_source,
                "returned": 0,
                "detail": "",
                "sample_titles": [],
            }
            try:
                batch = source.fetch(
                    profile,
                    per_source,
                    allow_stretch=allow_stretch,
                    flex_years=flex_years,
                )
                entry["returned"] = len(batch)
                entry["sample_titles"] = [j.title for j in batch[:5]]
                if not batch:
                    entry["status"] = "empty"
                    entry["detail"] = "0 jobs after source fetch/filters"
                for job in batch:
                    if job.content_hash in seen:
                        continue
                    seen.add(job.content_hash)
                    all_jobs.append(job)
                logger.info(f"Aggregate: {source.name} contributed {len(batch)} jobs")
            except Exception as exc:  # noqa: BLE001
                entry["status"] = "error"
                entry["detail"] = str(exc)[:300]
                logger.error(f"Aggregate: {source.name} failed: {exc}")
            report.append(entry)

        # Keep report ordered: active sources first (as fetched), then skipped
        active_ids = {s.name for s in active}
        report.sort(
            key=lambda r: (0 if r["id"] in active_ids else 1, r["id"])
        )
        self.last_fetch_report = report

        all_jobs.sort(key=lambda j: j.posted_at or j.scraped_at, reverse=True)
        return all_jobs[:limit]
