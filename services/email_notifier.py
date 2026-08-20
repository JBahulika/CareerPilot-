"""Email digest delivery via SMTP (stdlib only — no real sends in unit tests)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from core.config import settings
from core.logging import get_logger
from services.notify_config import NotifyConfig, email_ready, resolve_notify_config

logger = get_logger(__name__)


def email_configured(profile=None) -> bool:
    cfg = resolve_notify_config(profile) if profile is not None else resolve_notify_config()
    return email_ready(cfg)


def send_email(
    subject: str,
    body: str,
    *,
    to: str | None = None,
    cfg: NotifyConfig | None = None,
) -> bool:
    """Send plain-text email via SMTP. Returns False if misconfigured or on error."""
    config = cfg or resolve_notify_config()
    if not config.smtp_host:
        logger.warning("Email not configured (SMTP host missing).")
        return False

    recipient = (to or config.email_to or "").strip()
    if not recipient:
        logger.warning("Email not configured (recipient missing).")
        return False

    sender = (config.smtp_from or config.smtp_user or "").strip()
    if not sender:
        logger.warning("Email not configured (from / user missing).")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    try:
        if config.smtp_use_tls:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if config.smtp_user:
                    smtp.login(config.smtp_user, config.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                if config.smtp_user:
                    smtp.login(config.smtp_user, config.smtp_password)
                smtp.send_message(msg)
        logger.info(f"Email digest sent to {recipient}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Email send failed: {exc}")
        return False
