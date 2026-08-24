"""Indeed GraphQL + location host helpers (no live network required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.job_sources.scrape_sources import (
    _indeed_country_code,
    _indeed_graphql_jobs,
    _indeed_host,
)
from models.schemas import UserProfile


def test_indeed_host_india():
    assert _indeed_host(UserProfile(preferred_location="Bengaluru")) == "https://in.indeed.com"
    assert _indeed_country_code(UserProfile(preferred_location="Pune, India")) == "IN"


def test_indeed_host_us():
    assert _indeed_host(UserProfile(preferred_location="Austin, TX")) == "https://www.indeed.com"
    assert _indeed_country_code(UserProfile(preferred_location="New York")) == "US"


def test_indeed_graphql_paginates_with_cursor():
    """Second page uses nextCursor; jobs accumulate across pages."""
    profile = UserProfile(preferred_location="Bengaluru, India", target_role="Python Developer")

    page1 = {
        "data": {
            "jobSearch": {
                "pageInfo": {"nextCursor": "CURSOR2"},
                "results": [
                    {
                        "job": {
                            "key": "jk1",
                            "title": "Python Developer",
                            "datePublished": 1_700_000_000_000,
                            "description": {"html": "<p>a</p>"},
                            "location": {"formatted": {"short": "Bengaluru"}},
                            "employer": {"name": "Acme"},
                        }
                    }
                ],
            }
        }
    }
    page2 = {
        "data": {
            "jobSearch": {
                "pageInfo": {"nextCursor": None},
                "results": [
                    {
                        "job": {
                            "key": "jk2",
                            "title": "Backend Engineer",
                            "datePublished": 1_700_000_100_000,
                            "description": {"html": "<p>b</p>"},
                            "location": {"formatted": {"short": "Bengaluru"}},
                            "employer": {"name": "Beta"},
                        }
                    }
                ],
            }
        }
    }

    responses = [page1, page2]
    call_bodies: list[dict] = []

    def _post(url, headers=None, json=None, timeout=None):  # noqa: A002
        call_bodies.append(json or {})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = responses[len(call_bodies) - 1]
        return resp

    with patch("agents.job_sources.scrape_sources.httpx.post", side_effect=_post):
        jobs = _indeed_graphql_jobs(profile, "Python Developer", limit=60)

    assert len(jobs) == 2
    assert {j.title for j in jobs} == {"Python Developer", "Backend Engineer"}
    assert "CURSOR2" in (call_bodies[1].get("query") or "")
    assert "sort: RELEVANCE" in (call_bodies[0].get("query") or "")
