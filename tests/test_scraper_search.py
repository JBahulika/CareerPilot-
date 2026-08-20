"""Tests for skill + role search queries."""

from __future__ import annotations

from agents.job_sources.common import search_queries, search_terms
from models.schemas import UserProfile


def test_search_uses_skills_and_roles():
    profile = UserProfile(
        experience_level="Fresher",
        role="AI Engineer",
        skills=["Python", "PyTorch", "SQL", "LangChain", "FastAPI"],
        preferred_roles=["AI Engineer"],
        target_years_min=0,
        target_years_max=1,
    )
    queries = search_queries(profile)
    joined = " ".join(queries).lower()
    assert any(s in joined for s in ("python", "pytorch", "sql", "langchain", "fastapi"))
    assert "ai engineer" in joined
    # Primary may be a role or skill — both are valid discovery signals
    assert search_terms(profile)


def test_fresher_includes_junior_role_query():
    profile = UserProfile(
        experience_level="Fresher",
        role="AI Engineer",
        skills=["Python", "PyTorch", "Machine Learning"],
        preferred_roles=["AI Engineer"],
        target_years_min=0,
        target_years_max=0,
    )
    queries = search_queries(profile)
    joined = " ".join(queries).lower()
    assert "junior" in joined
    assert any("python" in q.lower() or "pytorch" in q.lower() for q in queries)


def test_senior_search_does_not_add_junior_keywords():
    profile = UserProfile(
        experience_level="5+ years",
        role="AI Engineer",
        skills=["Python", "PyTorch"],
        target_years_min=5,
        target_years_max=15,
    )
    joined = " ".join(search_queries(profile)).lower()
    assert "junior" not in joined
