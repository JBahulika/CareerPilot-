"""Tests for notification service."""

from __future__ import annotations

from models.schemas import UserProfile
from services.notifier import LocalNotifier, get_latest_notification_preview


def test_local_notifier_writes_file(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    profile = UserProfile(name="Alex", role="AI Engineer")
    matches = [
        {
            "company": "Acme",
            "title": "ML Engineer",
            "match_score": 90,
            "apply_url": "https://example.com/job",
        }
    ]
    ok = LocalNotifier().send_job_digest(profile, matches, run_id=42)
    assert ok is True
    files = list((tmp_path / "notifications").glob("digest_*.txt"))
    assert len(files) == 1
    assert "Acme" in files[0].read_text()
    assert get_latest_notification_preview() is not None


def test_local_notifier_skips_empty_matches(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    ok = LocalNotifier().send_job_digest(UserProfile(), [], run_id=1)
    assert ok is False
