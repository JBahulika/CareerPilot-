"""Tests for match-score threshold helpers and filter exclusion transparency."""

from __future__ import annotations

from agents.filter_agent import JobFilterAgent
from agents.job_sources.common import content_hash as _content_hash
from models.schemas import JobListing, MatchResult, Recommendation, UserProfile
from services.threshold import (
    effective_min_match_score,
    filter_digest_matches,
    filter_match_results,
)


def _job(title: str, desc: str = "python", location: str = "Remote") -> JobListing:
    return JobListing(
        title=title,
        company="Acme",
        description=desc,
        location=location,
        skills=["python"],
        content_hash=_content_hash("Acme", title, desc),
    )


def _match(score: int, title: str = "Engineer") -> MatchResult:
    return MatchResult(
        job=_job(title),
        match_score=score,
        recommendation=Recommendation.CONSIDER,
    )


def test_effective_threshold_override_beats_profile():
    profile = UserProfile(min_match_score=70)
    assert effective_min_match_score(profile, override=55) == 55
    assert effective_min_match_score(profile, override=None) == 70


def test_effective_threshold_falls_back_to_settings_default():
    profile = UserProfile()
    # UserProfile default is 60; still validates clamp
    assert effective_min_match_score(profile) == 60
    assert effective_min_match_score(None, override=120) == 100
    assert effective_min_match_score(None, override=-5) == 0


def test_filter_match_results_drops_below_threshold():
    matches = [_match(90), _match(50), _match(60)]
    kept, dropped = filter_match_results(matches, 60)
    assert dropped == 1
    assert [m.match_score for m in kept] == [90, 60]


def test_filter_digest_matches_dict_path():
    matches = [
        {"title": "A", "match_score": 80},
        {"title": "B", "match_score": 40},
    ]
    kept, dropped = filter_digest_matches(matches, 60)
    assert dropped == 1
    assert kept[0]["title"] == "A"


def test_location_mismatch_recorded_in_exclusions():
    profile = UserProfile(
        skills=["python"],
        experience_level="3-5 years",
        target_years_min=3,
        target_years_max=5,
        preferred_roles=["Engineer"],
        preferred_location="Bangalore",
        include_remote=False,
    )
    jobs = [
        _job("Remote Python Engineer", "python engineer", location="Remote"),
        _job("Local Python Engineer", "python engineer", location="Bangalore"),
    ]
    result = JobFilterAgent().run(jobs, profile)
    assert len(result.jobs) == 1
    assert result.jobs[0].location == "Bangalore"
    assert result.exclusions.get("location_mismatch", 0) >= 1
