"""Phase 10a — still-hiring classification (fail closed on unknown dates)."""

from __future__ import annotations

from datetime import datetime, timedelta

from models.schemas import JobListing, UserProfile
from services.scoring import relevance_score
from services.still_hiring import (
    classify_still_hiring,
    prefer_still_hiring,
    still_hiring_label,
)


def test_classify_likely_stale_unknown():
    now = datetime(2026, 8, 20, 12, 0, 0)
    assert (
        classify_still_hiring(posted_at=now - timedelta(days=2), now=now, window_days=7)
        == "likely"
    )
    assert (
        classify_still_hiring(posted_at=now - timedelta(days=20), now=now, window_days=7)
        == "stale"
    )
    assert classify_still_hiring(posted_at=None, now=now, window_days=7) == "unknown"
    assert still_hiring_label("unknown") == "Date unknown"
    assert "still hiring" in still_hiring_label("likely").lower()


def test_never_invent_likely_from_missing_date():
    # scraped_at alone must not be passed as posted_at
    assert classify_still_hiring(posted_at=None) == "unknown"


def test_prefer_sorts_likely_before_stale_and_unknown(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "still_hiring_enabled", True)
    monkeypatch.setattr(config.settings, "still_hiring_prefer", True)
    monkeypatch.setattr(config.settings, "still_hiring_days", 7)
    now = datetime.utcnow()
    items = [
        {
            "title": "OldHigh",
            "match_score": 99,
            "posted_at": (now - timedelta(days=30)).isoformat(),
        },
        {
            "title": "FreshMid",
            "match_score": 70,
            "posted_at": (now - timedelta(days=1)).isoformat(),
        },
        {"title": "NoDate", "match_score": 95, "posted_at": None},
    ]
    ordered = prefer_still_hiring(items)
    assert [m["title"] for m in ordered] == ["FreshMid", "OldHigh", "NoDate"]
    assert ordered[0]["still_hiring"] == "likely"
    assert ordered[2]["still_hiring"] == "unknown"


def test_recency_score_fail_closed_without_posted_at(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "still_hiring_enabled", True)
    profile = UserProfile(
        role="Engineer",
        skills=["Python"],
        preferred_roles=["Engineer"],
        experience_level="3-5 years",
        target_years_min=3,
        target_years_max=5,
    )
    undated = JobListing(
        title="Python Engineer",
        company="Acme",
        description="Build APIs with Python",
        skills=["Python"],
        posted_at=None,
        scraped_at=datetime.utcnow(),
    )
    fresh = JobListing(
        title="Python Engineer",
        company="Acme",
        description="Build APIs with Python",
        skills=["Python"],
        posted_at=datetime.utcnow() - timedelta(days=1),
        scraped_at=datetime.utcnow(),
    )
    # Undated must not get a free recency boost from scraped_at
    assert relevance_score(undated, profile) < relevance_score(fresh, profile)
