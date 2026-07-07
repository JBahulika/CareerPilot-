"""Experience-level / seniority inference and compatibility rules.

Deterministic, testable rules engine used by the filter agent, scraper, and
matcher to keep entry-level candidates from receiving senior roles.
"""

from __future__ import annotations

import re
from typing import Union

from models.schemas import JobListing, UserProfile

# Tier scale: 0=intern/fresher, 1=junior, 2=mid, 3=senior, 4=lead/staff, 5=executive
TIER_LABELS = {
    0: "Intern / Fresher",
    1: "Junior / Entry",
    2: "Mid-level",
    3: "Senior",
    4: "Lead / Staff",
    5: "Executive",
}

# Tight bands for entry candidates — tier 0 may only reach junior (+1).
_ALLOWED_ABOVE: dict[int, int] = {
    0: 1,
    1: 1,
    2: 2,
    3: 2,
    4: 2,
}
_ALLOWED_BELOW: dict[int, int] = {
    0: 0,
    1: 1,
    2: 1,
    3: 2,
    4: 2,
}

_SENIOR_TITLE_PATTERNS = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\barchitect\b",
]

_ENTRY_TITLE_PATTERNS = [
    r"\bintern\b",
    r"\binternship\b",
    r"\btrainee\b",
    r"\bjunior\b",
    r"\bjr\.?\b",
    r"\bentry[\s-]?level\b",
    r"\bassociate\b",
    r"\bgraduate\b",
    r"\bnew grad\b",
    r"\bfresher\b",
    r"\bentry\b",
]

_YEARS_REQUIRED_RE = re.compile(
    r"(?:minimum|min\.?|at least|requires?)\s*(\d+)\+?\s*years?",
    re.IGNORECASE,
)
_YEARS_EXPERIENCE_RE = re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE)
_EXPERIENCE_LEVEL_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*years?", re.IGNORECASE)


def default_target_years(profile: UserProfile) -> tuple[int, int]:
    """Map experience_level to a sensible default year range when unset."""
    level = (profile.experience_level or "").strip().lower()
    if level in ("fresher", "fresh graduate", "new grad", "student"):
        return 0, 0
    if "intern" in level:
        return 0, 0
    if "0-1" in level or "0 - 1" in level:
        return 0, 1
    if "1-3" in level:
        return 1, 3
    if "3-5" in level:
        return 3, 5
    if "5+" in level or level.startswith("5"):
        return 5, 15
    tier = _parse_years_from_level(profile.experience_level)
    if tier == 0:
        return 0, 1
    if tier == 1:
        return 0, 2
    if tier == 2:
        return 2, 5
    if tier == 3:
        return 4, 8
    return 5, 15


def effective_target_years(profile: UserProfile) -> tuple[int, int]:
    if profile.target_years_min is not None and profile.target_years_max is not None:
        return profile.target_years_min, profile.target_years_max
    return default_target_years(profile)


def _text_has_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(re.search(p, lowered) for p in patterns)


def _parse_years_from_level(level: str) -> int | None:
    """Map a free-text experience_level string to a tier."""
    if not level:
        return None
    lowered = level.strip().lower()

    if any(w in lowered for w in ("fresher", "fresh graduate", "new grad", "student")):
        return 0
    if "intern" in lowered:
        return 0

    range_match = _EXPERIENCE_LEVEL_RE.search(lowered)
    if range_match:
        low = int(range_match.group(1))
        if low <= 1:
            return 0
        if low <= 3:
            return 1
        if low <= 5:
            return 2
        if low <= 7:
            return 3
        return 4

    digits = re.findall(r"\d+", lowered)
    if digits:
        years = int(digits[0])
        if years <= 1:
            return 0
        if years <= 2:
            return 1
        if years <= 4:
            return 2
        if years <= 7:
            return 3
        return 4

    if any(w in lowered for w in ("0-1", "0 - 1")):
        return 0
    if any(w in lowered for w in ("entry", "junior")):
        return 1
    if any(w in lowered for w in ("mid", "intermediate", "1-3", "2-4")):
        return 2
    if "senior" in lowered and "lead" not in lowered:
        return 3
    if any(w in lowered for w in ("lead", "staff", "principal")):
        return 4
    if any(w in lowered for w in ("executive", "director", "vp")):
        return 5

    return None


def _years_from_work_history(profile: UserProfile) -> int | None:
    """Estimate tier from listed work experience count and duration hints."""
    if not profile.experience:
        return 0 if profile.education else None

    total_months = 0
    for exp in profile.experience:
        duration = (exp.duration or "").lower()
        year_matches = re.findall(r"(20\d{2})", duration)
        if len(year_matches) >= 2:
            total_months += (int(year_matches[-1]) - int(year_matches[0])) * 12
            continue
        month_match = re.search(r"(\d+)\s*months?", duration)
        if month_match:
            total_months += int(month_match.group(1))
            continue
        year_match = re.search(r"(\d+)\s*years?", duration)
        if year_match:
            total_months += int(year_match.group(1)) * 12
            continue
        total_months += 12

    years = total_months / 12
    if years <= 1:
        return 0
    if years <= 2:
        return 1
    if years <= 4:
        return 2
    if years <= 7:
        return 3
    return 4


def _tier_to_years(tier: int) -> float:
    return {0: 0.0, 1: 1.0, 2: 3.0, 3: 5.0, 4: 8.0, 5: 12.0}.get(tier, 3.0)


def infer_candidate_years(profile: UserProfile) -> float:
    """Estimate candidate years of experience as a float."""
    min_y, max_y = effective_target_years(profile)
    return (min_y + max_y) / 2


def infer_candidate_tier(profile: UserProfile) -> int:
    """Return candidate seniority tier (0-5)."""
    from_level = _parse_years_from_level(profile.experience_level)
    from_history = _years_from_work_history(profile)

    if from_level is not None and from_history is not None:
        return min(from_level, from_history)
    if from_level is not None:
        return from_level
    if from_history is not None:
        return from_history
    return 0


def infer_job_required_years(job: JobListing) -> int | None:
    """Extract minimum years of experience required from a job listing."""
    haystack = f"{job.title} {job.description}"
    max_years = 0
    found = False
    for pattern in (_YEARS_REQUIRED_RE, _YEARS_EXPERIENCE_RE):
        for match in pattern.finditer(haystack):
            max_years = max(max_years, int(match.group(1)))
            found = True
    if found:
        return max_years
    tier = infer_job_tier(job)
    return int(_tier_to_years(tier))


def is_years_compatible(
    profile: UserProfile,
    job: JobListing,
    *,
    flex_years: int = 1,
    allow_stretch: bool = False,
) -> bool:
    """Flexible year-range check using profile target range or inferred years."""
    job_years = infer_job_required_years(job)
    if job_years is None:
        return True

    flex = flex_years + (1 if allow_stretch else 0)
    min_y, max_y = effective_target_years(profile)
    min_allowed = max(0, min_y - flex)
    max_allowed = max_y + flex
    return min_allowed <= job_years <= max_allowed


def infer_job_tier_from_text(title: str, description: str = "") -> int:
    """Infer job seniority tier from title and description text."""
    haystack = f"{title} {description}"
    lowered = haystack.lower()

    max_required_years = 0
    for pattern in (_YEARS_REQUIRED_RE, _YEARS_EXPERIENCE_RE):
        for match in pattern.finditer(haystack):
            max_required_years = max(max_required_years, int(match.group(1)))

    if max_required_years >= 10:
        tier_from_years = 4
    elif max_required_years >= 7:
        tier_from_years = 3
    elif max_required_years >= 5:
        tier_from_years = 3
    elif max_required_years >= 3:
        tier_from_years = 2
    elif max_required_years >= 1:
        tier_from_years = 1
    else:
        tier_from_years = None

    if _text_has_any(lowered, [r"\bexecutive\b", r"\bvp\b", r"\bvice president\b"]):
        title_tier = 5
    elif _text_has_any(
        lowered,
        [
            r"\bprincipal\b",
            r"\bstaff\b",
            r"\btech lead\b",
            r"\bdirector\b",
            r"\bhead of\b",
            r"\blead\b",
        ],
    ):
        title_tier = 4
    elif _text_has_any(lowered, _SENIOR_TITLE_PATTERNS):
        title_tier = 3
    elif _text_has_any(lowered, _ENTRY_TITLE_PATTERNS):
        title_tier = 1 if "intern" not in lowered else 0
    elif re.search(r"\bengineer\b|\bdeveloper\b|\banalyst\b", lowered):
        title_tier = 1
    else:
        title_tier = 1

    if tier_from_years is not None:
        return max(title_tier, tier_from_years)
    return title_tier


def infer_job_tier(job: Union[JobListing, str], description: str = "") -> int:
    if isinstance(job, JobListing):
        return infer_job_tier_from_text(job.title, job.description)
    return infer_job_tier_from_text(job, description)


def is_compatible(
    candidate_tier: int,
    job_tier: int,
    *,
    allow_stretch: bool = False,
    flex_tiers: int = 0,
) -> bool:
    """Return True when the job tier is within the candidate's allowed band."""
    stretch = 1 if allow_stretch else 0
    extra = flex_tiers + stretch
    max_allowed = candidate_tier + _ALLOWED_ABOVE.get(candidate_tier, 1) + extra
    below = _ALLOWED_BELOW.get(candidate_tier, 1)
    min_allowed = 0 if candidate_tier <= 1 else max(0, candidate_tier - below - extra)
    return min_allowed <= job_tier <= max_allowed


def candidate_tier_label(tier: int) -> str:
    return TIER_LABELS.get(tier, "Unknown")


def job_seniority_label(job: Union[JobListing, str], description: str = "") -> str:
    tier = infer_job_tier(job, description) if isinstance(job, str) else infer_job_tier(job)
    return TIER_LABELS.get(tier, "Unknown")


def experience_label_for_job(job: JobListing) -> str:
    """Human-readable experience requirement for storage and UI."""
    tier = infer_job_tier(job)
    label = TIER_LABELS.get(tier, "Unknown")
    haystack = f"{job.title} {job.description}"
    years_match = _YEARS_EXPERIENCE_RE.search(haystack) or _YEARS_REQUIRED_RE.search(haystack)
    if years_match:
        return f"{label} ({years_match.group(1)}+ yrs)"
    return label


def compatibility_detail(
    job: JobListing,
    profile: UserProfile,
    *,
    allow_stretch: bool = False,
    flex_years: int | None = None,
) -> dict:
    from core.config import settings

    flex = flex_years if flex_years is not None else settings.experience_flex_years
    cand_tier = infer_candidate_tier(profile)
    job_tier = infer_job_tier(job)
    tier_ok = is_compatible(cand_tier, job_tier, allow_stretch=allow_stretch)
    years_ok = is_years_compatible(
        profile, job, flex_years=flex, allow_stretch=allow_stretch
    )
    min_y, max_y = effective_target_years(profile)
    return {
        "candidate_tier": cand_tier,
        "candidate_label": candidate_tier_label(cand_tier),
        "job_tier": job_tier,
        "job_label": job_seniority_label(job),
        "tier_ok": tier_ok,
        "years_ok": years_ok,
        "target_years": f"{min_y}-{max_y}",
        "job_required_years": infer_job_required_years(job),
        "compatible": tier_ok and years_ok,
    }


def is_job_compatible_with_profile(
    job: JobListing,
    profile: UserProfile,
    *,
    allow_stretch: bool = False,
    flex_years: int | None = None,
) -> bool:
    from core.config import settings

    flex = flex_years if flex_years is not None else settings.experience_flex_years
    detail = compatibility_detail(
        job, profile, allow_stretch=allow_stretch, flex_years=flex
    )
    return detail["compatible"]
