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
    loc = search_location(profile)
    assert "Bengaluru" in loc or "Bangalore" in loc
    assert "Karnataka" in loc
    assert "India" in loc


def test_indeed_url_includes_location():
    from agents.job_sources.scrape_sources import _indeed_host

    profile = UserProfile(role="Engineer", preferred_location="Bangalore")
    query = quote_plus(search_terms(profile))
    loc = quote_plus(search_location(profile))
    host = _indeed_host(profile)
    url = f"{host}/jobs?q={query}&sort=date&l={loc}"
    assert host == "https://in.indeed.com"
    assert "bengaluru" in url.lower() or "bangalore" in url.lower()
    assert "karnataka" in url.lower()


def test_indeed_host_global_for_us():
    from agents.job_sources.scrape_sources import _indeed_host

    assert _indeed_host(UserProfile(preferred_location="New York, USA")) == "https://www.indeed.com"


def test_naukri_url_includes_location_slug():
    profile = UserProfile(role="Engineer", preferred_location="Bangalore")
    query = quote_plus(search_terms(profile))
    slug = query.replace("+", "-")
    loc = search_location(profile)
    loc_slug = quote_plus(loc).replace("+", "-").lower()
    url = f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
    assert "jobs-in-" in url
    assert "bengaluru" in url.lower() or "bangalore" in url.lower()
