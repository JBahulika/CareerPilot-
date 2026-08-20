"""Shared helpers for all job source adapters."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urljoin

from core.config import settings
from models.schemas import JobListing, UserProfile
from services.seniority import (
    experience_label_for_job,
    infer_candidate_tier,
    is_job_compatible_with_profile,
)
from services.location import effective_location, format_geo_query, location_filter_ok

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def normalize_apply_url(url: str, *, base: str = "") -> str:
    """Turn relative/slug apply links into absolute URLs when possible."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    base = (base or "").strip()
    if not base:
        return ""
    if raw.startswith("/"):
        return urljoin(base if base.endswith("/") else base + "/", raw.lstrip("/"))
    # Bare slug (e.g. Himalayas) — join under base path
    return urljoin(base.rstrip("/") + "/", raw)


def search_fallback_url(company: str, title: str) -> str:
    """Guaranteed search link when no board URL was scraped."""
    q = quote_plus(f"{title} {company} job apply".strip())
    return f"https://www.google.com/search?q={q}"


def ensure_apply_url(
    url: str,
    *,
    base: str = "",
    company: str = "",
    title: str = "",
) -> str:
    """Normalize if possible; otherwise fall back to a Google job search link."""
    normalized = normalize_apply_url(url, base=base)
    if normalized:
        return normalized
    return search_fallback_url(company, title)


def content_hash(company: str, title: str, description: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{description[:500].strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(" ", text or "").replace("&nbsp;", " ").strip()


def parse_posted_at(value: str | None) -> datetime | None:
    """Parse absolute or relative job post dates into naive UTC datetimes."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            # Heuristic: ms vs seconds
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.utcfromtimestamp(ts)
        except (OSError, ValueError, OverflowError):
            return None

    text = str(value).strip()
    if not text:
        return None

    relative = parse_relative_posted_at(text)
    if relative is not None:
        return relative

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",  # RSS
        "%d %b %Y",
        "%b %d, %Y",
    ):
        try:
            dt = datetime.strptime(text[:32], fmt) if "%z" not in fmt else datetime.strptime(text, fmt)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    return None


_RELATIVE_POSTED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bjust\s+posted\b|\btoday\b|\bhours?\s+ago\b|\bminutes?\s+ago\b", re.I), "today"),
    (re.compile(r"\byesterday\b", re.I), "yesterday"),
    (re.compile(r"\b(\d+)\s*days?\s*ago\b", re.I), "days"),
    (re.compile(r"\b(\d+)\s*weeks?\s*ago\b", re.I), "weeks"),
    (re.compile(r"\b(\d+)\s*months?\s*ago\b", re.I), "months"),
    (re.compile(r"\b(\d+)\s*years?\s*ago\b", re.I), "years"),
]


def parse_relative_posted_at(text: str, *, now: datetime | None = None) -> datetime | None:
    """Parse phrases like '5 months ago' / '2 weeks ago' from listing text.

    Prefers short standalone lines (typical job-card metadata) so prose like
    'founded 5 years ago' in a long description is less likely to win.
    """
    if not text:
        return None
    now = now or datetime.utcnow()

    candidates: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) <= 40:
            candidates.append(stripped)
    # Also consider a short head of the blob (API one-liners)
    head = " ".join(text.split())[:80]
    if head:
        candidates.append(head)

    for blob in candidates:
        for pattern, kind in _RELATIVE_POSTED_PATTERNS:
            m = pattern.search(blob)
            if not m:
                continue
            # Require the line to be mostly the date phrase (card meta),
            # not a long sentence that happens to include 'years ago'.
            if len(blob) > 28 and kind in {"months", "years"}:
                continue
            if kind == "today":
                return now
            if kind == "yesterday":
                return now - timedelta(days=1)
            n = int(m.group(1))
            if kind == "days":
                return now - timedelta(days=n)
            if kind == "weeks":
                return now - timedelta(weeks=n)
            if kind == "months":
                return now - timedelta(days=30 * n)
            if kind == "years":
                return now - timedelta(days=365 * n)
    return None


def coerce_posted_at(
    value: str | datetime | int | float | None = None,
    *,
    fallback_text: str = "",
) -> datetime | None:
    """Best-effort post date from API field and/or free text (never invents 'now')."""
    parsed = parse_posted_at(value) if value not in (None, "") else None
    if parsed is not None:
        return parsed
    if fallback_text:
        return parse_relative_posted_at(fallback_text) or parse_posted_at(fallback_text)
    return None


def search_queries(profile: UserProfile, *, max_queries: int = 6) -> list[str]:
    """Board search queries blending resume skills and preferred roles.

    Interleaves skill queries, role queries, and skill+role combos so boards
    that rank by title still surface relevant listings. Optional ``focus_field``
    adds field role phrases first.
    """
    from services.skills import (
        get_focus_field_meta,
        role_search_terms,
        skill_search_terms,
    )

    max_queries = max(1, min(8, int(max_queries)))
    queries: list[str] = []

    def _add(q: str) -> None:
        clean = " ".join(q.split())
        if clean and clean.lower() not in {x.lower() for x in queries}:
            queries.append(clean)

    skills = skill_search_terms(profile, limit=10)
    roles = role_search_terms(profile)
    focus = get_focus_field_meta(profile)
    tier = infer_candidate_tier(profile)

    # Focus field roles first when set
    if focus:
        for role in list(focus.get("roles") or ())[:2]:
            _add(str(role))
        for term in list(focus.get("search_terms") or ())[:2]:
            _add(str(term))

    # Preferred / inferred roles (with junior prefix for entry-level)
    for role in roles[:3]:
        if tier <= 1:
            _add(f"junior {role}")
        _add(role)
        if len(queries) >= max_queries:
            return queries[:max_queries]

    # Individual skills
    for skill in skills:
        _add(skill)
        if len(queries) >= max_queries - 1:
            break

    # Skill + role combos (boards often rank these well)
    if skills and roles:
        _add(f"{skills[0]} {roles[0]}")
        if len(skills) >= 2:
            _add(f"{skills[1]} {roles[0]}")

    # Blend of top skills
    if len(skills) >= 2:
        _add(" ".join(skills[:3]))

    if not queries:
        queries = roles[:1] or skills[:1] or ["software engineer"]
    return queries[:max_queries]


def search_terms(profile: UserProfile) -> str:
    """Primary board search string (first skill/role query)."""
    return search_queries(profile)[0]


def split_limit_across_queries(limit: int, n_queries: int) -> list[int]:
    """Distribute a per-source limit across N search queries."""
    n = max(1, int(n_queries))
    limit = max(0, int(limit))
    if limit == 0:
        return [0] * n
    base = max(1, limit // n)
    parts = [base] * n
    rem = limit - base * n
    i = 0
    while rem > 0:
        parts[i % n] += 1
        rem -= 1
        i += 1
    while sum(parts) > limit:
        for j in range(n - 1, -1, -1):
            if parts[j] > 0:
                parts[j] -= 1
                break
    return parts


def job_identity_key(job: JobListing) -> str:
    """Cross-source identity: prefer apply URL, else company+title."""
    url = (job.apply_url or "").strip().lower()
    if url.startswith("http"):
        return "url:" + url.split("?", 1)[0].rstrip("/")
    company = (job.company or "").strip().lower()
    title = (job.title or "").strip().lower()
    return f"ct:{company}|{title}"


def early_relevance_score(job: JobListing, profile: UserProfile) -> int:
    """Cheap 0–100 score — skills weigh more than role-title hits."""
    from services.skills import role_search_terms, skill_hits_in_text

    hay = f"{job.title} {job.description} {' '.join(job.skills)}".lower()
    score = skill_hits_in_text(profile, hay) * 14
    for role in role_search_terms(profile):
        for token in role.lower().split():
            if len(token) > 2 and token in hay:
                score += 4
                break
    title_l = (job.title or "").lower()
    if any(w in title_l for w in ("intern", "internship")) and infer_candidate_tier(profile) >= 2:
        score -= 20
    return max(0, min(100, score))


def search_location(profile: UserProfile) -> str:
    pref = effective_location(profile)
    return format_geo_query(pref) if pref else ""


def sort_and_filter_recent(
    jobs: list[JobListing], *, recent_days: int | None = None
) -> list[JobListing]:
    """Sort newest-first and drop jobs older than ``recent_days``.

    When a recency window is active, jobs with no usable ``posted_at`` are
    dropped (fail closed) so missing dates cannot sneak in as "fresh".

    Phase 10a: when ``still_hiring_prefer`` is on, likely-still-hiring jobs
    (within ``still_hiring_days``) sort ahead of older dated jobs; undated
    jobs remain excluded when a recency window is active.
    """
    now = datetime.utcnow()
    for job in jobs:
        if job.posted_at is None:
            # Last chance: relative phrases buried in description/title
            recovered = coerce_posted_at(
                fallback_text=f"{job.title} {job.description[:500]}"
            )
            if recovered is not None:
                job.posted_at = recovered
        elif job.posted_at.tzinfo is not None:
            job.posted_at = job.posted_at.replace(tzinfo=None)

    days = recent_days if recent_days is not None else settings.recent_jobs_days
    if days and days > 0:
        cutoff = now - timedelta(days=days)
        kept: list[JobListing] = []
        for job in jobs:
            posted = job.posted_at
            if posted is None:
                continue  # unknown age — do not treat as fresh
            if posted.tzinfo is not None:
                posted = posted.replace(tzinfo=None)
            if posted >= cutoff:
                kept.append(job)
        jobs = kept

    prefer = bool(getattr(settings, "still_hiring_enabled", True)) and bool(
        getattr(settings, "still_hiring_prefer", True)
    )
    if prefer:
        from services.still_hiring import classify_still_hiring, still_hiring_sort_key

        jobs.sort(
            key=lambda j: (
                still_hiring_sort_key(
                    classify_still_hiring(posted_at=j.posted_at, now=now)
                ),
                -(j.posted_at.timestamp() if j.posted_at else 0.0),
            )
        )
    else:
        jobs.sort(
            key=lambda j: j.posted_at or datetime.min,
            reverse=True,
        )
    return jobs


def annotate_and_filter_jobs(
    jobs: list[JobListing],
    profile: UserProfile,
    *,
    allow_stretch: bool = False,
    flex_years: int | None = None,
) -> list[JobListing]:
    kept: list[JobListing] = []
    pref = search_location(profile)
    for job in jobs:
        job.experience = experience_label_for_job(job)
        if not is_job_compatible_with_profile(
            job, profile, allow_stretch=allow_stretch, flex_years=flex_years
        ):
            continue
        if not location_filter_ok(
            job, pref, include_remote=profile.include_remote
        ):
            continue
        kept.append(job)
    return kept


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
    apply_base: str = "",
    posted_at: datetime | None = None,
) -> JobListing:
    from services.job_text import enrich_job_listing

    now = datetime.utcnow()
    # Prefer explicit date; else recover from listing text; never invent "now"
    # (inventing now made stale jobs pass the recency window).
    resolved = posted_at
    if resolved is None:
        resolved = coerce_posted_at(fallback_text=f"{title} {description[:800]}")
    if resolved is not None and resolved.tzinfo is not None:
        resolved = resolved.replace(tzinfo=None)

    job = JobListing(
        source=source,
        company=company,
        title=title,
        description=description,
        skills=skills or [],
        location=location,
        salary=salary,
        apply_url=ensure_apply_url(
            apply_url, base=apply_base, company=company, title=title
        ),
        content_hash=content_hash(company, title, description),
        posted_at=resolved,
        scraped_at=now,
    )
    return enrich_job_listing(job)
