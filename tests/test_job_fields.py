"""Tests for multi-field job selection."""

from __future__ import annotations

from agents.job_sources.common import content_hash
from models.schemas import JobListing, UserProfile
from services.job_fields import (
    effective_fields,
    infer_fields_from_profile,
    job_matches_any_field,
    search_queries_for_fields,
)


def _job(title: str, desc: str = "", skills=None) -> JobListing:
    return JobListing(
        title=title,
        company="Acme",
        description=desc,
        skills=skills or [],
        content_hash=content_hash("Acme", title, desc),
    )


def _aiml_profile(**kwargs) -> UserProfile:
    base = dict(
        experience_level="0-1 years",
        skills=["Python", "PyTorch", "Machine Learning"],
        preferred_roles=["AI Engineer", "Machine Learning Engineer"],
    )
    base.update(kwargs)
    return UserProfile(**base)


def test_infer_fields_from_aiml_resume():
    profile = _aiml_profile()
    fields = infer_fields_from_profile(profile)
    assert "aiml" in fields


def test_infer_fields_fallback_to_software():
    profile = UserProfile(role="Professional", skills=["communication"])
    fields = infer_fields_from_profile(profile)
    assert fields == ["software"]


def test_effective_fields_uses_user_selection():
    profile = _aiml_profile(preferred_fields=["backend", "devops"])
    assert effective_fields(profile) == ["backend", "devops"]


def test_effective_fields_infers_when_empty():
    profile = _aiml_profile(preferred_fields=[])
    assert "aiml" in effective_fields(profile)


def test_search_queries_for_fields_dedupes():
    profile = _aiml_profile(preferred_fields=["aiml"])
    queries = search_queries_for_fields(["aiml"], profile)
    assert "AI Engineer" in queries or "machine learning engineer" in queries
    assert len(queries) == len({q.lower() for q in queries})


def test_multi_field_or_matching_aiml_job():
    profile = _aiml_profile(preferred_fields=["aiml", "backend"])
    job = _job("Junior ML Engineer", "python pytorch machine learning")
    assert job_matches_any_field(job, ["aiml", "backend"], profile)


def test_frontend_job_excluded_when_only_aiml_selected():
    profile = _aiml_profile(preferred_fields=["aiml"])
    job = _job("Frontend Engineer", "react typescript ui development")
    assert not job_matches_any_field(job, ["aiml"], profile)


def test_backend_job_matches_backend_field():
    profile = UserProfile(
        preferred_fields=["backend"],
        skills=["python", "django"],
        preferred_roles=["Backend Engineer"],
    )
    job = _job("Backend Engineer", "python api microservices django")
    assert job_matches_any_field(job, ["backend"], profile)
