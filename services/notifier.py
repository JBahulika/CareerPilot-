"""Pluggable notification service for job digests.

Backends (Profile ``notifier_backend`` or ``NOTIFIER_BACKEND``):
  - ``local`` — write digest file under ``logs/notifications/``
  - ``whatsapp`` — WhatsApp Cloud API + always write local file
  - ``email`` — SMTP email + always write local file
  - ``both`` — WhatsApp + email + always write local file

Local file is always written when there is anything to notify (fallback / audit).
CareerPilot never auto-applies; digests are for human review only.

Phase 8: after a digest is written, jobs are recorded so later runs do not
re-notify the same listing unless it refreshed or the score jumped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from agents.whatsapp_agent import format_digest, send_message
from core.config import settings
from core.logging import get_logger
from models.schemas import UserProfile
from services.digest import prepare_digest_matches
from services.email_notifier import send_email
from services.notify_config import (
    VALID_BACKENDS,
    email_ready,
    normalize_backend,
    resolve_notify_config,
    whatsapp_ready,
)
from services.notified import record_notified_matches

# Re-export for older imports / tests
__all__ = [
    "VALID_BACKENDS",
    "normalize_backend",
    "get_notifier",
    "LocalNotifier",
    "WhatsAppNotifier",
    "EmailNotifier",
    "BothNotifier",
]

logger = get_logger(__name__)


class Notifier(Protocol):
    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
        *,
        profile_id: int | None = None,
    ) -> bool:
        ...


def _write_local_digest(text: str, run_id: int) -> bool:
    out_dir = settings.logs_dir / "notifications"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"digest_run{run_id}_{stamp}.txt"
    path.write_text(text, encoding="utf-8")
    logger.info(f"Job digest saved to {path}")
    logger.info(f"Digest preview:\n{text[:500]}")
    return True


def _maybe_drive_backup(profile: UserProfile, text: str, run_id: int) -> None:
    try:
        from services.google_drive import maybe_backup_digest

        maybe_backup_digest(profile, text, run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Drive digest backup skipped: {exc}")


def _digest_text(profile: UserProfile, matches: list[dict], stats: dict) -> str:
    return format_digest(
        matches,
        profile.name,
        min_match_score=stats.get("min_match_score"),
        max_digest_jobs=stats.get("max_digest_jobs"),
    )


def _prepare(
    profile: UserProfile,
    matches: list[dict],
    *,
    profile_id: int | None,
) -> tuple[list[dict], dict]:
    return prepare_digest_matches(profile, matches, profile_id=profile_id)


def _after_digest_sent(
    prepared: list[dict],
    *,
    run_id: int,
    profile_id: int | None,
) -> None:
    try:
        record_notified_matches(prepared, run_id=run_id, profile_id=profile_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not persist notified jobs for run {run_id}: {exc}")


class LocalNotifier:
    """Persist digest to logs/notifications/ and log to console."""

    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
        *,
        profile_id: int | None = None,
    ) -> bool:
        prepared, stats = _prepare(profile, matches, profile_id=profile_id)
        if not prepared:
            logger.info(
                f"Run {run_id}: no digest matches "
                f"(dropped_score={stats['dropped_below_threshold']}, "
                f"dropped_location={stats['dropped_location']}, "
                f"dropped_already={stats.get('dropped_already_notified', 0)})."
            )
            return False
        text = _digest_text(profile, prepared, stats)
        ok = _write_local_digest(text, run_id)
        _maybe_drive_backup(profile, text, run_id)
        if ok:
            _after_digest_sent(prepared, run_id=run_id, profile_id=profile_id)
        return ok


class WhatsAppNotifier:
    """Send digest via WhatsApp Cloud API; local file always written first."""

    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
        *,
        profile_id: int | None = None,
    ) -> bool:
        prepared, stats = _prepare(profile, matches, profile_id=profile_id)
        if not prepared:
            return False

        text = _digest_text(profile, prepared, stats)
        local_ok = _write_local_digest(text, run_id)
        _maybe_drive_backup(profile, text, run_id)
        if local_ok:
            _after_digest_sent(prepared, run_id=run_id, profile_id=profile_id)

        cfg = resolve_notify_config(profile)
        if not whatsapp_ready(cfg):
            logger.warning("WhatsApp not fully configured; local digest retained.")
            return local_ok

        if send_message(cfg.whatsapp_recipient, text, cfg=cfg):
            return True
        logger.warning("WhatsApp send failed; local digest retained.")
        return local_ok


class EmailNotifier:
    """Send digest via SMTP; local file always written first."""

    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
        *,
        profile_id: int | None = None,
    ) -> bool:
        prepared, stats = _prepare(profile, matches, profile_id=profile_id)
        if not prepared:
            return False

        text = _digest_text(profile, prepared, stats)
        local_ok = _write_local_digest(text, run_id)
        _maybe_drive_backup(profile, text, run_id)
        if local_ok:
            _after_digest_sent(prepared, run_id=run_id, profile_id=profile_id)

        cfg = resolve_notify_config(profile)
        if not email_ready(cfg):
            logger.warning("Email not fully configured; local digest retained.")
            return local_ok

        subject = (
            f"CareerPilot — {len(prepared)} job match"
            f"{'es' if len(prepared) != 1 else ''} (run {run_id})"
        )
        if send_email(subject, text, cfg=cfg):
            return True
        logger.warning("Email send failed; local digest retained.")
        return local_ok


class BothNotifier:
    """WhatsApp + email; local file always written."""

    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
        *,
        profile_id: int | None = None,
    ) -> bool:
        prepared, stats = _prepare(profile, matches, profile_id=profile_id)
        if not prepared:
            return False

        text = _digest_text(profile, prepared, stats)
        local_ok = _write_local_digest(text, run_id)
        _maybe_drive_backup(profile, text, run_id)
        if local_ok:
            _after_digest_sent(prepared, run_id=run_id, profile_id=profile_id)
        remote_ok = False
        cfg = resolve_notify_config(profile)

        if whatsapp_ready(cfg):
            if send_message(cfg.whatsapp_recipient, text, cfg=cfg):
                remote_ok = True
            else:
                logger.warning("WhatsApp send failed in both-backend mode.")
        else:
            logger.warning("WhatsApp not configured in both-backend mode.")

        if email_ready(cfg):
            subject = (
                f"CareerPilot — {len(prepared)} job match"
                f"{'es' if len(prepared) != 1 else ''} (run {run_id})"
            )
            if send_email(subject, text, cfg=cfg):
                remote_ok = True
            else:
                logger.warning("Email send failed in both-backend mode.")
        else:
            logger.warning("Email not configured in both-backend mode.")

        return local_ok or remote_ok


def get_notifier(backend: str | None = None, profile: UserProfile | None = None) -> Notifier:
    if backend is None and profile is not None:
        choice = resolve_notify_config(profile).backend
    else:
        choice = normalize_backend(backend)
    if choice == "whatsapp":
        return WhatsAppNotifier()
    if choice == "email":
        return EmailNotifier()
    if choice == "both":
        return BothNotifier()
    return LocalNotifier()


def get_latest_notification_preview(max_chars: int = 800) -> str | None:
    """Return text from the most recent notification file, if any."""
    out_dir = settings.logs_dir / "notifications"
    if not out_dir.exists():
        return None
    files = sorted(out_dir.glob("digest_*.txt"), reverse=True)
    if not files:
        return None
    text = files[0].read_text(encoding="utf-8")
    return text[:max_chars]
