"""Semantic Matching Agent (FR-4).

Pipeline for max accuracy:
  1. Seniority pre-filter (hard gate)
  2. Bi-encoder retrieval + optional BM25 hybrid (recall)
  3. Cross-encoder rerank (precision)
  4. LLM scoring on top candidates only (explanations + tie-break)
"""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.base import call_ollama_json
from core.config import settings
from core.logging import get_logger
from models.schemas import (
    JobListing,
    MatchResult,
    Recommendation,
    UserProfile,
)
from prompts.templates import MATCHER_SYSTEM
from services.embeddings import normalize_rerank_scores, rerank_pairs
from services.hybrid_search import hybrid_similarity
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
)
from services.vector_store import index_jobs, rank_by_similarity
from services.threshold import effective_min_match_score, filter_match_results

logger = get_logger(__name__)

_RECENCY_BONUS_HOURS = 48
_RECENCY_BONUS_MAX = 5


def _recency_bonus(job: JobListing) -> int:
    posted = job.posted_at or job.scraped_at
    if posted is None:
        return 0
    age = datetime.utcnow() - posted
    if age <= timedelta(hours=_RECENCY_BONUS_HOURS):
        return _RECENCY_BONUS_MAX
    return 0


def _combine_score(
    *,
    embed_score: float,
    skill_score: float,
    rerank_score: float,
    llm_score: float,
    used_llm: bool,
) -> int:
    if used_llm:
        w_embed = settings.score_weight_embed
        w_skill = settings.score_weight_skill
        w_rerank = settings.score_weight_rerank
        w_llm = settings.score_weight_llm
    else:
        total = (
            settings.score_weight_embed
            + settings.score_weight_skill
            + settings.score_weight_rerank
        )
        w_embed = settings.score_weight_embed / total
        w_skill = settings.score_weight_skill / total
        w_rerank = settings.score_weight_rerank / total
        w_llm = 0.0

    combined = (
        w_embed * embed_score
        + w_skill * skill_score
        + w_rerank * rerank_score
        + w_llm * llm_score
    )
    return max(0, min(100, round(combined)))


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
        min_match_score: int | None = None,
    ) -> list[MatchResult]:
        if not jobs:
            return []

        candidate_tier = infer_candidate_tier(profile)
        eligible = jobs
        if strict_experience:
            eligible = [
                job
                for job in jobs
                if is_job_compatible_with_profile(
                    job,
                    profile,
                    allow_stretch=allow_stretch,
                    flex_years=flex_years,
                )
                and not has_unrelated_enterprise_stack(job, profile)
            ]
            logger.info(
                f"Matcher: {len(jobs)} -> {len(eligible)} jobs after seniority pre-filter"
            )

        if not eligible:
            return []

        index_jobs(eligible)
        query_text = profile.embedding_query_text()
        vector_scores = rank_by_similarity(
            query_text, [j.content_hash for j in eligible]
        )
        recall_scores = hybrid_similarity(query_text, eligible, vector_scores)

        ranked_recall = sorted(
            eligible,
            key=lambda j: (
                recall_scores.get(j.content_hash, 0.0),
                j.posted_at or j.scraped_at or datetime.min,
            ),
            reverse=True,
        )
        recall_pool = ranked_recall[: settings.matcher_recall_top_n]
        rerank_pool = recall_pool[: settings.matcher_rerank_top_n]

        rerank_raw = rerank_pairs(
            profile.embedding_query_text(),
            [j.embedding_passage_text() for j in rerank_pool],
        )
        rerank_norm = normalize_rerank_scores(rerank_raw)
        rerank_map = {
            job.content_hash: rerank_norm[i] * 100
            for i, job in enumerate(rerank_pool)
        }

        reranked = sorted(
            rerank_pool,
            key=lambda j: (
                rerank_map.get(j.content_hash, 0.0),
                recall_scores.get(j.content_hash, 0.0),
            ),
            reverse=True,
        )
        llm_hashes = {
            j.content_hash
            for j in reranked[: settings.matcher_llm_top_n]
        }

        results: list[MatchResult] = []
        score_pool = reranked[: max(top_n * 2, top_n)]

        for job in score_pool:
            embed_score = recall_scores.get(job.content_hash, 0.0) * 100
            skill_score = float(deterministic_skill_overlap(profile, job))
            rerank_score = rerank_map.get(job.content_hash, embed_score)
            used_llm = job.content_hash in llm_hashes
            match = self._score_job(
                profile,
                job,
                embed_score=embed_score,
                skill_score=skill_score,
                rerank_score=rerank_score,
                candidate_tier=candidate_tier,
                allow_stretch=allow_stretch,
                flex_years=flex_years,
                use_llm=used_llm,
            )
            if strict_experience and match.recommendation == Recommendation.SKIP:
                continue
            results.append(match)

        results.sort(
            key=lambda m: (
                m.match_score,
                m.job.posted_at or m.job.scraped_at or datetime.min,
            ),
            reverse=True,
        )
        threshold = effective_min_match_score(profile, min_match_score)
        kept, dropped = filter_match_results(results, threshold)
        if dropped:
            logger.info(
                f"Matcher: dropped {dropped} job(s) below min_match_score={threshold}"
            )
        return kept[:top_n]

    def _score_job(
        self,
        profile: UserProfile,
        job: JobListing,
        *,
        embed_score: float,
        skill_score: float,
        rerank_score: float,
        candidate_tier: int,
        allow_stretch: bool = False,
        flex_years: int | None = None,
        use_llm: bool = True,
    ) -> MatchResult:
        detail = compatibility_detail(
            job, profile, allow_stretch=allow_stretch, flex_years=flex_years
        )
        level_ok = detail["compatible"]
        llm_score = rerank_score
        matched: list[str] = []
        missing: list[str] = []
        reasons: list[str] = []
        recommendation = Recommendation.CONSIDER

        if use_llm:
            try:
                data = call_ollama_json(MATCHER_SYSTEM, self._user_prompt(profile, job))
                llm_score = float(data.get("match_score", rerank_score))
                matched = filter_matched_skills(
                    profile, data.get("matched_skills", []) or []
                )
                missing = data.get("missing_skills", []) or []
                reasons = data.get("reasons", []) or []
                recommendation = self._to_recommendation(data.get("recommendation", ""))
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LLM match failed for '{job.title}': {exc}")
                llm_score = rerank_score
                reasons = ["Scored with reranker and skill overlap (LLM unavailable)."]
        else:
            reasons = ["Ranked by cross-encoder reranker and skill overlap."]

        combined = _combine_score(
            embed_score=embed_score,
            skill_score=skill_score,
            rerank_score=rerank_score,
            llm_score=llm_score,
            used_llm=use_llm,
        )
        combined += _recency_bonus(job)
        combined = max(0, min(100, combined))

        if skill_score < 15 and not matched:
            combined = min(combined, 35)
            recommendation = Recommendation.SKIP
            reasons = list(reasons) + [
                "Low skill overlap with your profile — role may be unrelated."
            ]

        if not level_ok:
            combined = min(combined, 20)
            recommendation = Recommendation.SKIP
            reasons = list(reasons) + [
                (
                    f"Experience mismatch: you are {detail['candidate_label']} "
                    f"(target {detail['target_years']} yrs) but this job is "
                    f"{detail['job_label']} "
                    f"({detail['job_required_years']}+ yrs required)."
                )
            ]

        return MatchResult(
            job=job,
            match_score=combined,
            embed_score=round(embed_score, 1),
            skill_score=round(skill_score, 1),
            rerank_score=round(rerank_score, 1),
            llm_score=round(llm_score, 1),
            seniority_compatible=level_ok,
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
