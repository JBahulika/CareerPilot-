"""Runtime helpers for Phase 11 remote settings toggles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import PROJECT_ROOT, get_settings, settings
from core.logging import get_logger
from launcher.env_file import upsert_env_key

logger = get_logger(__name__)


def reload_settings() -> Any:
    """Clear Settings cache and refresh the module-level ``settings`` singleton."""
    import core.config as cfg

    get_settings.cache_clear()
    cfg.settings = get_settings()
    return cfg.settings


def apply_remote_settings(
    *,
    daily_scan_enabled: bool | None = None,
    notifier_backend: str | None = None,
    whatsapp_enabled: bool | None = None,
    notify_on_manual_run: bool | None = None,
    profile_id: int | None = None,
) -> dict[str, Any]:
    """Persist allowed toggles and restart the daily scheduler if needed."""
    env_path = PROJECT_ROOT / ".env"
    changed: list[str] = []

    if daily_scan_enabled is not None:
        upsert_env_key(env_path, "DAILY_SCAN_ENABLED", "true" if daily_scan_enabled else "false")
        changed.append("DAILY_SCAN_ENABLED")
    if notifier_backend is not None:
        backend = notifier_backend.strip().lower()
        from services.notify_config import VALID_BACKENDS

        if backend not in VALID_BACKENDS:
            raise ValueError(f"notifier_backend must be one of {sorted(VALID_BACKENDS)}")
        upsert_env_key(env_path, "NOTIFIER_BACKEND", backend)
        changed.append("NOTIFIER_BACKEND")
    if whatsapp_enabled is not None:
        upsert_env_key(env_path, "WHATSAPP_ENABLED", "true" if whatsapp_enabled else "false")
        changed.append("WHATSAPP_ENABLED")

    profile_updated = False
    if notify_on_manual_run is not None or (notifier_backend is not None and profile_id):
        from database.repositories import get_latest_profile, get_profile, save_profile

        target_id = profile_id
        profile = get_profile(profile_id) if profile_id else None
        if profile is None:
            latest = get_latest_profile()
            if latest:
                target_id, profile = latest
        if profile is not None and target_id is not None:
            updates: dict[str, Any] = {}
            if notify_on_manual_run is not None:
                updates["notify_on_manual_run"] = bool(notify_on_manual_run)
            if notifier_backend is not None:
                updates["notifier_backend"] = notifier_backend.strip().lower()
            if updates:
                save_profile(profile.model_copy(update=updates), resume_filename="")
                profile_updated = True
                changed.append("profile")

    new_settings = reload_settings() if any(
        c in {"DAILY_SCAN_ENABLED", "NOTIFIER_BACKEND", "WHATSAPP_ENABLED"} for c in changed
    ) else settings

    scheduler_action = "unchanged"
    if daily_scan_enabled is not None:
        from services.scheduler import start_daily_scan, stop_daily_scan

        stop_daily_scan()
        if new_settings.daily_scan_enabled:
            start_daily_scan()
            scheduler_action = "started"
        else:
            scheduler_action = "stopped"

    return {
        "changed": changed,
        "profile_updated": profile_updated,
        "scheduler_action": scheduler_action,
        "daily_scan_enabled": bool(new_settings.daily_scan_enabled),
        "notifier_backend": new_settings.notifier_backend,
        "whatsapp_enabled": bool(new_settings.whatsapp_enabled),
    }


def list_recent_digests(limit: int = 5, max_chars: int = 4000) -> list[dict[str, Any]]:
    out_dir = Path(settings.logs_dir) / "notifications"
    if not out_dir.exists():
        return []
    files = sorted(out_dir.glob("digest_*.txt"), reverse=True)[: max(1, min(limit, 20))]
    rows: list[dict[str, Any]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        rows.append(
            {
                "filename": path.name,
                "modified": path.stat().st_mtime,
                "preview": text[:max_chars],
                "chars": len(text),
            }
        )
    return rows
