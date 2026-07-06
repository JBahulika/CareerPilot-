"""Resume Parser Agent (FR-1, FR-2).

Extracts raw text from a PDF resume with PyMuPDF, then uses the local LLM to
produce a structured ``UserProfile``.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from agents.base import call_ollama_json
from core.logging import get_logger
from models.schemas import UserProfile
from prompts.templates import RESUME_PARSER_SYSTEM

logger = get_logger(__name__)


def extract_text(file_path: str | Path) -> str:
    """Extract plain text from a PDF resume."""
    text_parts: list[str] = []
    with fitz.open(str(file_path)) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError("No text could be extracted from the resume PDF.")
    return text


class ResumeParserAgent:
    """Turns a resume file into a structured, validated profile."""

    def run(self, file_path: str | Path) -> UserProfile:
        logger.info(f"Parsing resume: {file_path}")
        raw_text = extract_text(file_path)

        user_prompt = (
            "Parse the following resume into the required JSON schema.\n\n"
            f"RESUME TEXT:\n{raw_text[:12000]}"
        )
        data = call_ollama_json(RESUME_PARSER_SYSTEM, user_prompt)

        try:
            profile = UserProfile.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Profile validation failed: {exc}")
            raise ValueError(f"Could not parse resume into a valid profile: {exc}")

        if not profile.skills and not profile.experience and not profile.projects:
            raise ValueError(
                "Parsed profile is empty. The resume may be scanned/image-based "
                "or unreadable."
            )

        logger.info(
            f"Parsed profile for '{profile.name or 'unknown'}' "
            f"with {len(profile.skills)} skills."
        )
        return profile
