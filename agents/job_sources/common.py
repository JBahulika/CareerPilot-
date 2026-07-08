"""Shared helpers for all job source adapters."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse

import requests

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing, UserProfile
from services.location import (
    effective_location,
    is_remote_location,
    location_filter_ok,
)
from services.seniority import (
    experience_label_for_job,
    is_job_compatible_with_profile,
)

logger = get_logger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# One pooled session for all API adapters — reuses TCP connections and applies
# a consistent, polite User-Agent. Much faster than a fresh connection per call.
_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "CareerPilot/1.0 (+https://github.com/JBahulika/CareerPilot-)"
        ),
        "Accept": "application/json",
    }
)

_DEFAULT_TIMEOUT = 30


def http_get(url: str, *, params: dict | None = None, timeout: int = _DEFAULT_TIMEOUT,
             headers: dict | None = None) -> requests.Response:
    """Shared GET with pooled connections and sane defaults."""
    resp = _SESSION.get(url, params=params, timeout=timeout, headers=headers)
    resp.raise_for_status()
    return resp


def content_hash(company: str, title: str, description: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{description[:500].strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def strip_html(text: str) -> str:
    cleaned = _HTML_TAG_RE.sub(" ", text or "").replace("&nbsp;", " ")
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def normalize_apply_url(url: str, *, base: str = "") -> str:
    """Return an absolute http(s) URL, or "" when one cannot be built.

    Handles absolute URLs, root-relative paths, and bare slugs (joined onto the
    source's base URL). Anything that cannot be resolved returns "".
    """
    url = (url or "").strip()
    if not url:
        return ""
    if _is_valid_url(url):
        return url
    base = (base or "").rstrip("/")
    if not base:
        return ""
    if url.startswith("/"):
        candidate = f"{base}{url}"
    else:
        candidate = f"{base}/{url.lstrip('/')}"
    return candidate if _is_valid_url(candidate) else ""


def search_fallback_url(company: str, title: str) -> str:
    """A guaranteed link so the user can always reach the posting.

    Used when a source does not expose a usable apply URL. Points at a Google
    search scoped to the exact role + company.
    """
    query = " ".join(p for p in (title, company, "job apply") if p).strip()
    if not query:
        return ""
    return f"https://www.google.com/search?q={quote_plus(query)}"


def ensure_apply_url(url: str, *, base: str, company: str, title: str) -> str:
    """Normalize the URL, falling back to a scoped search when none is usable."""
    normalized = normalize_apply_url(url, base=base)
    if normalized:
        return normalized
    return search_fallback_url(company, title)


def parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value)
        except (OSError, ValueError):
            return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def search_terms(profile: UserProfile) -> str:
    """Single string for scrapers that accept one query (legacy)."""
    queries = search_queries(profile)
    return queries[0] if queries else "software engineer"


def search_queries(profile: UserProfile) -> list[str]:
    from services.skills import search_queries as _queries

    return _queries(profile)


def search_location(profile: UserProfile) -> str:
    return effective_location(profile)


def sort_and_filter_recent(
    jobs: list[JobListing], *, recent_days: int | None = None
) -> list[JobListing]:
    now = datetime.utcnow()
    for job in jobs:
        if job.posted_at is None:
            job.posted_at = job.scraped_at or now
    jobs.sort(key=lambda j: j.posted_at or now, reverse=True)
    days = recent_days if recent_days is not None else settings.recent_jobs_days
    if days and days > 0:
        cutoff = now - timedelta(days=days)
        jobs = [j for j in jobs if (j.posted_at or now) >= cutoff]
    return jobs


def annotate_and_filter_jobs(
    jobs: list[JobListing],
    profile: UserProfile,
    *,
    allow_stretch: bool = False,
    flex_years: int | None = None,
    apply_experience: bool = True,
    apply_location: bool = True,
) -> list[JobListing]:
    kept: list[JobListing] = []
    pref = search_location(profile)
    for job in jobs:
        job.experience = experience_label_for_job(job)
        if apply_experience and not is_job_compatible_with_profile(
            job, profile, allow_stretch=allow_stretch, flex_years=flex_years
        ):
            continue
        if apply_location and not location_filter_ok(
            job, pref, include_remote=profile.include_remote
        ):
            continue
        kept.append(job)
    return kept


def prepare_scraped_jobs(
    jobs: list[JobListing], profile: UserProfile | None = None
) -> list[JobListing]:
    """Label seniority, apply domain relevance, then recency sort."""
    from services.skills import is_relevant_job_posting

    for job in jobs:
        job.experience = experience_label_for_job(job)
    if profile is not None:
        jobs = [j for j in jobs if is_relevant_job_posting(j, profile)]
    return sort_and_filter_recent(jobs)


def build_job(
    *,
    source: str,
    company: str,
    title: str,
    description: str,
    skills: list[str] | None = None,
    location: str = "",
    salary: str = "",
    apply_url: str = "",
    posted_at: datetime | None = None,
) -> JobListing:
    now = datetime.utcnow()
    return JobListing(
        source=source,
        company=company,
        title=title,
        description=description,
        skills=skills or [],
        location=location,
        salary=salary,
        apply_url=apply_url,
        content_hash=content_hash(company, title, description),
        posted_at=posted_at or now,
        scraped_at=now,
    )
