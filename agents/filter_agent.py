"""Job Filtering Agent.

Removes duplicates and clearly irrelevant listings before the (more expensive)
semantic matching stage. Keeps the logic cheap: hash dedup, keyword relevance,
optional internship exclusion, location preference, and experience-level gating.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger
from models.schemas import JobListing, UserProfile
from services.seniority import (
    candidate_tier_label,
    infer_candidate_tier,
    is_job_compatible_with_profile,
    job_seniority_label,
)
from services.location import effective_location, location_filter_ok
from services.skills import has_unrelated_enterprise_stack, role_relevant

logger = get_logger(__name__)

_INTERNSHIP_TERMS = ("intern", "internship", "trainee")


@dataclass
class FilterResult:
    """Kept jobs plus compact exclusion counts for UI/history transparency."""

    jobs: list[JobListing]
    exclusions: dict[str, int] = field(default_factory=dict)

    @property
    def exclusion_summary(self) -> str:
        if not self.exclusions:
            return ""
        parts = [
            f"{reason.replace('_', ' ')}: {count}"
            for reason, count in sorted(self.exclusions.items())
            if count
        ]
        return "; ".join(parts)


class JobFilterAgent:
    def run(
        self,
        jobs: list[JobListing],
        profile: UserProfile,
        exclude_internships: bool = False,
        strict_experience: bool = True,
        allow_stretch: bool = False,
        flex_years: int | None = None,
    ) -> FilterResult:
        seen: set[str] = set()
        kept: list[JobListing] = []
        exclusions: dict[str, int] = {}
        candidate_tier = infer_candidate_tier(profile)

        def _drop(reason: str) -> None:
            exclusions[reason] = exclusions.get(reason, 0) + 1

        for job in jobs:
            if job.content_hash in seen:
                _drop("duplicate")
                continue
            seen.add(job.content_hash)

            if exclude_internships and self._is_internship(job):
                _drop("internship")
                continue

            if strict_experience and not self._experience_level_ok(
                job, profile, allow_stretch=allow_stretch, flex_years=flex_years
            ):
                _drop("experience_mismatch")
                continue

            if has_unrelated_enterprise_stack(job, profile):
                logger.info(f"Filter: dropped '{job.title}' — unrelated tech stack")
                _drop("enterprise_stack")
                continue

            if not role_relevant(job, profile):
                logger.info(f"Filter: dropped '{job.title}' — role/skill mismatch")
                _drop("role_mismatch")
                continue

            if not self._location_ok(job, profile):
                _drop("location_mismatch")
                continue

            kept.append(job)

        logger.info(
            f"Filter: {len(jobs)} -> {len(kept)} jobs "
            f"(candidate tier: {candidate_tier_label(candidate_tier)}; "
            f"exclusions={exclusions or '{}'})"
        )
        return FilterResult(jobs=kept, exclusions=exclusions)

    @staticmethod
    def _experience_level_ok(
        job: JobListing,
        profile: UserProfile,
        *,
        allow_stretch: bool = False,
        flex_years: int | None = None,
    ) -> bool:
        if is_job_compatible_with_profile(
            job, profile, allow_stretch=allow_stretch, flex_years=flex_years
        ):
            return True
        candidate_tier = infer_candidate_tier(profile)
        logger.info(
            f"Filter: dropped '{job.title}' — level mismatch "
            f"(candidate: {candidate_tier_label(candidate_tier)}, "
            f"job: {job_seniority_label(job)})"
        )
        return False

    @staticmethod
    def _is_internship(job: JobListing) -> bool:
        haystack = f"{job.title} {job.description[:200]}".lower()
        return any(term in haystack for term in _INTERNSHIP_TERMS)

    @staticmethod
    def _location_ok(job: JobListing, profile: UserProfile) -> bool:
        pref = effective_location(profile)
        return location_filter_ok(
            job, pref, include_remote=profile.include_remote
        )
