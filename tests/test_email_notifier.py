"""Tests for SMTP email helper (mocked — no real network)."""

from __future__ import annotations

from services import email_notifier as email_mod


def test_email_configured_requires_host_and_recipient(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "smtp_host", "")
    monkeypatch.setattr(config.settings, "email_to", "a@b.com")
    monkeypatch.setattr(config.settings, "smtp_from", "a@b.com")
    assert email_mod.email_configured() is False

    monkeypatch.setattr(config.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(config.settings, "email_to", "")
    assert email_mod.email_configured() is False

    monkeypatch.setattr(config.settings, "email_to", "me@example.com")
    monkeypatch.setattr(config.settings, "smtp_from", "me@example.com")
    assert email_mod.email_configured() is True


def test_send_email_uses_smtp(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(config.settings, "smtp_port", 587)
    monkeypatch.setattr(config.settings, "smtp_user", "u@example.com")
    monkeypatch.setattr(config.settings, "smtp_password", "secret")
    monkeypatch.setattr(config.settings, "smtp_from", "u@example.com")
    monkeypatch.setattr(config.settings, "smtp_use_tls", True)
    monkeypatch.setattr(config.settings, "email_to", "me@example.com")

    class FakeSMTP:
        instances = []

        def __init__(self, host, port, timeout=30):
            self.host = host
            self.port = port
            self.ops = []
            FakeSMTP.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            self.ops.append("ehlo")

        def starttls(self):
            self.ops.append("starttls")

        def login(self, user, password):
            self.ops.append(("login", user))

        def send_message(self, msg):
            self.ops.append(("send", msg["To"], msg["Subject"], msg.get_content()))

    monkeypatch.setattr(email_mod.smtplib, "SMTP", FakeSMTP)
    ok = email_mod.send_email("Hello", "Body text")
    assert ok is True
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert "starttls" in smtp.ops
    assert ("login", "u@example.com") in smtp.ops
    assert any(op[0] == "send" and op[1] == "me@example.com" for op in smtp.ops)


def test_send_email_returns_false_when_unconfigured(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "smtp_host", "")
    assert email_mod.send_email("x", "y") is False
