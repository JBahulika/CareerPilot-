"""Tests for job recency sorting and filtering."""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.scraper_agent import _parse_posted_at, _sort_and_filter_recent
from models.schemas import JobListing


def test_parse_posted_at_iso():
    dt = _parse_posted_at("2026-07-01T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026


def test_sort_newest_first():
    now = datetime.utcnow()
    jobs = [
        JobListing(title="Old", posted_at=now - timedelta(days=5), scraped_at=now),
        JobListing(title="New", posted_at=now - timedelta(days=1), scraped_at=now),
    ]
    sorted_jobs = _sort_and_filter_recent(jobs)
    assert sorted_jobs[0].title == "New"


def test_filter_drops_stale_jobs(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "recent_jobs_days", 3)
    now = datetime.utcnow()
    jobs = [
        JobListing(title="Recent", posted_at=now - timedelta(days=1), scraped_at=now),
        JobListing(title="Stale", posted_at=now - timedelta(days=10), scraped_at=now),
    ]
    kept = _sort_and_filter_recent(jobs)
    titles = [j.title for j in kept]
    assert "Recent" in titles
    assert "Stale" not in titles
