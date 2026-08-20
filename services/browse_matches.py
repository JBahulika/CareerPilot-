"""Deterministic low-match browse rows for scrapes that filters/matcher skip.

Keeps Results useful when boards return a few jobs that fail location/role/
experience gates — user can still inspect them via “Show low matches”.
Digests ignore these because scores stay below the run threshold.
"""

from __future__ import annotations

from agents.job_sources.common import early_relevance_score
from models.schemas import JobListing, MatchResult, Recommendation, UserProfile
from services.scoring import relevance_score
from services.skills import deterministic_skill_overlap, filter_matched_skills


def browse_match_for_job(
    job: JobListing,
    profile: UserProfile,
    *,
    threshold: int,
    filter_reason: str | None = None,
) -> MatchResult:
    """Build a browse-only MatchResult with score in [1, threshold-1]."""
    early = early_relevance_score(job, profile)
    composite = relevance_score(job, profile)
    raw = max(early, composite)
    # Always at least 1% so the low-match toggle can show every scrape.
    ceiling = max(1, int(threshold) - 1)
    score = max(1, min(ceiling, int(raw) if raw > 0 else 1))

    skill_pct = deterministic_skill_overlap(profile, job)
    matched = filter_matched_skills(
        profile,
        list(job.skills)[:12] if job.skills else [],
    )
    reasons = [
        "Browse-only: did not pass strong match filters "
        f"(score floored for visibility)."
    ]
    if filter_reason:
        reasons.insert(0, f"Filter: {filter_reason.replace('_', ' ')}")

    return MatchResult(
        job=job,
        match_score=score,
        embed_score=float(early),
        skill_score=float(skill_pct),
        rerank_score=float(composite),
        llm_score=0.0,
        seniority_compatible=True,
        matched_skills=matched,
        missing_skills=[],
        reasons=reasons,
        recommendation=Recommendation.SKIP,
    )


def merge_browse_matches(
    strong: list[MatchResult],
    scraped: list[JobListing],
    rejected: list[tuple[JobListing, str]],
    profile: UserProfile,
    *,
    threshold: int,
) -> list[MatchResult]:
    """Append browse rows for scrapes not already in ``strong``."""
    seen = {m.job.content_hash for m in strong}
    reason_by_hash = {job.content_hash: reason for job, reason in rejected}
    out = list(strong)

    # Prefer rejected (with reasons), then any remaining scraped jobs.
    candidates: list[tuple[JobListing, str | None]] = list(rejected)
    rejected_hashes = {j.content_hash for j, _ in rejected}
    for job in scraped:
        if job.content_hash not in rejected_hashes and job.content_hash not in seen:
            candidates.append((job, None))

    for job, reason in candidates:
        if job.content_hash in seen:
            continue
        seen.add(job.content_hash)
        out.append(
            browse_match_for_job(
                job,
                profile,
                threshold=threshold,
                filter_reason=reason or reason_by_hash.get(job.content_hash),
            )
        )

    out.sort(key=lambda m: m.match_score, reverse=True)
    return out
