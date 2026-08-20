"""Tests for digest preparation: threshold, location, sort, and cap."""

from __future__ import annotations

from models.schemas import UserProfile
from services.digest import prepare_digest_matches, short_reason


def _match(**kwargs):
    base = {
        "company": "Acme",
        "title": "Engineer",
        "match_score": 80,
        "location": "Bengaluru, Karnataka, India",
        "apply_url": "https://example.com/job",
        "reasons": ["Strong Python and FastAPI overlap"],
    }
    base.update(kwargs)
    return base


def test_short_reason_prefers_first_reason():
    assert "Python" in short_reason(_match())
    assert short_reason(_match(reasons=[], recommendation="Apply")) == "Apply"


def test_prepare_drops_below_threshold_and_caps():
    profile = UserProfile(
        name="Alex",
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=70,
    )
    matches = [
        _match(title="A", match_score=95),
        _match(title="B", match_score=90),
        _match(title="C", match_score=85),
        _match(title="D", match_score=80),
        _match(title="E", match_score=75),
        _match(title="F", match_score=72),
        _match(title="Low", match_score=50),
    ]
    prepared, stats = prepare_digest_matches(profile, matches, max_jobs=5, skip_dedupe=True)
    assert stats["dropped_below_threshold"] == 1
    assert stats["sent"] == 5
    assert stats["truncated"] == 1
    assert [m["title"] for m in prepared] == ["A", "B", "C", "D", "E"]
    assert all(m["match_score"] >= 70 for m in prepared)


def test_prepare_drops_location_mismatch():
    profile = UserProfile(
        preferred_location="Bengaluru",
        include_remote=False,
        min_match_score=60,
    )
    matches = [
        _match(title="Local", location="Bengaluru, India", match_score=90),
        _match(title="Remote", location="Remote", match_score=99),
        _match(title="Elsewhere", location="New York, NY", match_score=95),
    ]
    prepared, stats = prepare_digest_matches(profile, matches, max_jobs=5, skip_dedupe=True)
    assert stats["dropped_location"] == 2
    assert [m["title"] for m in prepared] == ["Local"]


def test_prepare_allows_remote_when_enabled():
    profile = UserProfile(
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    matches = [
        _match(title="Remote", location="Remote — Worldwide", match_score=88),
    ]
    prepared, stats = prepare_digest_matches(profile, matches, max_jobs=5, skip_dedupe=True)
    assert stats["dropped_location"] == 0
    assert prepared[0]["title"] == "Remote"
