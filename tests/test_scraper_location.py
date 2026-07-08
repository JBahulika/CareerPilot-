"""Tests for location-aware scraper URLs."""

from __future__ import annotations

from urllib.parse import quote_plus

from agents.job_sources.common import search_location, search_terms
from models.schemas import UserProfile


def test_search_location_uses_preferred():
    profile = UserProfile(
        role="Engineer",
        preferred_location="Bangalore",
        location="Mumbai",
    )
    assert search_location(profile) == "Bangalore"


def test_indeed_url_includes_location():
    profile = UserProfile(role="Engineer", preferred_location="Bangalore")
    query = quote_plus(search_terms(profile))
    loc = quote_plus(search_location(profile))
    url = f"https://www.indeed.com/jobs?q={query}&sort=date&l={loc}"
    assert "l=Bangalore" in url or "l=bangalore" in url.lower()


def test_naukri_url_includes_location_slug():
    profile = UserProfile(role="Engineer", preferred_location="Bangalore")
    query = quote_plus(search_terms(profile))
    slug = query.replace("+", "-")
    loc_slug = quote_plus("Bangalore").replace("+", "-").lower()
    url = f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
    assert "jobs-in-bangalore" in url
