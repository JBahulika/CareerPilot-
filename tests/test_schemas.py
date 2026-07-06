"""Tests for schema behavior and JSON extraction robustness."""

from __future__ import annotations

from agents.base import _extract_json
from agents.pdf_agent import _safe_filename
from models.schemas import JobListing, UserProfile


def test_extract_json_from_code_fence():
    text = 'Here you go:\n```json\n{"name": "Jo"}\n```'
    assert _extract_json(text) == {"name": "Jo"}


def test_extract_json_tolerates_trailing_comma():
    text = '{"skills": ["a", "b",],}'
    assert _extract_json(text) == {"skills": ["a", "b"]}


def test_user_profile_validates_partial_data():
    profile = UserProfile.model_validate({"name": "Jo", "skills": ["Python"]})
    assert profile.role == ""
    assert profile.experience_level == "Fresher"
    assert "Python" in profile.summary_text()


def test_job_match_text_includes_key_fields():
    job = JobListing(company="Acme", title="AI Engineer", skills=["Python"])
    text = job.match_text()
    assert "AI Engineer" in text and "Acme" in text and "Python" in text


def test_safe_filename_sanitizes():
    name = _safe_filename("Google/AI", "ML Engineer!")
    assert "/" not in name and " " not in name
    assert name.startswith("Resume_")
