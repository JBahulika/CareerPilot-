"""Adzuna optional API helpers (no live network)."""

from __future__ import annotations

from agents.job_sources.api_sources import AdzunaSource, _adzuna_country
from models.schemas import UserProfile


def test_adzuna_country_india():
    assert _adzuna_country(UserProfile(preferred_location="Bengaluru")) == "in"
    assert _adzuna_country(UserProfile(preferred_location="Pune, India")) == "in"


def test_adzuna_country_default_us():
    assert _adzuna_country(UserProfile(preferred_location="Austin, TX")) == "us"


def test_adzuna_skips_without_keys():
    jobs = AdzunaSource().fetch(
        UserProfile(preferred_location="Bengaluru", target_role="Engineer"),
        limit=10,
    )
    assert jobs == []


def test_adzuna_in_registry():
    from agents.job_sources.registry import POPULAR_JOB_SITES, get_source

    meta = next(s for s in POPULAR_JOB_SITES if s["id"] == "adzuna")
    assert meta["enabled_by_default"] is False
    assert get_source("adzuna").name == "adzuna"
