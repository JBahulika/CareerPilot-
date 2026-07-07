"""Shared helpers for all job source adapters."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

from core.config import settings
from models.schemas import JobListing, UserProfile
from agents.job_sources.common import infer_candidate_tier
from services.location import effective_location, location_filter_ok

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def content_hash(company: str, title: str, description: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{description[:500].strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(" ", text or "").replace("&nbsp;", " ").strip()


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
