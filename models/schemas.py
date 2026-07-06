"""Pydantic schemas shared across agents, the API, and the UI.

These are the data contracts that flow through the pipeline. They are kept
separate from the SQLModel database tables (``database/models.py``) so agent
logic never depends on persistence details.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str = ""


class UserProfile(BaseModel):
    """Structured profile extracted from a master resume (FR-2)."""

    name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    experience_level: str = "Fresher"  # e.g. "Fresher", "1-3 years"
    skills: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_location: str = ""

    def experience_tier(self) -> int:
        """Numeric seniority tier (0=intern/fresher .. 5=executive)."""
        from services.seniority import infer_candidate_tier

        return infer_candidate_tier(self)

    def summary_text(self) -> str:
        """Compact text used for embedding the profile."""
        from services.seniority import candidate_tier_label

        parts = [
            f"Role: {self.role}",
            f"Experience: {self.experience_level}",
            f"Seniority: {candidate_tier_label(self.experience_tier())}",
            f"Skills: {', '.join(self.skills)}",
            f"Preferred roles: {', '.join(self.preferred_roles)}",
            f"Location: {self.preferred_location or self.location}",
        ]
        for project in self.projects:
            parts.append(f"Project: {project.name} - {project.description}")
        for exp in self.experience:
            parts.append(f"Experience: {exp.title} at {exp.company} - {exp.description}")
        return "\n".join(parts)


class JobListing(BaseModel):
    """A normalized job from any source."""

    source: str = ""
    company: str = ""
    title: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: str = ""
    location: str = ""
    salary: str = ""
    apply_url: str = ""
    content_hash: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    def match_text(self) -> str:
        """Text used for embedding and LLM matching."""
        seniority = self.experience or "Not specified"
        return (
            f"{self.title} at {self.company}\n"
            f"Seniority: {seniority}\n"
            f"Location: {self.location}\n"
            f"Skills: {', '.join(self.skills)}\n"
            f"{self.description}"
        )


class Recommendation(str, Enum):
    HIGHLY_RECOMMENDED = "Highly Recommended"
    CONSIDER = "Consider"
    SKIP = "Skip"


class MatchResult(BaseModel):
    """Explainable match between a profile and a job (FR-4)."""

    job: JobListing
    match_score: int = 0  # 0-100
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    recommendation: Recommendation = Recommendation.CONSIDER
    generated_pdf_path: Optional[str] = None


class TailoredResume(BaseModel):
    """Structured, ATS-friendly resume produced for a specific job (FR-5)."""

    name: str = ""
    contact: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
