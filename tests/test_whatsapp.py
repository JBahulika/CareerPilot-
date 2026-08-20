"""Tests for WhatsApp digest formatting (no network)."""

from __future__ import annotations

from agents.whatsapp_agent import format_digest


def test_format_digest_includes_jobs():
    matches = [
        {
            "company": "Google",
            "title": "AI Engineer",
            "match_score": 94,
            "location": "Remote",
            "apply_url": "https://x.com",
            "reasons": ["Strong LLM experience"],
        },
        {
            "company": "OpenAI",
            "title": "ML Engineer",
            "match_score": 88,
            "apply_url": "",
            "reasons": [],
        },
    ]
    text = format_digest(matches, "Alex", min_match_score=60, max_digest_jobs=5)
    assert "2 matches" in text
    assert "Google" in text
    assert "94%" in text
    assert "Alex" in text
    assert "Location: Remote" in text
    assert "Why: Strong LLM experience" in text
    assert "Apply: https://x.com" in text
    assert "no auto-apply" in text.lower()
    assert "Min match score: 60%" in text
    assert "Digest cap: 5" in text


def test_format_digest_empty():
    text = format_digest([], "Alex", min_match_score=70)
    assert "No matching jobs" in text
    assert "Alex" in text
