"""Semantic Matching Agent (FR-4).

Combines embedding similarity (ChromaDB) with LLM reasoning to produce an
explainable match score, matched/missing skills, and a recommendation. The
final score blends both signals: 60% embedding, 40% LLM. Jobs that exceed the
candidate's experience band are excluded or heavily penalized.
"""

from __future__ import annotations

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
    infer_candidate_tier,
    infer_job_tier,
    is_compatible,
    job_seniority_label,
)
from services.vector_store import index_jobs, rank_by_similarity

logger = get_logger(__name__)

_EMBED_WEIGHT = 0.6
_LLM_WEIGHT = 0.4
_LEVEL_MISMATCH_CAP = 25


class SemanticMatcherAgent:
    def run(
        self,
        profile: UserProfile,
        jobs: list[JobListing],
        top_n: int = 5,
        *,
        strict_experience: bool = True,
        allow_stretch: bool = False,
    ) -> list[MatchResult]:
        if not jobs:
            return []

        candidate_tier = infer_candidate_tier(profile)
        eligible = jobs
        if strict_experience:
            eligible = [
                job
                for job in jobs
                if is_compatible(
                    candidate_tier,
                    infer_job_tier(job),
                    allow_stretch=allow_stretch,
                )
            ]
            logger.info(
                f"Matcher: {len(jobs)} -> {len(eligible)} jobs after seniority pre-filter"
            )

        if not eligible:
            return []

        index_jobs(eligible)
        similarity = rank_by_similarity(
            profile.summary_text(), [j.content_hash for j in eligible]
        )

        ranked = sorted(
            eligible, key=lambda j: similarity.get(j.content_hash, 0.0), reverse=True
        )
        shortlist = ranked[: max(top_n * 2, top_n)]

        results: list[MatchResult] = []
        for job in shortlist:
            embed_score = similarity.get(job.content_hash, 0.0) * 100
            match = self._score_job(
                profile,
                job,
                embed_score,
                candidate_tier=candidate_tier,
                allow_stretch=allow_stretch,
            )
            results.append(match)

        results.sort(key=lambda m: m.match_score, reverse=True)
        return results[:top_n]

    def _score_job(
        self,
        profile: UserProfile,
        job: JobListing,
        embed_score: float,
        *,
        candidate_tier: int,
        allow_stretch: bool = False,
    ) -> MatchResult:
        job_tier = infer_job_tier(job)
        level_ok = is_compatible(
            candidate_tier, job_tier, allow_stretch=allow_stretch
        )

        try:
            data = call_ollama_json(MATCHER_SYSTEM, self._user_prompt(profile, job))
            llm_score = float(data.get("match_score", 0))
            matched = data.get("matched_skills", []) or []
            missing = data.get("missing_skills", []) or []
            reasons = data.get("reasons", []) or []
            recommendation = self._to_recommendation(data.get("recommendation", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM match failed for '{job.title}': {exc}")
            llm_score = embed_score
            matched, missing, reasons = [], [], ["Scored on skill similarity only."]
            recommendation = Recommendation.CONSIDER

        combined = round(_EMBED_WEIGHT * embed_score + _LLM_WEIGHT * llm_score)
        combined = max(0, min(100, combined))

        if not level_ok:
            combined = min(combined, _LEVEL_MISMATCH_CAP)
            recommendation = Recommendation.SKIP
            reasons = list(reasons) + [
                (
                    f"Experience mismatch: candidate is "
                    f"{candidate_tier_label(candidate_tier)} but job is "
                    f"{job_seniority_label(job)}."
                )
            ]

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
            f"{job.match_text()[:6000]}"
        )

    @staticmethod
    def _to_recommendation(value: str) -> Recommendation:
        normalized = (value or "").strip().lower()
        if "highly" in normalized:
            return Recommendation.HIGHLY_RECOMMENDED
        if "skip" in normalized:
            return Recommendation.SKIP
        return Recommendation.CONSIDER
