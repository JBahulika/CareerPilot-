"""Tests for paginated match retrieval."""

from __future__ import annotations

from database.repositories import get_matches_for_run, save_matches, upsert_jobs
from models.schemas import JobListing, MatchResult, Recommendation


def _make_match(title: str, score: int) -> MatchResult:
    job = JobListing(
        title=title,
        company="Acme",
        description="python",
        content_hash=f"hash-{title}",
    )
    return MatchResult(job=job, match_score=score, recommendation=Recommendation.CONSIDER)


def test_pagination_slices_results():
    matches = [_make_match(f"Job{i}", 100 - i) for i in range(12)]
    job_ids = {}
    stored = upsert_jobs([m.job for m in matches])
    for m, jid in zip(matches, stored):
        job_ids[m.job.content_hash] = jid

    run_id = 9999
    save_matches(run_id, matches, job_ids)

    page1, total = get_matches_for_run(run_id, offset=0, limit=10)
    page2, _ = get_matches_for_run(run_id, offset=10, limit=10)

    assert total == 12
    assert len(page1) == 10
    assert len(page2) == 2
    assert page1[0]["match_score"] >= page1[-1]["match_score"]
