"""Resolve notification settings: Profile overrides, then ``.env`` / settings."""

from __future__ import annotations

from dataclasses import dataclass

from core.config import settings
from models.schemas import UserProfile

VALID_BACKENDS = frozenset({"local", "whatsapp", "email", "both"})


def normalize_backend(value: str | None = None) -> str:
    backend = (value if value is not None else settings.notifier_backend or "local")
    backend = backend.strip().lower()
    if backend not in VALID_BACKENDS:
        return "local"
    return backend


@dataclass(frozen=True)
class NotifyConfig:
    backend: str
    whatsapp_enabled: bool
    whatsapp_token: str
    whatsapp_phone_id: str
    whatsapp_recipient: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_use_tls: bool
    email_to: str
    google_drive_enabled: bool
    google_drive_folder_id: str


def _pick(profile_val: str | None, env_val: str) -> str:
    raw = (profile_val or "").strip()
    return raw if raw else (env_val or "").strip()


def resolve_notify_config(profile: UserProfile | None = None) -> NotifyConfig:
    """Merge profile notification fields over process env settings."""
    p = profile
    backend_raw = (getattr(p, "notifier_backend", "") or "").strip() if p else ""
    backend = normalize_backend(backend_raw) if backend_raw else normalize_backend()

    wa_token = _pick(getattr(p, "whatsapp_token", "") if p else "", settings.whatsapp_token)
    wa_phone_id = _pick(
        getattr(p, "whatsapp_phone_id", "") if p else "", settings.whatsapp_phone_id
    )
    wa_recipient = _pick(
        getattr(p, "notify_whatsapp", "") if p else "", settings.whatsapp_recipient
    )
    wa_enabled = bool(settings.whatsapp_enabled)
    if wa_token and wa_phone_id and wa_recipient:
        wa_enabled = True

    smtp_port = settings.smtp_port or 587
    if p is not None and getattr(p, "smtp_port", None):
        smtp_port = int(p.smtp_port)

    return NotifyConfig(
        backend=backend,
        whatsapp_enabled=wa_enabled,
        whatsapp_token=wa_token,
        whatsapp_phone_id=wa_phone_id,
        whatsapp_recipient=wa_recipient,
        smtp_host=_pick(getattr(p, "smtp_host", "") if p else "", settings.smtp_host),
        smtp_port=smtp_port,
        smtp_user=_pick(getattr(p, "smtp_user", "") if p else "", settings.smtp_user),
        smtp_password=_pick(
            getattr(p, "smtp_password", "") if p else "", settings.smtp_password
        ),
        smtp_from=_pick(getattr(p, "smtp_from", "") if p else "", settings.smtp_from),
        smtp_use_tls=bool(settings.smtp_use_tls),
        email_to=_pick(getattr(p, "notify_email", "") if p else "", settings.email_to),
        google_drive_enabled=bool(getattr(p, "google_drive_enabled", False)) if p else False,
        google_drive_folder_id=(
            (getattr(p, "google_drive_folder_id", "") or "").strip() if p else ""
        )
        or (getattr(settings, "google_drive_folder_id", "") or "").strip(),
    )


def whatsapp_ready(cfg: NotifyConfig) -> bool:
    return bool(
        cfg.whatsapp_enabled
        and cfg.whatsapp_token
        and cfg.whatsapp_phone_id
        and cfg.whatsapp_recipient
    )


def email_ready(cfg: NotifyConfig) -> bool:
    return bool(cfg.smtp_host and cfg.email_to and (cfg.smtp_from or cfg.smtp_user))


def resolve_send_digest(
    *,
    request_send_digest: bool | None,
    profile: UserProfile | None,
) -> bool:
    """Per-run override wins; else ``profile.notify_on_manual_run``."""
    if request_send_digest is not None:
        return bool(request_send_digest)
    if profile is None:
        return False
    return bool(getattr(profile, "notify_on_manual_run", False))
