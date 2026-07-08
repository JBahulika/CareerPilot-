"""Pluggable notification service for job digests.

``LocalNotifier`` writes digests to disk and logs them today.
``WhatsAppNotifier`` delegates to the WhatsApp agent when credentials exist.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from agents.whatsapp_agent import format_digest, send_message
from core.config import settings
from core.logging import get_logger
from models.schemas import UserProfile

logger = get_logger(__name__)


class Notifier(Protocol):
    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
    ) -> bool:
        ...


class LocalNotifier:
    """Persist digest to logs/notifications/ and log to console."""

    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
    ) -> bool:
        if not matches:
            logger.info(f"Run {run_id}: no matches to notify.")
            return False

        text = format_digest(matches, profile.name)
        out_dir = settings.logs_dir / "notifications"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"digest_run{run_id}_{stamp}.txt"
        path.write_text(text, encoding="utf-8")
        logger.info(f"Job digest saved to {path}")
        logger.info(f"Digest preview:\n{text[:500]}")
        return True


class WhatsAppNotifier:
    """Send digest via WhatsApp Cloud API when configured."""

    def send_job_digest(
        self,
        profile: UserProfile,
        matches: list[dict],
        run_id: int,
    ) -> bool:
        if not matches:
            return False

        text = format_digest(matches, profile.name)
        recipient = settings.whatsapp_recipient
        if not recipient:
            logger.warning("WHATSAPP_RECIPIENT not set; falling back to local log.")
            return LocalNotifier().send_job_digest(profile, matches, run_id)

        if send_message(recipient, text):
            return True

        logger.warning("WhatsApp send failed; writing local fallback.")
        return LocalNotifier().send_job_digest(profile, matches, run_id)


def get_notifier() -> Notifier:
    backend = (settings.notifier_backend or "local").lower()
    if backend == "whatsapp":
        return WhatsAppNotifier()
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
