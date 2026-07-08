"""Tests for location helpers."""

from __future__ import annotations

from models.schemas import JobListing, UserProfile
from services.location import (
    effective_location,
    is_remote_location,
    location_filter_ok,
    locations_match,
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
    assert locations_match("Gurugram", "Gurgaon")
    assert not locations_match("Chennai", "Bangalore")


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
