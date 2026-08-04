"""Tests for entry-level search term biasing in the scraper."""

from __future__ import annotations

from agents.job_sources.common import search_terms
from models.schemas import UserProfile


def test_fresher_search_includes_entry_keywords():
    profile = UserProfile(experience_level="Fresher", role="AI Engineer")
    terms = search_terms(profile).lower()
    assert "junior" in terms
    assert "entry" in terms


def test_senior_search_does_not_add_junior_keywords():
    profile = UserProfile(experience_level="5+ years", role="AI Engineer")
    terms = search_terms(profile).lower()
    assert "junior" not in terms
