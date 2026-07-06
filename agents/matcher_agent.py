"""Semantic Matching Agent (FR-4).

Combines embedding similarity (ChromaDB) with LLM reasoning to produce an
explainable match score, matched/missing skills, and a recommendation. The
final score blends both signals: 60% embedding, 40% LLM.
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
from services.vector_store import index_jobs, rank_by_similarity

logger = get_logger(__name__)

_EMBED_WEIGHT = 0.6
_LLM_WEIGHT = 0.4


class SemanticMatcherAgent:
    def run(
        self,
        profile: UserProfile,
        jobs: list[JobListing],
        top_n: int = 5,
    ) -> list[MatchResult]:
        if not jobs:
            return []

        index_jobs(jobs)
        similarity = rank_by_similarity(
            profile.summary_text(), [j.content_hash for j in jobs]
        )

        # Rank by embedding similarity first, then run the LLM only on the best
        # candidates to keep the pipeline fast.
        ranked = sorted(
            jobs, key=lambda j: similarity.get(j.content_hash, 0.0), reverse=True
        )
        shortlist = ranked[: max(top_n * 2, top_n)]

        results: list[MatchResult] = []
        for job in shortlist:
            embed_score = similarity.get(job.content_hash, 0.0) * 100
            match = self._score_job(profile, job, embed_score)
            results.append(match)

        results.sort(key=lambda m: m.match_score, reverse=True)
        return results[:top_n]

    def _score_job(
        self, profile: UserProfile, job: JobListing, embed_score: float
    ) -> MatchResult:
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
