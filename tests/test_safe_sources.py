"""Tests for Phase 3 safe sources + allowlist."""

from __future__ import annotations

from datetime import datetime, timedelta

from agents.job_sources.aggregate import AggregateSource
from agents.job_sources.api_sources import (
    TheMuseSource,
    WeWorkRemotelySource,
    WorkingNomadsSource,
    _parse_rss_items,
)
from agents.job_sources.registry import (
    POPULAR_JOB_SITES,
    default_enabled_source_ids,
    get_source,
    resolve_enabled_sources,
)
from models.schemas import UserProfile


def _recent_iso() -> str:
    return (datetime.utcnow() - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_captcha_prone_sources_disabled_by_default():
    by_id = {s["id"]: s for s in POPULAR_JOB_SITES}
    for sid in ("indeed", "linkedin", "glassdoor"):
        assert by_id[sid]["safety"] == "disabled_captcha"
        assert by_id[sid]["enabled_by_default"] is False


def test_default_enabled_are_api_safe():
    enabled = set(default_enabled_source_ids())
    assert "remotive" in enabled
    assert "themuse" in enabled
    assert "weworkremotely" in enabled
    assert "workingnomads" in enabled
    assert "linkedin" not in enabled
    assert "indeed" not in enabled


def test_resolve_allowlist_uses_profile_override():
    profile = UserProfile(enabled_sources=["remotive", "naukri", "linkedin"])
    allowed = resolve_enabled_sources(profile)
    assert allowed == {"remotive", "naukri", "linkedin"}


def test_aggregate_respects_allowlist(monkeypatch):
    calls: list[str] = []

    class _Src:
        def __init__(self, name: str):
            self.name = name

        def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None):
            calls.append(self.name)
            return []

    agg = AggregateSource([_Src("remotive"), _Src("linkedin"), _Src("themuse")])
    profile = UserProfile(enabled_sources=["remotive", "themuse"])
    agg.fetch(profile, limit=20)
    assert "remotive" in calls
    assert "themuse" in calls
    assert "linkedin" not in calls


def test_parse_rss_items():
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Acme: Python Engineer</title>
        <link>https://example.com/1</link>
        <description>Build APIs</description>
        <pubDate>2024-01-02</pubDate>
      </item>
    </channel></rss>"""
    items = _parse_rss_items(xml)
    assert len(items) == 1
    assert "Python" in items[0]["title"]


def test_themuse_fixture(monkeypatch):
    fixture = {
        "results": [
            {
                "name": "Software Engineer",
                "contents": "<p>Python FastAPI</p>",
                "company": {"name": "MuseCo"},
                "locations": [{"name": "Remote"}],
                "categories": [{"name": "Software Engineering"}],
                "refs": {"landing_page": "https://example.com/job"},
                "publication_date": _recent_iso(),
            }
        ]
    }

    class _Client:
        def get_json(self, *a, **k):
            return fixture

    monkeypatch.setattr(
        "agents.job_sources.api_sources.get_scrape_client", lambda: _Client()
    )
    jobs = TheMuseSource().fetch(
        UserProfile(
            role="Software Engineer",
            skills=["Python"],
            preferred_roles=["Software Engineer"],
            experience_level="1-3 years",
            target_years_min=1,
            target_years_max=3,
        ),
        limit=5,
    )
    assert len(jobs) == 1
    assert jobs[0].company == "MuseCo"
    assert jobs[0].source == "themuse"


def test_weworkremotely_fixture(monkeypatch):
    xml = f"""<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Nomad Inc: Backend Engineer</title>
        <link>https://weworkremotely.com/jobs/1</link>
        <description>Python remote backend</description>
        <pubDate>{_recent_iso()}</pubDate>
      </item>
    </channel></rss>"""

    class _Resp:
        text = xml

    class _Client:
        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(
        "agents.job_sources.api_sources.get_scrape_client", lambda: _Client()
    )
    jobs = WeWorkRemotelySource().fetch(
        UserProfile(
            skills=["Python"],
            preferred_roles=["Backend Engineer"],
            experience_level="1-3 years",
            target_years_min=1,
            target_years_max=3,
        ),
        limit=5,
    )
    assert len(jobs) == 1
    assert jobs[0].source == "weworkremotely"
    assert "Backend" in jobs[0].title


def test_workingnomads_fixture(monkeypatch):
    fixture = [
        {
            "title": "ML Engineer",
            "company_name": "NomadLabs",
            "description": "Machine learning with Python",
            "location": "Remote",
            "url": "https://example.com/ml",
            "tags": ["python", "ml"],
            "pub_date": _recent_iso(),
        }
    ]

    class _Client:
        def get_json(self, *a, **k):
            return fixture

    monkeypatch.setattr(
        "agents.job_sources.api_sources.get_scrape_client", lambda: _Client()
    )
    jobs = WorkingNomadsSource().fetch(
        UserProfile(
            skills=["Python", "machine learning"],
            preferred_roles=["ML Engineer"],
            experience_level="1-3 years",
            target_years_min=1,
            target_years_max=3,
        ),
        limit=5,
    )
    assert len(jobs) == 1
    assert jobs[0].company == "NomadLabs"


def test_get_source_new_ids():
    assert get_source("themuse").name == "themuse"
    assert get_source("weworkremotely").name == "weworkremotely"
    assert get_source("workingnomads").name == "workingnomads"
