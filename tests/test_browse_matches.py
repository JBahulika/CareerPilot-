"""Tests for browse-only low matches from filter-rejected scrapes."""

from __future__ import annotations

from agents.job_sources.common import content_hash
from models.schemas import JobListing, MatchResult, Recommendation, UserProfile
from services.browse_matches import browse_match_for_job, merge_browse_matches


def _job(title: str, desc: str = "python", **kwargs) -> JobListing:
    return JobListing(
        title=title,
        company=kwargs.get("company", "Acme"),
        description=desc,
        skills=kwargs.get("skills", ["python"]),
        location=kwargs.get("location", "Remote"),
        content_hash=content_hash("Acme", title, desc),
    )


def test_browse_match_floors_to_at_least_one():
    profile = UserProfile(skills=["cobol"], preferred_roles=["COBOL Engineer"])
    job = _job("Unrelated Role", "totally different domain", skills=[])
    match = browse_match_for_job(job, profile, threshold=60, filter_reason="role_mismatch")
    assert match.match_score >= 1
    assert match.match_score < 60
    assert match.recommendation == Recommendation.SKIP
    assert any("role mismatch" in r.lower() for r in match.reasons)


def test_merge_browse_adds_rejected_not_in_strong():
    profile = UserProfile(skills=["python"], preferred_roles=["Engineer"])
    kept = _job("Python Engineer", "python fastapi")
    rejected = _job("Data Analyst", "sql excel", location="Mumbai")
    strong = [
        MatchResult(
            job=kept,
            match_score=80,
            recommendation=Recommendation.CONSIDER,
        )
    ]
    merged = merge_browse_matches(
        strong,
        [kept, rejected],
        [(rejected, "location_mismatch")],
        profile,
        threshold=60,
    )
    assert len(merged) == 2
    scores = {m.job.title: m.match_score for m in merged}
    assert scores["Python Engineer"] == 80
    assert 1 <= scores["Data Analyst"] < 60
