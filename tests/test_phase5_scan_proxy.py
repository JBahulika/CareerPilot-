"""Phase 5 — proxies, scan windows, quiet hours, 429 backoff."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.proxies import load_proxy_urls, next_proxy_url, proxy_status
from services.scan_windows import in_quiet_hours, pick_random_scan_datetime, scan_window_bounds
from services.scrape_http import RateLimitedError, SafeScrapeClient


def test_quiet_hours_overnight(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "quiet_hours_enabled", True)
    monkeypatch.setattr(config.settings, "quiet_hours_start_hour", 22)
    monkeypatch.setattr(config.settings, "quiet_hours_start_minute", 0)
    monkeypatch.setattr(config.settings, "quiet_hours_end_hour", 7)
    monkeypatch.setattr(config.settings, "quiet_hours_end_minute", 0)

    assert in_quiet_hours(datetime(2026, 8, 20, 23, 0)) is True
    assert in_quiet_hours(datetime(2026, 8, 20, 3, 0)) is True
    assert in_quiet_hours(datetime(2026, 8, 20, 10, 0)) is False


def test_quiet_hours_disabled(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "quiet_hours_enabled", False)
    assert in_quiet_hours(datetime(2026, 8, 20, 23, 0)) is False


def test_scan_window_bounds_and_random(monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "daily_scan_window_start_hour", 8)
    monkeypatch.setattr(config.settings, "daily_scan_window_start_minute", 0)
    monkeypatch.setattr(config.settings, "daily_scan_window_end_hour", 11)
    monkeypatch.setattr(config.settings, "daily_scan_window_end_minute", 0)

    start, end = scan_window_bounds()
    assert start == 8 * 60
    assert end == 11 * 60

    # Force "now" early so today's window is still ahead
    now = datetime(2026, 8, 20, 7, 0)
    picked = pick_random_scan_datetime(now)
    assert picked.date() == now.date()
    mins = picked.hour * 60 + picked.minute
    assert start <= mins < end


def test_proxy_load_and_rotate(tmp_path, monkeypatch):
    from core import config
    import services.proxies as proxies_mod

    proxy_file = tmp_path / "list.txt"
    proxy_file.write_text(
        "# comment\nhttp://127.0.0.1:8080\nhttp://127.0.0.1:8081\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.settings, "scrape_proxy_enabled", True)
    monkeypatch.setattr(config.settings, "scrape_proxy_url", "")
    monkeypatch.setattr(config.settings, "scrape_proxy_file", str(proxy_file))
    monkeypatch.setattr(config.settings, "scrape_proxy_rotate", True)
    monkeypatch.setattr(proxies_mod, "_INDEX", 0)

    urls = load_proxy_urls()
    assert urls == ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]
    assert next_proxy_url() == "http://127.0.0.1:8080"
    assert next_proxy_url() == "http://127.0.0.1:8081"
    status = proxy_status()
    assert status["configured"] is True
    assert status["count"] == 2
    assert status["samples"][0] == "http://127.0.0.1:8080"


def test_proxy_redacts_credentials(tmp_path, monkeypatch):
    from core import config

    monkeypatch.setattr(config.settings, "scrape_proxy_enabled", True)
    monkeypatch.setattr(
        config.settings, "scrape_proxy_url", "http://user:secret@proxy.example:8080"
    )
    monkeypatch.setattr(config.settings, "scrape_proxy_file", str(tmp_path / "missing.txt"))
    status = proxy_status()
    assert status["samples"] == ["http://***@proxy.example:8080"]


def test_429_backoff_honors_retry_after(monkeypatch):
    client = SafeScrapeClient()
    from services.source_health import SourceHealthRegistry

    registry = SourceHealthRegistry(cooldown_seconds=60)
    sleeps: list[float] = []
    calls = {"n": 0}

    class _Resp:
        def __init__(self, code: int, text: str, headers=None):
            self.status_code = code
            self.text = text
            self.headers = headers or {}
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
                return _Resp(429, "slow down", {"Retry-After": "3"})
            return _Resp(200, '{"ok":true}')

    monkeypatch.setattr("services.scrape_http.httpx.Client", _Client)
    monkeypatch.setattr("services.scrape_http.get_source_health_registry", lambda: registry)
    monkeypatch.setattr("services.scrape_http.settings.scrape_min_delay_ms", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_max_delay_ms", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_max_retries", 1)
    monkeypatch.setattr("services.scrape_http.settings.scrape_429_max_retries", 3)
    monkeypatch.setattr("services.scrape_http.settings.scrape_429_base_delay_ms", 1000)
    monkeypatch.setattr("services.scrape_http.settings.scrape_429_max_delay_ms", 60000)
    monkeypatch.setattr("services.scrape_http.settings.scrape_proxy_enabled", False)
    monkeypatch.setattr(
        "services.scrape_http.time.sleep", lambda s: sleeps.append(float(s))
    )

    resp = client.get("https://api.example.com/jobs", source_id="remotive")
    assert resp.status_code == 200
    assert calls["n"] == 2
    assert sleeps and sleeps[0] >= 3.0


def test_429_exhausted_raises(monkeypatch):
    client = SafeScrapeClient()
    from services.source_health import SourceHealthRegistry

    registry = SourceHealthRegistry(cooldown_seconds=60)

    class _Resp:
        status_code = 429
        text = "nope"
        headers = {}
        url = "https://api.example.com/jobs"

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
    monkeypatch.setattr("services.scrape_http.settings.scrape_429_max_retries", 0)
    monkeypatch.setattr("services.scrape_http.settings.scrape_proxy_enabled", False)
    monkeypatch.setattr("services.scrape_http.time.sleep", lambda *_: None)

    with pytest.raises(RateLimitedError):
        client.get("https://api.example.com/jobs", source_id="remotive")
