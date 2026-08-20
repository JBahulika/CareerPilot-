"""Phase 8 — dedupe already-notified digest jobs."""

from __future__ import annotations

from datetime import datetime, timedelta

from models.schemas import UserProfile
from services.digest import prepare_digest_matches
from services.notified import (
    filter_already_notified,
    listing_fingerprint,
    normalize_apply_url,
    record_notified_matches,
    should_notify_again,
)


def test_normalize_apply_url_strips_tracking_noise():
    assert normalize_apply_url("https://Example.com/jobs/1/") == "https://example.com/jobs/1"
    assert normalize_apply_url("https://www.google.com/search?q=x") == ""


def test_should_notify_new_and_score_jump():
    from services.notified import PriorNotify

    prior = PriorNotify(
        match_score=70,
        posted_at=datetime(2026, 8, 1),
        listing_fingerprint="aaaa",
    )
    ok, reason = should_notify_again({"match_score": 70}, None)
    assert ok and reason == "new"
    ok, reason = should_notify_again({"match_score": 85}, prior, score_delta=10)
    assert ok and reason == "score_jump"
    ok, reason = should_notify_again({"match_score": 72}, prior, score_delta=10)
    assert not ok and reason == "already_notified"


def test_should_notify_on_newer_posted_at():
    from services.notified import PriorNotify

    prior = PriorNotify(
        match_score=80,
        posted_at=datetime(2026, 8, 1),
        listing_fingerprint="same",
    )
    ok, reason = should_notify_again(
        {
            "match_score": 80,
            "posted_at": "2026-08-10T00:00:00",
            "listing_fingerprint": "same",
        },
        prior,
    )
    assert ok and reason == "listing_refreshed"


def test_filter_and_record_roundtrip(tmp_path, monkeypatch):
    from core import config
    from database.session import init_db
    from sqlmodel import create_engine, Session, SQLModel
    import database.session as db_session

    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", True)
    monkeypatch.setattr(config.settings, "notify_resend_score_delta", 10)
    # Re-bind get_session to new engine via init
    import database.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    from contextlib import contextmanager

    @contextmanager
    def _sess():
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(db_session, "get_session", _sess)

    match = {
        "company": "Acme",
        "title": "Engineer",
        "match_score": 90,
        "location": "Bengaluru",
        "apply_url": "https://example.com/job/1",
        "content_hash": "hash-abc",
        "description": "Build APIs with FastAPI",
        "posted_at": "2026-08-20T00:00:00",
    }
    kept, dropped = filter_already_notified([match], profile_id=1)
    assert dropped == 0 and len(kept) == 1

    record_notified_matches([match], run_id=1, profile_id=1)
    kept2, dropped2 = filter_already_notified([match], profile_id=1)
    assert dropped2 == 1 and kept2 == []

    # Score jump re-notifies
    bumped = dict(match, match_score=100)
    kept3, dropped3 = filter_already_notified([bumped], profile_id=1)
    assert dropped3 == 0 and len(kept3) == 1


def test_prepare_digest_dedupes(tmp_path, monkeypatch):
    from core import config
    import database.session as db_session
    from sqlmodel import create_engine, Session, SQLModel
    from contextlib import contextmanager

    engine = create_engine(
        f"sqlite:///{tmp_path / 'd.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db_session, "engine", engine)
    import database.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    @contextmanager
    def _sess():
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(db_session, "get_session", _sess)
    monkeypatch.setattr(config.settings, "notify_dedupe_enabled", True)
    monkeypatch.setattr(config.settings, "max_digest_jobs", 5)

    profile = UserProfile(
        preferred_location="Bengaluru",
        include_remote=True,
        min_match_score=60,
    )
    m = {
        "company": "Acme",
        "title": "Engineer",
        "match_score": 90,
        "location": "Bengaluru",
        "apply_url": "https://example.com/x",
        "content_hash": "h1",
        "description": "Python",
    }
    prepared, stats = prepare_digest_matches(profile, [m], profile_id=7)
    assert stats["sent"] == 1
    record_notified_matches(prepared, run_id=2, profile_id=7)
    prepared2, stats2 = prepare_digest_matches(profile, [m], profile_id=7)
    assert stats2["sent"] == 0
    assert stats2["dropped_already_notified"] == 1
