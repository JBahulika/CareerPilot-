"""Aggregate scraper — fetches from every registered job source."""

from __future__ import annotations

from agents.job_sources.budget import allocate_scrape_budgets
from agents.job_sources.common import early_relevance_score, job_identity_key
from agents.job_sources.registry import resolve_enabled_sources
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

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

        budgets = allocate_scrape_budgets([s.name for s in active], limit)
        all_jobs: list[JobListing] = []
        seen_hash: set[str] = set()
        seen_identity: set[str] = set()
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
            per_source = budgets.get(source.name, max(8, limit // max(len(active), 1)))
            entry: dict = {
                "id": source.name,
                "status": "ok",
                "requested": per_source,
                "returned": 0,
                "kept": 0,
                "detail": f"even budget={per_source}",
                "sample_titles": [],
            }
            kept = 0
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
                    if job.content_hash in seen_hash:
                        continue
                    ident = job_identity_key(job)
                    if ident in seen_identity:
                        continue
                    seen_hash.add(job.content_hash)
                    seen_identity.add(ident)
                    all_jobs.append(job)
                    kept += 1
                entry["kept"] = kept
                logger.info(
                    f"Aggregate: {source.name} requested={per_source} "
                    f"returned={len(batch)} kept={kept}"
                )
            except Exception as exc:  # noqa: BLE001
                entry["status"] = "error"
                entry["detail"] = str(exc)[:300]
                logger.error(f"Aggregate: {source.name} failed: {exc}")
            report.append(entry)

        active_ids = {s.name for s in active}
        report.sort(key=lambda r: (0 if r["id"] in active_ids else 1, r["id"]))
        self.last_fetch_report = report

        # Prefer recent + early skill/role relevance when truncating to limit
        all_jobs.sort(
            key=lambda j: (
                early_relevance_score(j, profile),
                j.posted_at or j.scraped_at,
            ),
            reverse=True,
        )
        return all_jobs[:limit]
