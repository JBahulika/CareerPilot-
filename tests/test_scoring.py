"""Tests for the deterministic scrape-time relevance score."""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.job_sources.common import build_job
from models.schemas import UserProfile
from services.scoring import relevance_score


def _aiml_fresher() -> UserProfile:
    return UserProfile(
        role="Machine Learning Engineer",
        experience_level="0-1 years",
        target_years_min=0,
        target_years_max=1,
        skills=["Python", "PyTorch", "Machine Learning", "NLP"],
        preferred_roles=["Machine Learning Engineer", "AI Engineer"],
        preferred_location="Bangalore",
        include_remote=True,
    )


def test_relevant_entry_job_scores_higher_than_offtopic():
    profile = _aiml_fresher()
    good = build_job(
        source="test",
        company="Acme",
        title="Junior Machine Learning Engineer",
        description="Work on PyTorch and NLP models. Python required.",
        skills=["Python", "PyTorch", "NLP"],
        location="Remote",
        remote=True,
        posted_at=datetime.utcnow(),
    )
    bad = build_job(
        source="test",
        company="Acme",
        title="Senior Sales Manager",
        description="Lead the regional sales team and manage quotas.",
        location="Remote",
        posted_at=datetime.utcnow(),
    )
    assert relevance_score(good, profile) > relevance_score(bad, profile)


def test_excluded_title_scores_zero():
    profile = _aiml_fresher()
    job = build_job(
        source="test",
        company="Acme",
        title="Proposal Manager",
        description="Manage proposals and RFPs.",
        posted_at=datetime.utcnow(),
    )
    assert relevance_score(job, profile) == 0


def test_recent_job_beats_stale_equivalent():
    profile = _aiml_fresher()
    common = dict(
        source="test",
        company="Acme",
        title="Machine Learning Engineer",
        description="PyTorch, NLP, Python.",
        skills=["Python", "PyTorch"],
        location="Remote",
        remote=True,
    )
    fresh = build_job(**common, posted_at=datetime.utcnow())
    stale = build_job(**common, posted_at=datetime.utcnow() - timedelta(days=25))
    # content_hash is identical, but scoring is independent of dedup.
    assert relevance_score(fresh, profile) >= relevance_score(stale, profile)


def test_score_is_bounded():
    profile = _aiml_fresher()
    job = build_job(
        source="test",
        company="Acme",
        title="Machine Learning Engineer",
        description="PyTorch NLP Python machine learning deep learning",
        skills=["Python", "PyTorch", "NLP", "Machine Learning"],
        location="Bangalore",
        posted_at=datetime.utcnow(),
    )
    score = relevance_score(job, profile)
    assert 0 <= score <= 100
