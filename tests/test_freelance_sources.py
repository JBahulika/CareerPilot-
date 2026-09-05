"""Freelance marketplace sources (API / RSS / Playwright)."""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.job_sources.freelance_sources import (
    FREELANCE_PLAYWRIGHT_SPECS,
    FreelancerComSource,
    PlaywrightFreelanceSource,
    RssFreelanceSource,
    _format_search_url,
    freelance_registry_rows,
)
from agents.job_sources.registry import POPULAR_JOB_SITES, get_source
from models.schemas import UserProfile


def _recent_iso() -> str:
    return (datetime.utcnow() - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_freelance_sites_in_registry():
    ids = {s["id"] for s in POPULAR_JOB_SITES}
    assert "freelancer" in ids
    assert "upwork" in ids
    assert "guru" in ids
    assert "peopleperhour" in ids
    assert "internshala" in ids
    assert "truelancer" in ids
    assert "fiverr" in ids
    assert "toptal" in ids
    assert len(freelance_registry_rows()) >= 20


def test_freelancer_com_default_on():
    meta = next(s for s in POPULAR_JOB_SITES if s["id"] == "freelancer")
    assert meta["enabled_by_default"] is True
    assert meta["safety"] == "api"
    assert get_source("freelancer").name == "freelancer"


def test_long_tail_freelance_off_by_default():
    by_id = {s["id"]: s for s in POPULAR_JOB_SITES}
    for sid in ("fiverr", "toptal", "flexjobs", "ninetyninedesigns"):
        assert by_id[sid]["enabled_by_default"] is False


def test_freelancer_api_fixture(monkeypatch):
    fixture = {
        "status": "success",
        "result": {
            "projects": [
                {
                    "id": 1,
                    "title": "Python FastAPI backend",
                    "preview_description": "Build APIs with Python",
                    "seo_url": "python/python-fastapi-backend",
                    "type": "hourly",
                    "time_submitted": int(
                        (datetime.utcnow() - timedelta(hours=6)).timestamp()
                    ),
                    "budget": {"minimum": 20, "maximum": 40},
                    "currency": {"sign": "$", "code": "USD"},
                    "jobs": [{"name": "Python"}],
                    "location": {"country": {"name": "India"}},
                }
            ]
        },
    }

    class _Client:
        def get_json(self, *a, **k):
            return fixture

    monkeypatch.setattr(
        "agents.job_sources.freelance_sources.get_scrape_client", lambda: _Client()
    )
    jobs = FreelancerComSource().fetch(
        UserProfile(
            role="Python Developer",
            skills=["Python", "FastAPI"],
            preferred_roles=["Python Developer"],
            experience_level="1-3 years",
            target_years_min=1,
            target_years_max=3,
        ),
        limit=5,
    )
    assert len(jobs) == 1
    assert jobs[0].source == "freelancer"
    assert "FastAPI" in jobs[0].title
    assert jobs[0].apply_url.startswith("https://www.freelancer.com/projects/")
    assert "20" in jobs[0].salary


def test_rss_freelance_fixture(monkeypatch):
    xml = f"""<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Remote Python contractor</title>
        <link>https://jobspresso.co/jobs/1</link>
        <description>Python FastAPI contract</description>
        <pubDate>{_recent_iso()}</pubDate>
      </item>
    </channel></rss>"""

    class _Resp:
        text = xml

    class _Client:
        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(
        "agents.job_sources.freelance_sources.get_scrape_client", lambda: _Client()
    )
    spec = next(s for s in freelance_registry_rows() if s["id"] == "jobspresso")
    from agents.job_sources.freelance_sources import FREELANCE_RSS_SPECS

    src = RssFreelanceSource(FREELANCE_RSS_SPECS[0])
    jobs = src.fetch(
        UserProfile(
            skills=["Python"],
            preferred_roles=["Python Developer"],
            experience_level="1-3 years",
            target_years_min=1,
            target_years_max=3,
        ),
        limit=5,
    )
    assert spec["id"] == "jobspresso"
    assert len(jobs) == 1
    assert jobs[0].source == "jobspresso"


def test_playwright_freelance_fixture(monkeypatch):
    spec = next(s for s in FREELANCE_PLAYWRIGHT_SPECS if s.id == "upwork")

    def _fake_cards(url, selectors, limit, *, source_id=""):
        assert "upwork.com" in url
        return [
            {
                "title": "Python scraper",
                "company": "Acme",
                "location": "Remote",
                "description": "Python FastAPI freelance",
                "apply_url": "/jobs/1",
            }
        ]

    monkeypatch.setattr(
        "agents.job_sources.scrape_sources._playwright_fetch_cards", _fake_cards
    )
    jobs = PlaywrightFreelanceSource(spec).fetch(
        UserProfile(
            skills=["Python"],
            preferred_roles=["Python Developer"],
            experience_level="1-3 years",
            target_years_min=1,
            target_years_max=3,
        ),
        limit=5,
    )
    assert len(jobs) == 1
    assert jobs[0].source == "upwork"
    assert jobs[0].apply_url.startswith("https://www.upwork.com")


def test_format_search_url_encodes_query():
    url = _format_search_url(
        "https://www.guru.com/d/jobs/q/{query_slug}/",
        "Python Developer",
        "Bengaluru",
    )
    assert "python-developer" in url
    assert " " not in url
