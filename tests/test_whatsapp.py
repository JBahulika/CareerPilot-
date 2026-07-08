"""Tests for WhatsApp digest formatting."""

from __future__ import annotations

from agents.whatsapp_agent import format_digest


def test_format_digest_includes_jobs():
    matches = [
        {"company": "Google", "title": "AI Engineer", "match_score": 94, "apply_url": "https://x.com"},
        {"company": "OpenAI", "title": "ML Engineer", "match_score": 88, "apply_url": ""},
    ]
    text = format_digest(matches, "Alex")
    assert "2 new matches" in text
    assert "Google" in text
    assert "94%" in text
    assert "Alex" in text
