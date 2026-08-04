"""Match-score threshold helpers (Phase 1).

User-settable minimum match score (0–100). Profile default can be overridden
per pipeline run without permanently changing the saved profile.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from core.config import settings
from models.schemas import MatchResult, UserProfile


def clamp_match_score(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def effective_min_match_score(
    profile: UserProfile | None = None,
    override: Optional[int] = None,
) -> int:
    """Resolve threshold: per-run override > profile > settings default."""
    if override is not None:
        return clamp_match_score(override)
    if profile is not None and getattr(profile, "min_match_score", None) is not None:
        return clamp_match_score(profile.min_match_score)
    return clamp_match_score(settings.min_match_score)


def filter_match_results(
    matches: Sequence[MatchResult],
    min_score: int,
) -> tuple[list[MatchResult], int]:
    """Keep MatchResult items at/above threshold. Returns (kept, dropped_count)."""
    threshold = clamp_match_score(min_score)
    kept = [m for m in matches if m.match_score >= threshold]
    return kept, len(matches) - len(kept)


def filter_digest_matches(
    matches: Sequence[Mapping[str, Any]],
    min_score: int,
) -> tuple[list[dict[str, Any]], int]:
    """Keep digest dicts at/above threshold. Returns (kept, dropped_count)."""
    threshold = clamp_match_score(min_score)
    kept = [dict(m) for m in matches if int(m.get("match_score", 0) or 0) >= threshold]
    return kept, len(matches) - len(kept)
