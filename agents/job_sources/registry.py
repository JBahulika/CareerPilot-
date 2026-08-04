"""Registry of popular job posting sites and their adapters."""

from __future__ import annotations

from typing import Protocol

from models.schemas import JobListing, UserProfile

# safety:
#   api              — public JSON/API (preferred)
#   scrape_safe      — HTML scrape, usually works without login walls
#   scrape_risky     — often flaky / soft-gated
#   disabled_captcha — frequent captcha/login challenges; off by default
POPULAR_JOB_SITES: list[dict[str, object]] = [
    {
        "id": "remotive",
        "name": "Remotive",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public JSON API",
    },
    {
        "id": "remoteok",
        "name": "RemoteOK",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public JSON API",
    },
    {
        "id": "arbeitnow",
        "name": "Arbeitnow",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public JSON API",
    },
    {
        "id": "jobicy",
        "name": "Jobicy",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public JSON API",
    },
    {
        "id": "himalayas",
        "name": "Himalayas",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public JSON API",
    },
    {
        "id": "themuse",
        "name": "The Muse",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public jobs API (no key)",
    },
    {
        "id": "weworkremotely",
        "name": "We Work Remotely",
        "method": "rss",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public RSS feed",
    },
    {
        "id": "workingnomads",
        "name": "Working Nomads",
        "method": "api",
        "safety": "api",
        "enabled_by_default": True,
        "region": "global",
        "notes": "Public exposed_jobs JSON",
    },
    {
        "id": "wellfound",
        "name": "Wellfound (AngelList)",
        "method": "scrape",
        "safety": "scrape_risky",
        "enabled_by_default": False,
        "region": "global",
        "notes": "Playwright scrape; soft gates common",
    },
    {
        "id": "naukri",
        "name": "Naukri",
        "method": "scrape",
        "safety": "scrape_risky",
        "enabled_by_default": False,
        "region": "india",
        "notes": "Playwright scrape; bot checks common",
    },
    {
        "id": "indeed",
        "name": "Indeed",
        "method": "scrape",
        "safety": "disabled_captcha",
        "enabled_by_default": False,
        "region": "global",
        "notes": "Frequent captcha/challenge pages — off by default",
    },
    {
        "id": "linkedin",
        "name": "LinkedIn",
        "method": "scrape",
        "safety": "disabled_captcha",
        "enabled_by_default": False,
        "region": "global",
        "notes": "Login/captcha walls — off by default; never bypass",
    },
    {
        "id": "glassdoor",
        "name": "Glassdoor",
        "method": "scrape",
        "safety": "disabled_captcha",
        "enabled_by_default": False,
        "region": "global",
        "notes": "Frequent bot checks — off by default",
    },
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


def default_enabled_source_ids() -> list[str]:
    return [
        str(s["id"])
        for s in POPULAR_JOB_SITES
        if s.get("enabled_by_default")
    ]


def resolve_enabled_sources(profile: UserProfile | None = None) -> set[str]:
    """Allowlist for aggregate runs. Empty profile list → defaults only."""
    known = {str(s["id"]) for s in POPULAR_JOB_SITES}
    if profile is not None and profile.enabled_sources:
        chosen = {sid for sid in profile.enabled_sources if sid in known}
        return chosen or set(default_enabled_source_ids())
    return set(default_enabled_source_ids())


def _build_registry() -> dict[str, JobSource]:
    from agents.job_sources.api_sources import (
        ArbeitnowSource,
        HimalayasSource,
        JobicySource,
        RemotiveSource,
        RemoteOKSource,
        TheMuseSource,
        WeWorkRemotelySource,
        WorkingNomadsSource,
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
        TheMuseSource(),
        WeWorkRemotelySource(),
        WorkingNomadsSource(),
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


def list_sources() -> list[dict]:
    base = [dict(s) for s in POPULAR_JOB_SITES]
    base.append(
        {
            "id": "all",
            "name": "All sources (aggregate)",
            "method": "mixed",
            "safety": "api",
            "enabled_by_default": True,
            "region": "global",
            "notes": "Respects profile allowlist + default-enabled flags",
        }
    )
    return base


def list_sources_with_health() -> list[dict]:
    """Sources metadata plus live health status for Setup/API."""
    from services.source_health import get_source_health_registry

    health = get_source_health_registry()
    rows = []
    for meta in list_sources():
        sid = str(meta["id"])
        if sid == "all":
            rows.append({**meta, "health": "ok", "health_detail": "aggregate"})
            continue
        h = health.get(sid)
        rows.append(
            {
                **meta,
                "health": h.status,
                "health_detail": h.detail,
                "health_updated_at": h.updated_at,
            }
        )
    return rows
