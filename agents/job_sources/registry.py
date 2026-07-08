"""Registry of popular job posting sites and their adapters."""

from __future__ import annotations

from typing import Protocol

from models.schemas import JobListing, UserProfile

# Popular job boards CareerPilot aggregates from.
POPULAR_JOB_SITES: list[dict[str, str]] = [
    {"id": "remotive", "name": "Remotive", "method": "api", "region": "global"},
    {"id": "remoteok", "name": "RemoteOK", "method": "api", "region": "global"},
    {"id": "arbeitnow", "name": "Arbeitnow", "method": "api", "region": "global"},
    {"id": "jobicy", "name": "Jobicy", "method": "api", "region": "global"},
    {"id": "himalayas", "name": "Himalayas", "method": "api", "region": "global"},
    {"id": "wellfound", "name": "Wellfound (AngelList)", "method": "scrape", "region": "global"},
    {"id": "indeed", "name": "Indeed", "method": "scrape", "region": "global"},
    {"id": "naukri", "name": "Naukri", "method": "scrape", "region": "india"},
    {"id": "linkedin", "name": "LinkedIn", "method": "scrape", "region": "global"},
    {"id": "glassdoor", "name": "Glassdoor", "method": "scrape", "region": "global"},
]


class JobSource(Protocol):
    name: str

    def fetch(
        self,
        profile: UserProfile,
        limit: int,
        *,
        allow_stretch: bool = False,
        flex_years: int | None = None,
    ) -> list[JobListing]:
        ...


def _build_registry() -> dict[str, JobSource]:
    from agents.job_sources.api_sources import (
        ArbeitnowSource,
        HimalayasSource,
        JobicySource,
        RemotiveSource,
        RemoteOKSource,
    )
    from agents.job_sources.scrape_sources import (
        GlassdoorSource,
        IndeedSource,
        LinkedInSource,
        NaukriSource,
        WellfoundSource,
    )
    from agents.job_sources.aggregate import AggregateSource

    sources: list[JobSource] = [
        RemotiveSource(),
        RemoteOKSource(),
        ArbeitnowSource(),
        JobicySource(),
        HimalayasSource(),
        WellfoundSource(),
        IndeedSource(),
        NaukriSource(),
        LinkedInSource(),
        GlassdoorSource(),
    ]
    registry = {s.name: s for s in sources}
    registry["all"] = AggregateSource(list(sources))
    return registry


_REGISTRY: dict[str, JobSource] | None = None


def get_source(name: str) -> JobSource:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY.get(name, _REGISTRY["all"])


def list_sources() -> list[dict[str, str]]:
    return POPULAR_JOB_SITES + [{"id": "all", "name": "All sources (aggregate)", "method": "mixed", "region": "global"}]
