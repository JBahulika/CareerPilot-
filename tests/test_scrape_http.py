"""Tests for safe scrape HTTP client and captcha abort (Phase 2)."""

from __future__ import annotations

import pytest

from services.scrape_http import (
    CaptchaBlockedError,
    SafeScrapeClient,
    looks_like_captcha,
)
from services.source_health import SourceHealthRegistry


def test_looks_like_captcha_detects_challenge_page():
    html = "<html><body>Attention Required! Enable JavaScript and cookies to continue. cf-challenge</body></html>"
    assert looks_like_captcha(html, status_code=403) is True


def test_looks_like_captcha_ignores_normal_job_html():
    html = "<html><body><h1>Python Engineer</h1><p>Build APIs with FastAPI.</p></body></html>"
    assert looks_like_captcha(html, status_code=200) is False


def test_safe_client_aborts_on_captcha(monkeypatch):
    client = SafeScrapeClient()
    registry = SourceHealthRegistry(cooldown_seconds=60)

    class _Resp:
        status_code = 403
        text = "<html>Just a moment... cf-challenge verify you are human</html>"
        headers = {}
        url = "https://example.com/jobs"

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr("services.scrape_http.httpx.Client", _Client)
    monkeypatch.setattr("services.scrape_http.get_source_health_registry", lambda: registry)
    monkeypatch.setattr("services.scrape_http.settings.scrape_min_delay_ms", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_max_delay_ms", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_max_retries", 0)

    with pytest.raises(CaptchaBlockedError):
        client.get("https://example.com/jobs", source_id="indeed")

    assert registry.get("indeed").status == "captcha_blocked"


def test_safe_client_retries_then_ok(monkeypatch):
    client = SafeScrapeClient()
    registry = SourceHealthRegistry(cooldown_seconds=60)
    calls = {"n": 0}

    class _Resp:
        def __init__(self, code: int, text: str):
            self.status_code = code
            self.text = text
            self.headers = {"content-type": "application/json"}
            self.url = "https://api.example.com/jobs"

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return _Resp(503, '{"error":"busy"}')
            return _Resp(200, '{"jobs":[]}')

    monkeypatch.setattr("services.scrape_http.httpx.Client", _Client)
    monkeypatch.setattr("services.scrape_http.get_source_health_registry", lambda: registry)
    monkeypatch.setattr("services.scrape_http.settings.scrape_min_delay_ms", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_max_delay_ms", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_max_retries", 2)
    monkeypatch.setattr("services.scrape_http.time.sleep", lambda *_: None)

    data = client.get_json("https://api.example.com/jobs", source_id="remotive")
    assert data == {"jobs": []}
    assert calls["n"] == 2
    assert registry.get("remotive").status == "ok"


def test_health_cooldown_blocks_source():
    reg = SourceHealthRegistry(cooldown_seconds=3600)
    reg.record("linkedin", "captcha_blocked", "challenge")
    assert reg.is_temporarily_blocked("linkedin") is True
    reg.mark_ok("linkedin")
    assert reg.is_temporarily_blocked("linkedin") is False
