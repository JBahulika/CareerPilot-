"""Phase 11 — remote API auth + run endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.config import settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "remote_api_token", "test-remote-secret-token")
    monkeypatch.setattr(settings, "remote_ui_enabled", True)
    # Avoid scheduler side effects during import lifespan where possible
    from main import app

    with TestClient(app) as c:
        yield c


def _auth():
    return {"Authorization": "Bearer test-remote-secret-token"}


def test_remote_disabled_without_token(monkeypatch):
    monkeypatch.setattr(settings, "remote_api_token", "")
    from main import app

    with TestClient(app) as c:
        r = c.get("/remote/ping")
        assert r.status_code == 503


def test_remote_unauthorized(client):
    r = client.get("/remote/ping")
    assert r.status_code == 401
    r2 = client.get("/remote/ping", headers={"Authorization": "Bearer wrong"})
    assert r2.status_code == 401


def test_remote_ping_ok(client):
    r = client.get("/remote/ping", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["auto_apply"] is False
    assert body["captcha_solving"] is False


def test_remote_status(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.remote.get_latest_profile", lambda: (1, MagicMock())
    )
    monkeypatch.setattr("api.routes.remote.list_runs", lambda limit=5: [])
    monkeypatch.setattr(
        "api.routes.remote.get_scheduler_status",
        lambda: {"running": False, "next_run": None, "enabled": True},
    )
    r = client.get("/remote/status", headers=_auth())
    assert r.status_code == 200
    assert r.json()["profile_id"] == 1
    assert r.json()["auto_apply"] is False


def test_remote_pipeline_run(client, monkeypatch):
    profile = MagicMock()
    profile.notify_on_manual_run = False
    monkeypatch.setattr(
        "api.routes.remote.get_latest_profile", lambda: (7, profile)
    )
    monkeypatch.setattr("api.routes.remote.get_profile", lambda _id: None)
    monkeypatch.setattr("api.routes.remote.create_run", lambda _pid: 42)
    monkeypatch.setattr(
        "api.routes.remote.resolve_send_digest",
        lambda **kwargs: False,
    )
    added = []

    class _BG:
        def add_task(self, fn, **kwargs):
            added.append((fn, kwargs))

    # TestClient injects BackgroundTasks; patch run_pipeline to no-op
    monkeypatch.setattr("api.routes.remote.run_pipeline", lambda **kw: None)

    r = client.post(
        "/remote/pipeline/run",
        headers=_auth(),
        json={"top_n": 5, "scrape_limit": 40},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == 42
    assert body["profile_id"] == 7
    assert body["status"] == "pending"


def test_remote_pipeline_run_no_profile(client, monkeypatch):
    monkeypatch.setattr("api.routes.remote.get_latest_profile", lambda: None)
    monkeypatch.setattr("api.routes.remote.get_profile", lambda _id: None)
    r = client.post(
        "/remote/pipeline/run",
        headers=_auth(),
        json={},
    )
    assert r.status_code == 404


def test_x_remote_token_header(client):
    r = client.get(
        "/remote/ping",
        headers={"X-Remote-Token": "test-remote-secret-token"},
    )
    assert r.status_code == 200


def test_meta_remote_no_secrets(client):
    r = client.get("/meta/remote")
    assert r.status_code == 200
    body = r.json()
    assert "token_configured" in body
    assert body["token_configured"] is True
    assert "test-remote-secret-token" not in str(body)
    assert body.get("mobile_ui_path") == "/m/"
    assert body.get("auto_apply") is False
    assert "readiness" in body


def test_meta_remote_disabled(monkeypatch):
    monkeypatch.setattr(settings, "remote_api_token", "")
    from main import app

    with TestClient(app) as c:
        r = c.get("/meta/remote")
        assert r.status_code == 200
        body = r.json()
        assert body["token_configured"] is False
        assert body["ok"] is False
        assert body["readiness"] == "disabled"
