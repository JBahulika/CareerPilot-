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
        raise HTTPException(status_code=422, detail=str(exc))

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
    return {"profile_id": new_id, "profile": profile.model_dump()}
