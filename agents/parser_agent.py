"""Resume Parser Agent (FR-1, FR-2).

Two-stage parsing:
  1. PyMuPDF text extraction + deterministic contact/section heuristics
  2. Local LLM structured extraction into ``UserProfile``
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import fitz  # PyMuPDF

from agents.base import call_ollama_json
from core.logging import get_logger
from models.schemas import UserProfile
from prompts.templates import RESUME_PARSER_SYSTEM

logger = get_logger(__name__)

_PARSE_CACHE: dict[str, dict] = {}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}"
)
_URL_RE = re.compile(r"https?://[^\s<>]+|(?:linkedin\.com/in/\S+|github\.com/\S+)", re.I)
_SECTION_HEADERS = re.compile(
    r"(?im)^(?:"
    r"experience|work experience|professional experience|employment|"
    r"education|projects?|skills|technical skills|certifications?|summary|"
    r"objective|about me"
    r")\s*:?\s*$"
)


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


def _file_hash(file_path: str | Path) -> str:
    data = Path(file_path).read_bytes()
    return hashlib.sha256(data).hexdigest()

def _extract_contacts(text: str) -> dict[str, str]:
    emails = _EMAIL_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    urls = _URL_RE.findall(text)
    linkedin = next((u for u in urls if "linkedin" in u.lower()), "")
    github = next((u for u in urls if "github" in u.lower()), "")
    portfolio = next(
        (u for u in urls if "linkedin" not in u.lower() and "github" not in u.lower()),
        "",
    )
    return {
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "linkedin_url": linkedin if linkedin.startswith("http") else (
            f"https://{linkedin}" if linkedin else ""
        ),
        "github_url": github if github.startswith("http") else (
            f"https://{github}" if github else ""
        ),
        "portfolio_url": portfolio if portfolio.startswith("http") else (
            f"https://{portfolio}" if portfolio else ""
        ),
    }


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "header"
    sections[current] = []
    for line in text.splitlines():
        if _SECTION_HEADERS.match(line.strip()):
            current = line.strip().rstrip(":").lower()
            sections[current] = []
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def _merge_contacts(profile: UserProfile, contacts: dict[str, str]) -> UserProfile:
    updates: dict = {}
    if contacts.get("email") and not profile.email:
        updates["email"] = contacts["email"]
    if contacts.get("phone") and not profile.phone:
        updates["phone"] = contacts["phone"]
    if contacts.get("linkedin_url") and not profile.linkedin_url:
        updates["linkedin_url"] = contacts["linkedin_url"]
    if contacts.get("github_url") and not profile.github_url:
        updates["github_url"] = contacts["github_url"]
    if contacts.get("portfolio_url") and not profile.portfolio_url:
        updates["portfolio_url"] = contacts["portfolio_url"]
    if not updates:
        return profile
    return profile.model_copy(update=updates)


def _normalize_skills(profile: UserProfile) -> UserProfile:
    if profile.technical_skills:
        merged = profile.all_skills()
        return profile.model_copy(update={"skills": merged})
    if profile.skills and not profile.technical_skills:
        return profile.model_copy(update={"technical_skills": list(profile.skills)})
    return profile


class ResumeParserAgent:
    """Turns a resume file into a structured, validated profile."""

    def run(self, file_path: str | Path) -> UserProfile:
        logger.info(f"Parsing resume: {file_path}")
        path = Path(file_path)
        file_hash = _file_hash(path)
        if file_hash in _PARSE_CACHE:
            logger.info(f"Using cached parse for {path.name}")
            return UserProfile.model_validate(_PARSE_CACHE[file_hash])

        raw_text = extract_text(path)

        contacts = _extract_contacts(raw_text)
        sections = _split_sections(raw_text)
        section_blob = "\n\n".join(
            f"## {name.upper()}\n{body[:2500]}"
            for name, body in sections.items()
            if body
        )

        user_prompt = (
            "Parse the following resume into the required JSON schema.\n\n"
            f"PRE-EXTRACTED CONTACTS (use these if the resume agrees):\n{contacts}\n\n"
            f"DETECTED SECTIONS:\n{section_blob[:8000]}\n\n"
            f"FULL RESUME TEXT:\n{raw_text[:12000]}"
        )
        data = call_ollama_json(RESUME_PARSER_SYSTEM, user_prompt)

        try:
            profile = UserProfile.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Profile validation failed: {exc}")
            raise ValueError(f"Could not parse resume into a valid profile: {exc}")

        profile = _merge_contacts(profile, contacts)
        profile = _normalize_skills(profile)

        if (
            not profile.all_skills()
            and not profile.experience
            and not profile.projects
        ):
            raise ValueError(
                "Parsed profile is empty. The resume may be scanned/image-based "
                "or unreadable."
            )

        logger.info(
            f"Parsed profile for '{profile.name or 'unknown'}' "
            f"with {len(profile.all_skills())} skills."
        )
        _PARSE_CACHE[file_hash] = profile.model_dump()
        return profile
