"""Semantic Matching Agent (FR-4).

Combines embedding similarity (ChromaDB) with LLM reasoning to produce an
explainable match score, matched/missing skills, and a recommendation. The
final score blends embedding, deterministic skill overlap, and LLM signals.
Jobs outside the candidate's experience band are excluded when strict mode is on.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.base import call_ollama_json
from core.logging import get_logger
from models.schemas import (
    JobListing,
    MatchResult,
    Recommendation,
    UserProfile,
)
from prompts.templates import MATCHER_SYSTEM
from services.seniority import (
    candidate_tier_label,
    compatibility_detail,
    infer_candidate_tier,
    is_job_compatible_with_profile,
    job_seniority_label,
)
from services.skills import (
    deterministic_skill_overlap,
    filter_matched_skills,
    has_unrelated_enterprise_stack,
    is_relevant_job_posting,
)
from services.vector_store import index_jobs, rank_by_similarity

logger = get_logger(__name__)

_EMBED_WEIGHT = 0.45
_SKILL_WEIGHT = 0.25
_LLM_WEIGHT = 0.30
_RECENCY_BONUS_HOURS = 48
_RECENCY_BONUS_MAX = 5


def _recency_bonus(job: JobListing) -> int:
    """Small score boost for jobs posted within the last 48 hours."""
    posted = job.posted_at or job.scraped_at
    if posted is None:
        return 0
    age = datetime.utcnow() - posted
    if age <= timedelta(hours=_RECENCY_BONUS_HOURS):
        return _RECENCY_BONUS_MAX
    return 0


class SemanticMatcherAgent:
    def run(
        self,
        profile: UserProfile,
        jobs: list[JobListing],
        top_n: int = 5,
        *,
        strict_experience: bool = True,
        allow_stretch: bool = False,
        flex_years: int | None = None,
    ) -> list[MatchResult]:
        if not jobs:
            return []

        candidate_tier = infer_candidate_tier(profile)

        relevant = [
            job
            for job in jobs
            if is_relevant_job_posting(job, profile)
            and not has_unrelated_enterprise_stack(job, profile)
        ]

        # Progressive relaxation: never leave the user with an empty page.
        # 1) strict (relevance + experience band) -> 2) relevance only ->
        # 3) any scraped job. Relaxed pools are ranked and clearly labelled.
        relaxed = False
        pool = relevant
        if strict_experience:
            strict_pool = [
                job
                for job in relevant
                if is_job_compatible_with_profile(
                    job,
                    profile,
                    allow_stretch=allow_stretch,
                    flex_years=flex_years,
                )
            ]
            if strict_pool:
                pool = strict_pool
            elif relevant:
                pool = relevant
                relaxed = True
                logger.info(
                    "Matcher: no jobs inside experience band — relaxing seniority "
                    "to surface the closest roles"
                )

        if not pool:
            pool = jobs
            relaxed = True
            logger.info(
                "Matcher: no domain-relevant jobs — falling back to all scraped jobs"
            )

        logger.info(
            f"Matcher: {len(jobs)} -> {len(pool)} candidate jobs (relaxed={relaxed})"
        )

        index_jobs(pool)
        similarity = rank_by_similarity(
            profile.summary_text(), [j.content_hash for j in pool]
        )

        ranked = sorted(
            pool,
            key=lambda j: (
                similarity.get(j.content_hash, 0.0),
                j.relevance_score,
                (j.posted_at or j.scraped_at or datetime.min),
            ),
            reverse=True,
        )
        shortlist = ranked[: max(top_n * 2, top_n)]

        results: list[MatchResult] = []
        for job in shortlist:
            embed_score = similarity.get(job.content_hash, 0.0) * 100
            skill_score = deterministic_skill_overlap(profile, job)
            match = self._score_job(
                profile,
                job,
                embed_score,
                skill_score,
                candidate_tier=candidate_tier,
                allow_stretch=allow_stretch,
                flex_years=flex_years,
                relaxed=relaxed,
            )
            results.append(match)

        def _rank_key(m: MatchResult):
            return (m.match_score, m.job.posted_at or m.job.scraped_at or datetime.min)

        quality = [
            m
            for m in results
            if m.recommendation != Recommendation.SKIP and m.match_score >= 35
        ]
        if quality:
            quality.sort(key=_rank_key, reverse=True)
            return quality[:top_n]

        # Best-effort: surface the closest jobs rather than returning nothing.
        results.sort(key=_rank_key, reverse=True)
        return results[:top_n]

    def _score_job(
        self,
        profile: UserProfile,
        job: JobListing,
        embed_score: float,
        skill_score: float,
        *,
        candidate_tier: int,
        allow_stretch: bool = False,
        flex_years: int | None = None,
        relaxed: bool = False,
    ) -> MatchResult:
        detail = compatibility_detail(
            job, profile, allow_stretch=allow_stretch, flex_years=flex_years
        )
        level_ok = detail["compatible"]

        try:
            data = call_ollama_json(MATCHER_SYSTEM, self._user_prompt(profile, job))
            llm_score = float(data.get("match_score", 0))
            matched = filter_matched_skills(
                profile, data.get("matched_skills", []) or []
            )
            missing = data.get("missing_skills", []) or []
            reasons = data.get("reasons", []) or []
            recommendation = self._to_recommendation(data.get("recommendation", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM match failed for '{job.title}': {exc}")
            llm_score = max(embed_score, skill_score)
            matched, missing, reasons = [], [], ["Scored on skill similarity only."]
            recommendation = Recommendation.CONSIDER

        combined = round(
            _EMBED_WEIGHT * embed_score
            + _SKILL_WEIGHT * skill_score
            + _LLM_WEIGHT * llm_score
        )
        combined += _recency_bonus(job)
        combined = max(0, min(100, combined))

        if skill_score < 15 and not matched:
            if relaxed:
                combined = max(0, combined - 15)
                reasons = list(reasons) + [
                    "Limited skill overlap — shown because no closer roles were found."
                ]
            else:
                combined = min(combined, 35)
                recommendation = Recommendation.SKIP
                reasons = list(reasons) + [
                    "Low skill overlap with your profile — role may be unrelated."
                ]

        if not level_ok:
            mismatch_reason = (
                f"Experience mismatch: you are {detail['candidate_label']} "
                f"(target {detail['target_years']} yrs) but this job is "
                f"{detail['job_label']} "
                f"({detail['job_required_years']}+ yrs required)."
            )
            if relaxed:
                # Keep the job visible as a stretch/reach rather than hiding it.
                combined = max(0, combined - 20)
                reasons = list(reasons) + [
                    "Stretch role (asks for more experience than your target): "
                    + mismatch_reason
                ]
            else:
                combined = min(combined, 20)
                recommendation = Recommendation.SKIP
                reasons = list(reasons) + [mismatch_reason]

        # In relaxed mode we never hard-skip: these are the closest available jobs.
        if relaxed and recommendation == Recommendation.SKIP:
            recommendation = Recommendation.CONSIDER

        return MatchResult(
            job=job,
            match_score=combined,
            matched_skills=matched,
            missing_skills=missing,
            reasons=reasons,
            recommendation=recommendation,
        )

    @staticmethod
    def _user_prompt(profile: UserProfile, job: JobListing) -> str:
        return (
            "CANDIDATE PROFILE:\n"
            f"{profile.summary_text()}\n\n"
            "JOB:\n"
            f"{job.match_text()[:6000]}\n\n"
            "Only list matched_skills that appear verbatim or as clear synonyms "
            "in the candidate skills list. Never invent skills the candidate lacks."
        )

    @staticmethod
    def _to_recommendation(value: str) -> Recommendation:
        normalized = (value or "").strip().lower()
        if "highly" in normalized:
            return Recommendation.HIGHLY_RECOMMENDED
        if "skip" in normalized:
            return Recommendation.SKIP
        return Recommendation.CONSIDER
