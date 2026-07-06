"""Aggregate scraper — fetches from every registered job source."""

from __future__ import annotations

from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)


class AggregateSource:
  name = "all"

  def __init__(self, sources: list) -> None:
      self._sources = sources

  def fetch(
      self,
      profile: UserProfile,
      limit: int,
      *,
      allow_stretch: bool = False,
      flex_years: int | None = None,
  ) -> list[JobListing]:
      per_source = max(10, limit // max(len(self._sources), 1))
      all_jobs: list[JobListing] = []
      seen: set[str] = set()

      for source in self._sources:
          try:
              batch = source.fetch(
                  profile,
                  per_source,
                  allow_stretch=allow_stretch,
                  flex_years=flex_years,
              )
              for job in batch:
                  if job.content_hash in seen:
                      continue
                  seen.add(job.content_hash)
                  all_jobs.append(job)
              logger.info(f"Aggregate: {source.name} contributed {len(batch)} jobs")
          except Exception as exc:  # noqa: BLE001
              logger.error(f"Aggregate: {source.name} failed: {exc}")

      all_jobs.sort(key=lambda j: j.posted_at or j.scraped_at, reverse=True)
      return all_jobs[:limit]
