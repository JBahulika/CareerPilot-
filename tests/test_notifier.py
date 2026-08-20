"""Tests for notification service (no real WhatsApp/email sends)."""

from __future__ import annotations

from models.schemas import UserProfile
from services.notifier import (
    BothNotifier,
    EmailNotifier,
    LocalNotifier,
    WhatsAppNotifier,
    get_latest_notification_preview,
    get_notifier,
    normalize_backend,
)


def _matches():
    return [
        {
            "company": "Acme",
            "title": "ML Engineer",
            "match_score": 90,
            "location": "Bengaluru",
            "apply_url": "https://example.com/job",
            "reasons": ["Strong ML stack overlap"],
        },
        {
            "company": "Beta",
            "title": "Junior Dev",
            "match_score": 70,
            "location": "Bengaluru",
            "apply_url": "https://example.com/j",
            "reasons": ["Entry fit"],
        },
        {
            "company": "Gamma",
            "title": "Low",
            "match_score": 40,
            "location": "Bengaluru",
            "apply_url": "https://example.com/low",
        },
    ]


def test_normalize_backend():
    assert normalize_backend("EMAIL") == "email"
    assert normalize_backend("both") == "both"
    assert normalize_backend("nope") == "local"


def test_get_notifier_selection(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "notifier_backend", "local")
    assert isinstance(get_notifier(), LocalNotifier)
    assert isinstance(get_notifier("whatsapp"), WhatsAppNotifier)
    assert isinstance(get_notifier("email"), EmailNotifier)
    assert isinstance(get_notifier("both"), BothNotifier)


def test_local_notifier_writes_file_and_caps(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    monkeypatch.setattr(config.settings, "max_digest_jobs", 1)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", False)
    profile = UserProfile(
        name="Alex",
        role="AI Engineer",
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    ok = LocalNotifier().send_job_digest(profile, _matches(), run_id=42)
    assert ok is True
    files = list((tmp_path / "notifications").glob("digest_*.txt"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "Acme" in text
    assert "ML Engineer" in text
    assert "Apply: https://example.com/job" in text
    assert "Why:" in text
    assert "no auto-apply" in text.lower()
    assert "Beta" not in text  # capped to 1
    assert "Low" not in text
    assert get_latest_notification_preview() is not None


def test_local_notifier_skips_empty_matches(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    ok = LocalNotifier().send_job_digest(UserProfile(), [], run_id=1)
    assert ok is False


def test_whatsapp_notifier_falls_back_to_local(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    monkeypatch.setattr(config.settings, "whatsapp_enabled", False)
    monkeypatch.setattr(config.settings, "max_digest_jobs", 5)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", False)
    profile = UserProfile(
        name="Alex",
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    ok = WhatsAppNotifier().send_job_digest(profile, _matches(), run_id=7)
    assert ok is True
    assert list((tmp_path / "notifications").glob("digest_*.txt"))


def test_email_notifier_falls_back_to_local(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    monkeypatch.setattr(config.settings, "smtp_host", "")
    monkeypatch.setattr(config.settings, "max_digest_jobs", 5)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", False)
    profile = UserProfile(
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    ok = EmailNotifier().send_job_digest(profile, _matches(), run_id=8)
    assert ok is True
    assert list((tmp_path / "notifications").glob("digest_*.txt"))


def test_email_notifier_calls_send_when_configured(tmp_path, monkeypatch):
    from core import config
    import services.notifier as notifier_mod

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    monkeypatch.setattr(config.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(config.settings, "smtp_user", "u@example.com")
    monkeypatch.setattr(config.settings, "smtp_from", "u@example.com")
    monkeypatch.setattr(config.settings, "email_to", "me@example.com")
    monkeypatch.setattr(config.settings, "max_digest_jobs", 5)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", False)

    called = {}

    def _fake_send(subject, body, *, to=None, cfg=None):
        called["subject"] = subject
        called["body"] = body
        return True

    monkeypatch.setattr(notifier_mod, "send_email", _fake_send)
    monkeypatch.setattr(notifier_mod, "email_ready", lambda cfg: True)

    profile = UserProfile(
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    assert EmailNotifier().send_job_digest(profile, _matches(), run_id=9) is True
    assert "CareerPilot" in called["subject"]
    assert "Acme" in called["body"]


def test_both_notifier_attempts_whatsapp_and_email(tmp_path, monkeypatch):
    from core import config
    import services.notifier as notifier_mod

    monkeypatch.setattr(config.settings, "logs_dir", tmp_path)
    monkeypatch.setattr(config.settings, "whatsapp_recipient", "+15551212")
    monkeypatch.setattr(config.settings, "max_digest_jobs", 5)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", False)

    calls = {"wa": 0, "email": 0}
    monkeypatch.setattr(notifier_mod, "whatsapp_ready", lambda cfg: True)
    monkeypatch.setattr(notifier_mod, "email_ready", lambda cfg: True)
    monkeypatch.setattr(
        notifier_mod,
        "send_message",
        lambda phone, text, **kw: calls.__setitem__("wa", calls["wa"] + 1) or True,
    )
    monkeypatch.setattr(
        notifier_mod,
        "send_email",
        lambda subject, body, **kw: calls.__setitem__("email", calls["email"] + 1) or True,
    )

    profile = UserProfile(
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    assert BothNotifier().send_job_digest(profile, _matches(), run_id=10) is True
    assert calls["wa"] == 1
    assert calls["email"] == 1
    assert list((tmp_path / "notifications").glob("digest_*.txt"))
