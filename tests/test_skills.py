"""Tests for skill relevance and false-positive blocking."""

from __future__ import annotations

from agents.job_sources.common import content_hash
from agents.filter_agent import JobFilterAgent
from models.schemas import JobListing, UserProfile
from services.skills import (
    filter_matched_skills,
    has_unrelated_enterprise_stack,
    is_excluded_job_title,
    is_relevant_job_posting,
)


def _job(title: str, desc: str = "", skills=None) -> JobListing:
    return JobListing(
        title=title,
        company="Acme",
        description=desc,
        skills=skills or [],
        content_hash=content_hash("Acme", title, desc),
    )


def _aiml_profile() -> UserProfile:
    return UserProfile(
        experience_level="0-1 years",
        target_years_min=0,
        target_years_max=1,
        skills=[
            "Python",
            "PyTorch",
            "TensorFlow",
            "LangChain",
            "Machine Learning",
        ],
        preferred_roles=["AI Engineer", "Machine Learning Engineer"],
    )


def test_abap_job_blocked_for_aiml_profile():
    profile = _aiml_profile()
    job = _job("SAP ABAP Developer", "ABAP and SAP required", skills=["ABAP", "SAP"])
    assert has_unrelated_enterprise_stack(job, profile)
    kept = JobFilterAgent().run([job], profile, strict_experience=True)
    assert len(kept) == 0


def test_aiml_job_relevant_for_aiml_profile():
    profile = _aiml_profile()
    job = _job("Junior ML Engineer", "Python pytorch machine learning", skills=["Python"])
    assert is_relevant_job_posting(job, profile)
    assert not has_unrelated_enterprise_stack(job, profile)


def test_aiml_profile_blocks_unrelated_manager_roles():
    profile = _aiml_profile()
    assert is_excluded_job_title("Proposal Manager")
    assert is_excluded_job_title("Junior Risk Manager")
    job = _job("Proposal Manager", "project management and proposals", skills=[])
    assert not is_relevant_job_posting(job, profile)
    job2 = _job(
        "Binance Accelerator Program - Lifecycle Operations",
        "marketing operations CRM",
        skills=[],
    )
    assert not is_relevant_job_posting(job2, profile)


def test_filter_matched_skills_rejects_hallucinated_abap():
    profile = _aiml_profile()
    claimed = ["Python", "ABAP", "PyTorch"]
    filtered = filter_matched_skills(profile, claimed)
    assert "Python" in filtered
    assert "PyTorch" in filtered
    assert "ABAP" not in filtered
