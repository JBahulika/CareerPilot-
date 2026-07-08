"""Tests for daily scheduler job."""

from __future__ import annotations

from services import scheduler as sched_module


def test_daily_job_skips_without_profile(monkeypatch):
    monkeypatch.setattr(sched_module, "get_latest_profile", lambda: None)
    called = {"pipeline": False}

    def _fake_pipeline(*args, **kwargs):
        called["pipeline"] = True

    monkeypatch.setattr(sched_module, "run_pipeline", _fake_pipeline)
    sched_module._daily_job()
    assert called["pipeline"] is False
