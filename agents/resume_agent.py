"""Resume Tailoring Agent (FR-5).

Rewrites the master resume for a specific job while enforcing truthfulness:
the LLM may only rephrase/reorder/emphasize existing content. A post-generation
guardrail flags any employer or skill that does not appear in the source resume.
"""

from __future__ import annotations

import re

from agents.base import call_ollama_json
from core.logging import get_logger
from models.schemas import (
    Experience,
    JobListing,
    TailoredResume,
    UserProfile,
)
from prompts.templates import RESUME_TAILOR_SYSTEM

logger = get_logger(__name__)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9\+\#\.]+", text.lower()))


class ResumeTailorAgent:
    def run(
        self, profile: UserProfile, job: JobListing
    ) -> TailoredResume:
        data = call_ollama_json(
            RESUME_TAILOR_SYSTEM, self._user_prompt(profile, job)
        )

        try:
            tailored = TailoredResume.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Tailoring validation failed, using source profile: {exc}")
            tailored = self._fallback(profile)

        self._enforce_truthfulness(tailored, profile)
        return tailored

    @staticmethod
    def _user_prompt(profile: UserProfile, job: JobListing) -> str:
        source = profile.model_dump()
        return (
            "SOURCE RESUME (the only facts you may use):\n"
            f"{source}\n\n"
            "TARGET JOB:\n"
            f"{job.match_text()[:5000]}\n\n"
            "Tailor the resume for this job following all integrity rules."
        )

    @staticmethod
    def _fallback(profile: UserProfile) -> TailoredResume:
        return TailoredResume(
            name=profile.name,
            contact=f"{profile.email} | {profile.phone} | {profile.location}",
            summary=f"{profile.role} with skills in {', '.join(profile.skills[:6])}.",
            skills=profile.skills,
            experience=profile.experience,
            projects=profile.projects,
            education=profile.education,
            certifications=profile.certifications,
        )

    def _enforce_truthfulness(
        self, tailored: TailoredResume, profile: UserProfile
    ) -> None:
        """Drop fabricated employers/skills not present in the source resume."""
        source_tokens = _tokenize(profile.summary_text() + " " + str(profile.model_dump()))

        # Skills must exist (token-level) in the source.
        allowed_skills = []
        for skill in tailored.skills:
            if _tokenize(skill) & source_tokens or not source_tokens:
                allowed_skills.append(skill)
            else:
                logger.warning(f"Removed fabricated skill from tailored resume: {skill}")
        tailored.skills = allowed_skills or profile.skills

        # Employers must match a source employer.
        source_companies = {e.company.lower() for e in profile.experience if e.company}
        if source_companies:
            valid_experience: list[Experience] = []
            for exp in tailored.experience:
                if not exp.company or exp.company.lower() in source_companies:
                    valid_experience.append(exp)
                else:
                    logger.warning(
                        f"Removed fabricated employer from tailored resume: {exp.company}"
                    )
            tailored.experience = valid_experience or profile.experience
