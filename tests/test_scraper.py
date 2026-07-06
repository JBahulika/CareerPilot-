"""Tests for scraper hashing, HTML stripping, and Remotive parsing."""

from __future__ import annotations

from agents.scraper_agent import RemotiveSource, _content_hash, _strip_html
from models.schemas import UserProfile


def test_content_hash_is_stable_and_case_insensitive():
    a = _content_hash("Google", "AI Engineer", "Build models")
    b = _content_hash("google", "ai engineer", "build models")
    assert a == b


def test_content_hash_differs_for_different_jobs():
    a = _content_hash("Google", "AI Engineer", "Build models")
    b = _content_hash("Amazon", "ML Engineer", "Deploy models")
    assert a != b


def test_strip_html_removes_tags():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello  world"


def test_remotive_parses_fixture(monkeypatch):
    fixture = {
        "jobs": [
            {
                "title": "AI Engineer",
                "company_name": "Acme",
                "description": "<p>Build <b>ML</b> systems</p>",
                "tags": ["Python", "PyTorch"],
                "candidate_required_location": "Remote",
                "salary": "$100k",
                "url": "https://example.com/job/1",
            }
        ]
    }

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return fixture

    monkeypatch.setattr(
        "agents.scraper_agent.requests.get", lambda *a, **k: _Resp()
    )

    jobs = RemotiveSource().fetch(
        UserProfile(role="AI Engineer", experience_level="3-5 years"), limit=10
    )
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Acme"
    assert job.skills == ["Python", "PyTorch"]
    assert "<" not in job.description
    assert job.content_hash
