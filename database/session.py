"""SQLite engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from core.config import settings

# check_same_thread=False lets FastAPI background tasks share the engine.
engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


def _migrate_columns() -> None:
    """Add columns introduced after initial schema (SQLite-safe)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("jobs")}
    with engine.begin() as conn:
        if "posted_at" not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN posted_at DATETIME"))


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Import ensures models are registered on SQLModel.metadata.
    from database import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_columns()


@contextmanager
def get_session() -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
