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

# How many tiers above the candidate's level are allowed (0 = exact band only).
_ALLOWED_ABOVE: dict[int, int] = {
    0: 1,  # fresher -> intern, entry, junior
    1: 1,  # 0-2 yrs -> up to mid
    2: 1,  # 2-4 yrs -> up to senior
    3: 1,  # 4-7 yrs -> up to lead
    4: 1,  # 7+ yrs -> up to executive
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

    if any(w in lowered for w in ("entry", "junior", "0-1", "0 - 1")):
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
        # Unknown duration — assume ~1 year per role
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


def infer_job_tier_from_text(title: str, description: str = "") -> int:
    """Infer job seniority tier from title and description text."""
    haystack = f"{title} {description}"
    lowered = haystack.lower()

    # Years-required signals override title ambiguity.
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

    # Title-based signals (check lead/staff before generic senior).
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
        title_tier = 2  # generic title — assume mid unless years say otherwise
    else:
        title_tier = 2

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
) -> bool:
    """Return True when the job tier is within the candidate's allowed band."""
    stretch = 1 if allow_stretch else 0
    max_allowed = candidate_tier + _ALLOWED_ABOVE.get(candidate_tier, 1) + stretch
    # Candidates should not be matched to jobs clearly below their level either,
    # except entry candidates who may still see intern roles.
    min_allowed = 0 if candidate_tier <= 1 else max(0, candidate_tier - 2)
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


def is_job_compatible_with_profile(
    job: JobListing,
    profile: UserProfile,
    *,
    allow_stretch: bool = False,
) -> bool:
    return is_compatible(
        infer_candidate_tier(profile),
        infer_job_tier(job),
        allow_stretch=allow_stretch,
    )
