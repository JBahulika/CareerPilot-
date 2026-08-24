"""Unit tests for scrape card field parsing (Indeed/Naukri)."""

from __future__ import annotations

from agents.job_sources.scrape_sources import _indeed_host, _naukri_location_slug, _parse_card_fields
from models.schemas import UserProfile


def test_naukri_card_skips_rating_for_location():
    lines = [
        "Python Developer",
        "Persistent",
        "3.5",
        "5297 Reviews",
        "3-7 Yrs",
        "Bengaluru",
        "Build APIs",
        "3 weeks ago",
        "Save",
    ]
    parsed = _parse_card_fields(lines, source_id="naukri")
    assert parsed["title"] == "Python Developer"
    assert parsed["company"] == "Persistent"
    assert parsed["location"] == "Bengaluru"
    assert "3.5" not in parsed["location"]


def test_naukri_location_slug_short():
    profile = UserProfile(preferred_location="Bengaluru")
    assert _naukri_location_slug(profile) == "bangalore"


def test_indeed_host_india():
    assert _indeed_host(UserProfile(preferred_location="Pune")) == "https://in.indeed.com"
    assert _indeed_host(UserProfile(preferred_location="Austin, TX")) == "https://www.indeed.com"
