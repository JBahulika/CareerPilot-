"""Tests for job recency sorting and filtering."""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.job_sources.common import (
    build_job,
    parse_posted_at,
    parse_relative_posted_at,
    sort_and_filter_recent,
)
from models.schemas import JobListing


def test_parse_posted_at_iso():
    dt = parse_posted_at("2026-07-01T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026


def test_parse_relative_months_ago():
    now = datetime(2026, 8, 7, 12, 0, 0)
    dt = parse_relative_posted_at("Software Engineer\nAcme\n5 months ago", now=now)
    assert dt is not None
    assert (now - dt).days >= 140


def test_sort_newest_first():
    now = datetime.utcnow()
    jobs = [
        JobListing(title="Old", posted_at=now - timedelta(days=5), scraped_at=now),
        JobListing(title="New", posted_at=now - timedelta(days=1), scraped_at=now),
    ]
    sorted_jobs = sort_and_filter_recent(jobs, recent_days=14)
    assert sorted_jobs[0].title == "New"


def test_filter_drops_stale_jobs(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "recent_jobs_days", 3)
    now = datetime.utcnow()
    jobs = [
        JobListing(title="Recent", posted_at=now - timedelta(days=1), scraped_at=now),
        JobListing(title="Stale", posted_at=now - timedelta(days=10), scraped_at=now),
    ]
    kept = sort_and_filter_recent(jobs)
    titles = [j.title for j in kept]
    assert "Recent" in titles
    assert "Stale" not in titles


def test_filter_drops_five_month_old_with_14_day_window():
    now = datetime.utcnow()
    jobs = [
        JobListing(
            title="Ancient",
            posted_at=now - timedelta(days=150),
            scraped_at=now,
        ),
        JobListing(
            title="Fresh",
            posted_at=now - timedelta(days=2),
            scraped_at=now,
        ),
    ]
    kept = sort_and_filter_recent(jobs, recent_days=14)
    titles = [j.title for j in kept]
    assert titles == ["Fresh"]


def test_unknown_posted_at_fail_closed_when_window_set():
    now = datetime.utcnow()
    jobs = [
        JobListing(title="NoDate", posted_at=None, scraped_at=now),
        JobListing(title="Fresh", posted_at=now - timedelta(days=1), scraped_at=now),
    ]
    kept = sort_and_filter_recent(jobs, recent_days=14)
    assert [j.title for j in kept] == ["Fresh"]


def test_build_job_recovers_relative_date_from_description():
    job = build_job(
        source="linkedin",
        company="Acme",
        title="Engineer",
        description="Bengaluru\n5 months ago\nBuild APIs",
        apply_url="https://example.com/job",
    )
    assert job.posted_at is not None
    assert (datetime.utcnow() - job.posted_at).days >= 100
