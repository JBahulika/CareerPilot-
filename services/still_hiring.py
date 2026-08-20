"""Still-hiring signals from listing dates (Phase 10a).

Prefers jobs that look freshly posted / recently updated. Never invents
"still hiring" when ``posted_at`` is unknown — fail closed (``unknown``).
Does not scrape employer ATS for live status; date-based heuristic only.
No auto-apply.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal, Mapping, Optional, Sequence

from core.config import settings

StillHiringStatus = Literal["likely", "stale", "unknown"]


def still_hiring_enabled() -> bool:
    return bool(getattr(settings, "still_hiring_enabled", True))


def still_hiring_days() -> int:
    return max(1, int(getattr(settings, "still_hiring_days", 7)))


def _as_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def parse_posted_value(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _as_naive(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return _as_naive(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def classify_still_hiring(
    *,
    posted_at: datetime | str | None,
    now: datetime | None = None,
    window_days: int | None = None,
) -> StillHiringStatus:
    """Return likely | stale | unknown from a real posted date only."""
    posted = parse_posted_value(posted_at) if not isinstance(posted_at, datetime) else _as_naive(posted_at)
    if posted is None:
        return "unknown"
    days = window_days if window_days is not None else still_hiring_days()
    days = max(1, int(days))
    ref = _as_naive(now) or datetime.utcnow()
    age = ref - posted
    if age < timedelta(0):
        # Future-dated listings — treat as likely fresh, not invented
        return "likely"
    if age <= timedelta(days=days):
        return "likely"
    return "stale"


def still_hiring_label(status: StillHiringStatus) -> str:
    if status == "likely":
        return "Likely still hiring"
    if status == "stale":
        return "Older listing"
    return "Date unknown"


def still_hiring_sort_key(status: StillHiringStatus) -> int:
    """Lower = preferred when sorting."""
    return {"likely": 0, "stale": 1, "unknown": 2}.get(status, 2)


def annotate_match_still_hiring(match: Mapping[str, Any]) -> dict[str, Any]:
    """Add still_hiring fields to a match dict (never claims likely without a date)."""
    row = dict(match)
    status = classify_still_hiring(posted_at=match.get("posted_at"))
    row["still_hiring"] = status
    row["still_hiring_label"] = still_hiring_label(status)
    return row


def prefer_still_hiring(
    items: Sequence[Mapping[str, Any]],
    *,
    enabled: bool | None = None,
) -> list[dict[str, Any]]:
    """Stable-ish sort: likely first, then by match_score desc, then fresher posted_at."""
    use = still_hiring_enabled() if enabled is None else bool(enabled)
    annotated = [annotate_match_still_hiring(m) for m in items]
    if not use or not bool(getattr(settings, "still_hiring_prefer", True)):
        return annotated

    def _key(m: dict[str, Any]) -> tuple:
        status = m.get("still_hiring") or "unknown"
        score = -int(m.get("match_score", 0) or 0)
        posted = parse_posted_value(m.get("posted_at"))
        # Avoid datetime.min.timestamp() (breaks on Windows)
        posted_ord = posted.timestamp() if posted is not None else 0.0
        return (still_hiring_sort_key(status), score, -posted_ord)

    return sorted(annotated, key=_key)
