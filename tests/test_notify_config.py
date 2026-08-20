"""Tests for profile/env notify config merge."""

from __future__ import annotations

from models.schemas import UserProfile
from services.notify_config import (
    email_ready,
    resolve_notify_config,
    whatsapp_ready,
)


def test_profile_overrides_recipients(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "whatsapp_enabled", True)
    monkeypatch.setattr(config.settings, "whatsapp_token", "tok")
    monkeypatch.setattr(config.settings, "whatsapp_phone_id", "pid")
    monkeypatch.setattr(config.settings, "whatsapp_recipient", "+1000")
    monkeypatch.setattr(config.settings, "email_to", "env@example.com")
    monkeypatch.setattr(config.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(config.settings, "smtp_from", "from@example.com")
    monkeypatch.setattr(config.settings, "notifier_backend", "local")

    profile = UserProfile(
        notifier_backend="both",
        notify_whatsapp="+919999999999",
        notify_email="me@example.com",
        google_drive_enabled=True,
        google_drive_folder_id="folder123",
    )
    cfg = resolve_notify_config(profile)
    assert cfg.backend == "both"
    assert cfg.whatsapp_recipient == "+919999999999"
    assert cfg.email_to == "me@example.com"
    assert whatsapp_ready(cfg)
    assert email_ready(cfg)
    assert cfg.google_drive_enabled is True
    assert cfg.google_drive_folder_id == "folder123"


def test_profile_smtp_and_token_override(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "whatsapp_token", "")
    monkeypatch.setattr(config.settings, "whatsapp_phone_id", "")
    monkeypatch.setattr(config.settings, "whatsapp_recipient", "")
    monkeypatch.setattr(config.settings, "smtp_host", "")
    monkeypatch.setattr(config.settings, "email_to", "")

    profile = UserProfile(
        notify_whatsapp="+15551212",
        whatsapp_token="abc",
        whatsapp_phone_id="99",
        notify_email="a@b.com",
        smtp_host="smtp.gmail.com",
        smtp_from="a@b.com",
        smtp_user="a@b.com",
        smtp_password="x",
    )
    cfg = resolve_notify_config(profile)
    assert whatsapp_ready(cfg)
    assert email_ready(cfg)
    assert cfg.smtp_host == "smtp.gmail.com"
