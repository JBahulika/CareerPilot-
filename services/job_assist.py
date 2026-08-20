"""User-selected job assist: skills gap + cover-letter draft (Phase 9).

Only invoked after the user picks a match in Results / via API.
Never auto-sends email/WhatsApp and never auto-applies.
"""

from __future__ import annotations

from typing import Any

from agents.base import call_ollama
from core.logging import get_logger
from models.schemas import UserProfile

logger = get_logger(__name__)

_COVER_SYSTEM = (
    "You write concise, professional cover-letter drafts for job seekers. "
    "Use only the resume/profile and job details provided. "
    "Do not invent employers, degrees, or tools the candidate does not list. "
    "Do not claim the letter was sent or that you applied. "
    "Output plain text only (no markdown fences)."
)


def build_skills_gap(
    match: dict[str, Any],
    profile: UserProfile | None = None,
) -> dict[str, Any]:
    """Structured skills gap from stored match fields (no network / no apply)."""
    matched = [str(s).strip() for s in (match.get("matched_skills") or []) if str(s).strip()]
    missing = [str(s).strip() for s in (match.get("missing_skills") or []) if str(s).strip()]
    # Dedupe case-insensitively preserving order
    def _uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    matched = _uniq(matched)
    missing = _uniq(missing)
    profile_skills = []
    if profile is not None:
        profile_skills = _uniq([str(s) for s in (profile.skills or []) if str(s).strip()])

    tips: list[str] = []
    if missing:
        tips.append(
            "Consider highlighting adjacent experience for the missing technical skills, "
            "or be ready to learn them quickly if you apply."
        )
    if matched:
        tips.append("Lead with the matched skills in your resume bullets and cover letter.")
    if not matched and not missing:
        tips.append("Re-run matching if skills look empty — older runs may lack skill tags.")

    return {
        "match_id": match.get("match_id"),
        "job_id": match.get("job_id"),
        "title": match.get("title"),
        "company": match.get("company"),
        "match_score": match.get("match_score"),
        "matched_skills": matched,
        "missing_skills": missing,
        "profile_skills": profile_skills,
        "overlap_count": len(matched),
        "gap_count": len(missing),
        "tips": tips,
        "auto_apply": False,
        "auto_send": False,
    }


def draft_cover_letter(
    profile: UserProfile,
    match: dict[str, Any],
    *,
    max_words: int = 280,
) -> dict[str, Any]:
    """Generate a cover-letter draft via Ollama. Returns text; never sends/applies."""
    name = (profile.name or "Candidate").strip()
    role = (profile.role or "").strip()
    skills = ", ".join((profile.skills or [])[:20]) or "see resume"
    exp = profile.experience_level or ""
    title = match.get("title") or "the role"
    company = match.get("company") or "the company"
    desc = (match.get("description") or "")[:2500]
    missing = ", ".join(match.get("missing_skills") or []) or "none noted"
    matched = ", ".join(match.get("matched_skills") or []) or "none noted"

    user = (
        f"Write a cover letter draft (about {max_words} words max) for:\n"
        f"Candidate: {name}\n"
        f"Target role on resume: {role}\n"
        f"Experience level: {exp}\n"
        f"Skills: {skills}\n\n"
        f"Job title: {title}\n"
        f"Company: {company}\n"
        f"Matched skills: {matched}\n"
        f"Missing skills (acknowledge carefully, do not fake): {missing}\n"
        f"Job description excerpt:\n{desc}\n\n"
        "Tone: confident, specific, human. End with a polite close. "
        "Do not include a postal address block."
    )
    text = call_ollama(_COVER_SYSTEM, user, temperature=0.4).strip()
    logger.info(
        f"Cover letter draft generated for match_id={match.get('match_id')} "
        f"(len={len(text)}); not sent, not applied"
    )
    return {
        "match_id": match.get("match_id"),
        "title": title,
        "company": company,
        "draft": text,
        "auto_apply": False,
        "auto_send": False,
        "disclaimer": (
            "Draft only — review and edit before you send. "
            "CareerPilot never emails/WhatsApps or applies for you."
        ),
    }
