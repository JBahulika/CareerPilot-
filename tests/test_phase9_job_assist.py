"""Phase 9 — skills gap + cover letter (user-selected only)."""

from __future__ import annotations

from models.schemas import UserProfile
from services.job_assist import build_skills_gap, draft_cover_letter


def test_build_skills_gap_structure():
    profile = UserProfile(name="Alex", skills=["Python", "FastAPI", "SQL"])
    match = {
        "match_id": 11,
        "job_id": 22,
        "title": "Backend Engineer",
        "company": "Acme",
        "match_score": 82,
        "matched_skills": ["Python", "FastAPI", "python"],
        "missing_skills": ["Kubernetes", ""],
    }
    gap = build_skills_gap(match, profile)
    assert gap["match_id"] == 11
    assert gap["matched_skills"] == ["Python", "FastAPI"]
    assert gap["missing_skills"] == ["Kubernetes"]
    assert gap["overlap_count"] == 2
    assert gap["gap_count"] == 1
    assert gap["auto_apply"] is False
    assert gap["auto_send"] is False
    assert gap["tips"]


def test_draft_cover_letter_calls_ollama(monkeypatch):
    called = {}

    def _fake(system, user, temperature=0.4):
        called["system"] = system
        called["user"] = user
        return "Dear Hiring Manager,\nI am excited...\nSincerely,\nAlex"

    monkeypatch.setattr("services.job_assist.call_ollama", _fake)
    profile = UserProfile(
        name="Alex",
        role="Software Engineer",
        skills=["Python"],
        experience_level="3-5 years",
    )
    match = {
        "match_id": 5,
        "title": "Python Engineer",
        "company": "Beta",
        "description": "Build APIs",
        "matched_skills": ["Python"],
        "missing_skills": ["Go"],
    }
    out = draft_cover_letter(profile, match)
    assert "Hiring Manager" in out["draft"]
    assert out["auto_apply"] is False
    assert out["auto_send"] is False
    assert "never" in out["disclaimer"].lower()
    assert "Alex" in called["user"]
    assert "Beta" in called["user"]
