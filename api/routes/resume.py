"""Resume upload and parsing endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from agents.parser_agent import ResumeParserAgent
from core.config import settings
from core.logging import get_logger
from database.repositories import get_latest_profile, save_profile
from models.schemas import UserProfile

router = APIRouter(prefix="/resume", tags=["resume"])
logger = get_logger(__name__)
_parser = ResumeParserAgent()


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    dest = settings.resumes_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)
    logger.info(f"Saved resume to {dest}")

    try:
        profile = _parser.run(dest)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resume parse failed")
        raise HTTPException(
            status_code=500,
            detail=(
                f"Resume parsing failed: {exc}. "
                "Check that Ollama is running and the selected model is pulled "
                "(e.g. ollama pull qwen2.5:7b)."
            ),
        ) from exc

    profile_id = save_profile(profile, file.filename)
    return {"profile_id": profile_id, "profile": profile.model_dump()}


@router.get("/latest")
def latest_profile() -> dict:
    result = get_latest_profile()
    if result is None:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")
    profile_id, profile = result
    return {"profile_id": profile_id, "profile": profile.model_dump()}


@router.put("/{profile_id}")
def update_profile(profile_id: int, profile: UserProfile) -> dict:
    """Persist user edits to a parsed profile."""
    new_id = save_profile(profile, resume_filename="")
    try:
        from services.google_drive import maybe_backup_profile

        maybe_backup_profile(profile)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Drive profile backup skipped: {exc}")
    return {"profile_id": new_id, "profile": profile.model_dump()}


@router.post("/drive/credentials")
async def upload_drive_credentials(file: UploadFile = File(...)) -> dict:
    """Save a Google service-account JSON for Drive backups."""
    from services.google_drive import drive_credentials_status, save_service_account_json

    raw = await file.read()
    try:
        path = save_service_account_json(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    status = drive_credentials_status()
    return {
        "ok": True,
        "path": str(path),
        "client_email": status.get("client_email", ""),
        "hint": "Share your Drive folder with this service-account email (Editor).",
    }
