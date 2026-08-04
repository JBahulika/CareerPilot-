"""Tests for location helpers."""

from __future__ import annotations

from models.schemas import JobListing, UserProfile
from services.location import (
    effective_location,
    format_geo_query,
    is_remote_location,
    location_filter_ok,
    locations_match,
    resolve_cities,
)


def _job(location: str = "") -> JobListing:
    return JobListing(title="Engineer", company="Acme", location=location)


def test_effective_location_override_order():
    profile = UserProfile(
        location="Mumbai",
        preferred_location="Bangalore",
    )
    assert effective_location(profile) == "Bangalore"
    assert effective_location(profile, override="Delhi") == "Delhi"
    assert effective_location(UserProfile(location="Pune")) == "Pune"


def test_locations_match_aliases():
    assert locations_match("Bengaluru, India", "Bangalore")
    assert locations_match("Bangalore Urban, Karnataka, India", "bengaluru")
    assert locations_match("New Delhi, India", "delhi")
    assert locations_match("Delhi NCR", "New Delhi")
    assert locations_match("Mumbai, Maharashtra, India", "bombay")
    assert locations_match("Bombay", "Mumbai")
    assert locations_match("Gurugram", "Gurgaon")
    assert not locations_match("Chennai", "Bangalore")


def test_locations_match_region_from_city_pref():
    """User types city only; job lists state/country context."""
    assert locations_match("Karnataka, India", "Bengaluru")
    assert locations_match("Maharashtra", "Bombay")
    assert locations_match("Tamil Nadu", "Chennai")


def test_locations_match_multi_city_pref():
    assert locations_match("Chennai, TN", "Bangalore, Chennai")
    assert locations_match("Bengaluru", "Delhi / Bangalore")
    assert not locations_match("Pune", "Delhi, Chennai")


def test_format_geo_query_expands_city():
    q = format_geo_query("bangalore")
    assert "Bengaluru" in q or "Bangalore" in q
    assert "Karnataka" in q
    assert "India" in q
    q2 = format_geo_query("bombay")
    assert "Mumbai" in q2
    assert "Maharashtra" in q2


def test_resolve_cities_from_long_resume_location():
    cities = resolve_cities("Bangalore Urban, Karnataka, India")
    assert len(cities) == 1
    assert cities[0].canonical == "bengaluru"


def test_is_remote_location():
    assert is_remote_location("Fully Remote")
    assert is_remote_location("Work from home")
    assert not is_remote_location("Bangalore")


def test_location_filter_ok_remote_when_included():
    job = _job("Remote")
    assert location_filter_ok(job, "Bangalore", include_remote=True)


def test_location_filter_ok_remote_blocked_when_disabled():
    job = _job("Remote")
    assert not location_filter_ok(job, "Bangalore", include_remote=False)


def test_location_filter_ok_city_match():
    job = _job("Bangalore, Karnataka")
    assert location_filter_ok(job, "Bangalore", include_remote=False)
    assert location_filter_ok(job, "bengaluru", include_remote=False)
    assert location_filter_ok(_job("New Delhi"), "delhi", include_remote=False)
