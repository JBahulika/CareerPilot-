"""Tests for entry-level search query biasing in the scraper."""

from __future__ import annotations

from agents.job_sources.common import search_queries, search_terms
from models.schemas import UserProfile


def test_fresher_aiml_search_includes_entry_queries():
    profile = UserProfile(
        experience_level="Fresher",
        role="AI Engineer",
        skills=["Python", "PyTorch", "Machine Learning"],
        preferred_roles=["AI Engineer", "Machine Learning Engineer"],
    )
    queries = [q.lower() for q in search_queries(profile)]
    assert any("junior" in q for q in queries)
    assert any("machine learning" in q for q in queries)
    assert "ai engineer" in search_terms(profile).lower()


def test_senior_search_does_not_add_junior_queries():
    profile = UserProfile(
        experience_level="5+ years",
        role="AI Engineer",
        skills=["Python", "Machine Learning"],
        preferred_roles=["AI Engineer"],
    )
    queries = [q.lower() for q in search_queries(profile)]
    assert not any("junior" in q for q in queries)
