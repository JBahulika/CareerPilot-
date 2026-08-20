"""Digest preparation: threshold, location eligibility, score sort, and caps.

CareerPilot discovers and notifies; the user chooses applications manually.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from core.config import settings
from models.schemas import UserProfile
from services.location import effective_location, location_filter_ok
from services.threshold import clamp_match_score, effective_min_match_score, filter_digest_matches


def short_reason(match: Mapping[str, Any], *, max_len: int = 160) -> str:
    """One-line reason for digest cards (first LLM reason or recommendation)."""
    reasons = match.get("reasons") or []
    if isinstance(reasons, list) and reasons:
        text = str(reasons[0]).strip()
        if text:
            return text if len(text) <= max_len else text[: max_len - 1] + "…"
    rec = match.get("recommendation")
    if rec:
        return str(rec).strip()
    return ""


def location_eligible(match: Mapping[str, Any], profile: UserProfile) -> bool:
    """Re-check location prefs so digests never include location mismatches."""
    pref = effective_location(profile)
    job = SimpleNamespace(location=match.get("location") or "")
    return location_filter_ok(
        job, pref, include_remote=bool(profile.include_remote)
    )


def prepare_digest_matches(
    profile: UserProfile,
    matches: Sequence[Mapping[str, Any]],
    *,
    max_jobs: int | None = None,
    min_score: int | None = None,
    profile_id: int | None = None,
    skip_dedupe: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter, sort, and cap matches for a human-in-the-loop digest.

    Returns ``(prepared_matches, stats)`` where stats counts drops by reason.
    Phase 8: also drops already-notified jobs unless refreshed / score jump.
    """
    threshold = (
        clamp_match_score(min_score)
        if min_score is not None
        else effective_min_match_score(profile)
    )
    cap = max_jobs if max_jobs is not None else int(settings.max_digest_jobs)
    cap = max(0, int(cap))

    after_score, dropped_score = filter_digest_matches(matches, threshold)
    location_kept: list[dict[str, Any]] = []
    dropped_location = 0
    for m in after_score:
        if location_eligible(m, profile):
            location_kept.append(m)
        else:
            dropped_location += 1

    location_kept.sort(
        key=lambda m: int(m.get("match_score", 0) or 0),
        reverse=True,
    )

    dropped_already = 0
    if not skip_dedupe:
        from services.notified import filter_already_notified

        location_kept, dropped_already = filter_already_notified(
            location_kept, profile_id=profile_id
        )

    # Phase 10a — prefer likely still-hiring (never invent; unknown sorts last)
    from services.still_hiring import prefer_still_hiring

    location_kept = prefer_still_hiring(location_kept)

    truncated = max(0, len(location_kept) - cap) if cap else len(location_kept)
    prepared = location_kept[:cap] if cap else []

    stats = {
        "input": len(matches),
        "dropped_below_threshold": dropped_score,
        "dropped_location": dropped_location,
        "dropped_already_notified": dropped_already,
        "truncated": truncated,
        "sent": len(prepared),
        "min_match_score": threshold,
        "max_digest_jobs": cap,
    }
    return prepared, stats
