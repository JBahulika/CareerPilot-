"""Location helpers for job search and filtering."""

from __future__ import annotations

import re

from models.schemas import JobListing, UserProfile

_REMOTE_TERMS = (
    "remote",
    "anywhere",
    "work from home",
    "wfh",
    "distributed",
    "worldwide",
)

# Common city aliases (normalized key -> accepted variants).
_ALIASES: dict[str, set[str]] = {
    "bangalore": {"bangalore", "bengaluru", "blr"},
    "bengaluru": {"bangalore", "bengaluru", "blr"},
    "mumbai": {"mumbai", "bombay"},
    "delhi": {"delhi", "new delhi", "ncr"},
    "new delhi": {"delhi", "new delhi", "ncr"},
    "hyderabad": {"hyderabad", "hyd"},
    "chennai": {"chennai", "madras"},
    "kolkata": {"kolkata", "calcutta"},
    "pune": {"pune", "poona"},
    "gurgaon": {"gurgaon", "gurugram"},
    "gurugram": {"gurgaon", "gurugram"},
    "noida": {"noida", "greater noida"},
    "san francisco": {"san francisco", "sf", "bay area"},
    "new york": {"new york", "nyc", "new york city"},
    "london": {"london", "greater london"},
}

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


def _normalize(text: str) -> str:
    return _NON_ALNUM_RE.sub(" ", (text or "").lower()).strip()


def effective_location(profile: UserProfile, override: str | None = None) -> str:
    """Run override -> preferred_location -> resume location."""
    if override and override.strip():
        return override.strip()
    if profile.preferred_location and profile.preferred_location.strip():
        return profile.preferred_location.strip()
    return (profile.location or "").strip()


def is_remote_location(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    return any(term in normalized for term in _REMOTE_TERMS)


def locations_match(job_loc: str, pref: str) -> bool:
    job_n = _normalize(job_loc)
    pref_n = _normalize(pref)
    if not job_n or not pref_n:
        return False
    if pref_n in job_n or job_n in pref_n:
        return True
    pref_aliases = _ALIASES.get(pref_n, {pref_n})
    job_aliases = _ALIASES.get(job_n, {job_n})
    return bool(pref_aliases & job_aliases) or any(
        alias in job_n for alias in pref_aliases
    )


def location_filter_ok(
    job: JobListing,
    pref: str,
    *,
    include_remote: bool = True,
) -> bool:
    """Return True if job passes location preference."""
    pref = (pref or "").strip()
    if not pref:
        return True
    location = job.location or ""
    if include_remote and is_remote_location(location):
        return True
    if is_remote_location(location) and not include_remote:
        return False
    if not location.strip():
        # Unknown location: keep when remote is allowed, else drop.
        return include_remote
    return locations_match(location, pref)
