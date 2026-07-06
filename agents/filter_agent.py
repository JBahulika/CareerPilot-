"""Job Filtering Agent.

Removes duplicates and clearly irrelevant listings before the (more expensive)
semantic matching stage. Keeps the logic cheap: hash dedup, keyword relevance,
optional internship exclusion, location preference, and experience-level gating.
"""

from __future__ import annotations

from core.logging import get_logger
from models.schemas import JobListing, UserProfile
from services.seniority import (
    candidate_tier_label,
    infer_candidate_tier,
    infer_job_tier,
    is_compatible,
    job_seniority_label,
)

logger = get_logger(__name__)

_INTERNSHIP_TERMS = ("intern", "internship", "trainee")


class JobFilterAgent:
    def run(
        self,
        jobs: list[JobListing],
        profile: UserProfile,
        exclude_internships: bool = False,
        strict_experience: bool = True,
        allow_stretch: bool = False,
    ) -> list[JobListing]:
        seen: set[str] = set()
        kept: list[JobListing] = []
        candidate_tier = infer_candidate_tier(profile)

        profile_terms = self._profile_terms(profile)

        for job in jobs:
            if job.content_hash in seen:
                continue
            seen.add(job.content_hash)

            if exclude_internships and self._is_internship(job):
                continue

            if strict_experience and not self._experience_level_ok(
                job, candidate_tier, allow_stretch=allow_stretch
            ):
                continue

            if profile_terms and not self._is_relevant(job, profile_terms):
                continue

            if not self._location_ok(job, profile):
                continue

            kept.append(job)

        logger.info(
            f"Filter: {len(jobs)} -> {len(kept)} jobs "
            f"(candidate tier: {candidate_tier_label(candidate_tier)})"
        )
        return kept

    @staticmethod
    def _experience_level_ok(
        job: JobListing,
        candidate_tier: int,
        *,
        allow_stretch: bool = False,
    ) -> bool:
        job_tier = infer_job_tier(job)
        if is_compatible(candidate_tier, job_tier, allow_stretch=allow_stretch):
            return True
        logger.info(
            f"Filter: dropped '{job.title}' — level mismatch "
            f"(candidate: {candidate_tier_label(candidate_tier)}, "
            f"job: {job_seniority_label(job)})"
        )
        return False

    @staticmethod
    def _profile_terms(profile: UserProfile) -> set[str]:
        terms = set()
        for value in (*profile.skills, *profile.preferred_roles, profile.role):
            for word in value.lower().split():
                if len(word) > 2:
                    terms.add(word)
        return terms

    @staticmethod
    def _is_internship(job: JobListing) -> bool:
        haystack = f"{job.title} {job.description[:200]}".lower()
        return any(term in haystack for term in _INTERNSHIP_TERMS)

    @staticmethod
    def _is_relevant(job: JobListing, profile_terms: set[str]) -> bool:
        haystack = f"{job.title} {' '.join(job.skills)} {job.description}".lower()
        return any(term in haystack for term in profile_terms)

    @staticmethod
    def _location_ok(job: JobListing, profile: UserProfile) -> bool:
        pref = (profile.preferred_location or "").strip().lower()
        if not pref:
            return True
        location = job.location.lower()
        # Remote roles always pass; otherwise require a location overlap.
        if "remote" in location or "anywhere" in location:
            return True
        return pref in location or location in pref
