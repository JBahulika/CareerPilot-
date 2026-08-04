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


def test_scrape_boards_on_by_default():
    by_id = {s["id"]: s for s in POPULAR_JOB_SITES}
    for sid in ("indeed", "linkedin", "glassdoor", "wellfound", "naukri"):
        assert by_id[sid]["enabled_by_default"] is True
        assert by_id[sid]["method"] == "scrape"


def test_default_enabled_include_api_and_scrape_boards():
    enabled = set(default_enabled_source_ids())
    assert "remotive" in enabled
    assert "themuse" in enabled
    assert "weworkremotely" in enabled
    assert "workingnomads" in enabled
    assert "linkedin" in enabled
    assert "indeed" in enabled
    assert "glassdoor" in enabled
    assert "naukri" in enabled
    assert "wellfound" in enabled


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
    by_id = {r["id"]: r for r in agg.last_fetch_report}
    assert by_id["linkedin"]["status"] == "skipped"
    assert by_id["remotive"]["status"] == "empty"


def test_aggregate_report_records_errors():
    class _Ok:
        name = "remotive"

        def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None):
            from agents.job_sources.common import build_job
            from datetime import datetime

            return [
                build_job(
                    source="remotive",
                    company="Acme",
                    title="Python Engineer",
                    description="Python remote",
                    posted_at=datetime.utcnow(),
                )
            ]

    class _Boom:
        name = "linkedin"

        def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None):
            raise RuntimeError("connection refused")

    agg = AggregateSource([_Ok(), _Boom()])
    profile = UserProfile(enabled_sources=["remotive", "linkedin"])
    jobs = agg.fetch(profile, limit=20)
    assert len(jobs) == 1
    by_id = {r["id"]: r for r in agg.last_fetch_report}
    assert by_id["remotive"]["status"] == "ok"
    assert by_id["remotive"]["returned"] == 1
    assert by_id["linkedin"]["status"] == "error"
    assert "refused" in by_id["linkedin"]["detail"]


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
