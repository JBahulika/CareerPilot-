"""Optional Google Drive backup (service-account JSON).

Uploads digests / profile snapshots to a Drive folder without blocking the
pipeline. Share the target folder with the service-account email.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.config import PROJECT_ROOT, settings
from core.logging import get_logger

logger = get_logger(__name__)

_SECRETS_DIR = PROJECT_ROOT / "data" / "secrets"
_DEFAULT_CREDS = _SECRETS_DIR / "gdrive_service_account.json"
_SCOPES = ("https://www.googleapis.com/auth/drive.file",)


def credentials_path() -> Path:
    custom = (getattr(settings, "google_drive_credentials_path", "") or "").strip()
    if custom:
        return Path(custom)
    return _DEFAULT_CREDS


def save_service_account_json(raw: bytes | str) -> Path:
    """Persist uploaded service-account JSON for the API process to use."""
    _SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    path = _DEFAULT_CREDS
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    data = json.loads(text)
    if not isinstance(data, dict) or "client_email" not in data:
        raise ValueError("Invalid service account JSON (missing client_email).")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def drive_credentials_status() -> dict[str, Any]:
    path = credentials_path()
    if not path.is_file():
        return {"configured": False, "path": str(path), "client_email": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "configured": True,
            "path": str(path),
            "client_email": str(data.get("client_email") or ""),
        }
    except Exception as exc:  # noqa: BLE001
        return {"configured": False, "path": str(path), "detail": str(exc)[:200]}


def _build_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    path = credentials_path()
    if not path.is_file():
        raise FileNotFoundError(f"Drive credentials missing: {path}")
    creds = service_account.Credentials.from_service_account_file(
        str(path), scopes=list(_SCOPES)
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_text(
    filename: str,
    content: str,
    *,
    folder_id: str,
    mime_type: str = "text/plain",
) -> str | None:
    """Upload a text/json file. Returns Drive file id or None on failure."""
    folder_id = (folder_id or "").strip()
    if not folder_id:
        logger.warning("Google Drive upload skipped: no folder_id.")
        return None
    try:
        from googleapiclient.http import MediaInMemoryUpload

        service = _build_service()
        media = MediaInMemoryUpload(
            content.encode("utf-8"), mimetype=mime_type, resumable=False
        )
        meta: dict[str, Any] = {"name": filename, "parents": [folder_id]}
        created = (
            service.files()
            .create(body=meta, media_body=media, fields="id,name", supportsAllDrives=True)
            .execute()
        )
        file_id = created.get("id")
        logger.info(f"Google Drive uploaded {filename} -> {file_id}")
        return file_id
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Google Drive upload failed for {filename}: {exc}")
        return None


def maybe_backup_digest(profile, text: str, run_id: int) -> str | None:
    """Best-effort digest backup when profile enables Drive."""
    from services.notify_config import resolve_notify_config

    cfg = resolve_notify_config(profile)
    if not cfg.google_drive_enabled or not cfg.google_drive_folder_id:
        return None
    name = f"careerpilot_digest_run{run_id}.txt"
    return upload_text(name, text, folder_id=cfg.google_drive_folder_id)


def maybe_backup_profile(profile) -> str | None:
    """Best-effort profile JSON snapshot (secrets redacted lightly)."""
    from services.notify_config import resolve_notify_config

    cfg = resolve_notify_config(profile)
    if not cfg.google_drive_enabled or not cfg.google_drive_folder_id:
        return None
    data = profile.model_dump() if hasattr(profile, "model_dump") else dict(profile)
    for key in ("smtp_password", "whatsapp_token"):
        if data.get(key):
            data[key] = "***"
    name = f"careerpilot_profile_{(data.get('name') or 'user').replace(' ', '_')}.json"
    return upload_text(
        name,
        json.dumps(data, indent=2, default=str),
        folder_id=cfg.google_drive_folder_id,
        mime_type="application/json",
    )


def maybe_backup_run_summary(profile, run_id: int, summary: dict) -> str | None:
    from services.notify_config import resolve_notify_config

    cfg = resolve_notify_config(profile)
    if not cfg.google_drive_enabled or not cfg.google_drive_folder_id:
        return None
    name = f"careerpilot_run{run_id}_summary.json"
    return upload_text(
        name,
        json.dumps(summary or {}, indent=2, default=str),
        folder_id=cfg.google_drive_folder_id,
        mime_type="application/json",
    )
