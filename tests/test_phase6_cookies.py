"""Phase 6 — optional board cookies + stricter limits when used."""

from __future__ import annotations

from services.cookies import (
    cookie_status,
    load_cookie_header,
    load_playwright_cookies,
    source_has_cookies,
)
from services.scrape_http import SafeScrapeClient


def test_cookie_header_from_txt(tmp_path, monkeypatch):
    from core import config

    cookie_file = tmp_path / "linkedin.txt"
    cookie_file.write_text("li_at=secret_value; JSESSIONID=abc\n", encoding="utf-8")
    monkeypatch.setattr(config.settings, "scrape_cookies_enabled", True)
    monkeypatch.setattr(config.settings, "scrape_cookies_dir", str(tmp_path))

    assert source_has_cookies("linkedin") is True
    header = load_cookie_header("linkedin")
    assert header == "li_at=secret_value; JSESSIONID=abc"
    status = cookie_status()
    assert status["enabled"] is True
    assert "linkedin" in status["boards_active"]
    assert "secret_value" not in str(status)


def test_cookies_disabled_ignores_files(tmp_path, monkeypatch):
    from core import config

    (tmp_path / "indeed.txt").write_text("a=b", encoding="utf-8")
    monkeypatch.setattr(config.settings, "scrape_cookies_enabled", False)
    monkeypatch.setattr(config.settings, "scrape_cookies_dir", str(tmp_path))

    assert source_has_cookies("indeed") is False
    assert load_cookie_header("indeed") is None


def test_json_playwright_cookies(tmp_path, monkeypatch):
    from core import config
    import json

    payload = [
        {
            "name": "session",
            "value": "tok",
            "domain": ".indeed.com",
            "path": "/",
            "secure": True,
        }
    ]
    (tmp_path / "indeed.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(config.settings, "scrape_cookies_enabled", True)
    monkeypatch.setattr(config.settings, "scrape_cookies_dir", str(tmp_path))

    cookies = load_playwright_cookies("indeed")
    assert len(cookies) == 1
    assert cookies[0]["name"] == "session"
    assert cookies[0]["domain"] == "indeed.com"


def test_netscape_cookie_file(tmp_path, monkeypatch):
    from core import config

    netscape = (
        "# Netscape HTTP Cookie File\n"
        ".example.com\tTRUE\t/\tFALSE\t0\tsid\txyz\n"
    )
    (tmp_path / "remotive.txt").write_text(netscape, encoding="utf-8")
    monkeypatch.setattr(config.settings, "scrape_cookies_enabled", True)
    monkeypatch.setattr(config.settings, "scrape_cookies_dir", str(tmp_path))

    assert load_cookie_header("remotive") == "sid=xyz"


def test_http_client_attaches_cookie_and_strict_delay(tmp_path, monkeypatch):
    from core import config

    (tmp_path / "remotive.txt").write_text("tok=abc123", encoding="utf-8")
    monkeypatch.setattr(config.settings, "scrape_cookies_enabled", True)
    monkeypatch.setattr(config.settings, "scrape_cookies_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "scrape_cookies_strict", True)
    monkeypatch.setattr(config.settings, "scrape_cookie_min_delay_ms", 100)
    monkeypatch.setattr(config.settings, "scrape_cookie_max_delay_ms", 100)
    monkeypatch.setattr(config.settings, "scrape_min_delay_ms", 0)
    monkeypatch.setattr(config.settings, "scrape_max_delay_ms", 0)
    monkeypatch.setattr(config.settings, "scrape_max_retries", 0)
    monkeypatch.setattr(config.settings, "scrape_429_max_retries", 0)
    monkeypatch.setattr(config.settings, "scrape_proxy_enabled", False)

    seen: dict = {}
    sleeps: list[float] = []

    class _Resp:
        status_code = 200
        text = '{"ok":true}'
        headers = {}
        url = "https://remotive.com/api"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None, headers=None):
            seen["headers"] = dict(headers or {})
            return _Resp()

    from services.source_health import SourceHealthRegistry
    import time as time_mod

    registry = SourceHealthRegistry(cooldown_seconds=60)
    monkeypatch.setattr("services.scrape_http.httpx.Client", _Client)
    monkeypatch.setattr("services.scrape_http.get_source_health_registry", lambda: registry)
    monkeypatch.setattr(
        "services.scrape_http.time.sleep", lambda s: sleeps.append(float(s))
    )

    client = SafeScrapeClient()
    # Pretend we just requested so the cookie delay must sleep
    client._last_request_at = time_mod.monotonic()
    resp = client.get("https://remotive.com/api", source_id="remotive")
    assert resp.status_code == 200
    assert seen["headers"].get("Cookie") == "tok=abc123"
    assert sleeps and sleeps[0] >= 0.05


def test_status_never_leaks_secrets(tmp_path, monkeypatch):
    from core import config

    (tmp_path / "linkedin.txt").write_text("li_at=SUPERSECRET", encoding="utf-8")
    monkeypatch.setattr(config.settings, "scrape_cookies_enabled", True)
    monkeypatch.setattr(config.settings, "scrape_cookies_dir", str(tmp_path))
    blob = str(cookie_status())
    assert "SUPERSECRET" not in blob
    assert "li_at" not in blob
