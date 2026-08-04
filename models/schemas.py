"""Pydantic schemas shared across agents, the API, and the UI.

These are the data contracts that flow through the pipeline. They are kept
separate from the SQLModel database tables (``database/models.py``) so agent
logic never depends on persistence details.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

_JOB_BOILERPLATE_RE = re.compile(
    r"(equal opportunity|eeo|affirmative action|background check|"
    r"we are an equal|privacy policy|accommodation)",
    re.IGNORECASE,
)


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    url: str = ""
    role: str = ""


class Experience(BaseModel):
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str = ""
    start_date: str = ""  # YYYY-MM when known
    end_date: str = ""  # YYYY-MM or empty when current
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """Structured profile extracted from a master resume (FR-2)."""

    name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    summary: str = ""
    experience_level: str = "Fresher"  # e.g. "Fresher", "1-3 years"
    skills: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_location: str = ""
    include_remote: bool = True
    target_years_min: Optional[int] = None
    target_years_max: Optional[int] = None
    # Pipeline preferences (saved on Profile, used by Run Pipeline defaults)
    strict_experience: bool = True
    allow_stretch: bool = False
    flex_years: Optional[int] = None
    exclude_internships: bool = False
    min_match_score: int = 60  # 0–100; only notify/tailor matches at or above

    def all_skills(self) -> list[str]:
        """Technical skills plus legacy flat skills list (deduplicated)."""
        seen: set[str] = set()
        ordered: list[str] = []
        for skill in [*self.technical_skills, *self.skills]:
            key = skill.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(skill.strip())
        return ordered

    def experience_tier(self) -> int:
        """Numeric seniority tier (0=intern/fresher .. 5=executive)."""
        from services.seniority import infer_candidate_tier

        return infer_candidate_tier(self)

    def summary_text(self) -> str:
        """Compact text for LLM prompts and UI display."""
        from services.seniority import candidate_tier_label

        skills = self.all_skills()
        parts = [
            f"Role: {self.role}",
            f"Summary: {self.summary}" if self.summary else "",
            f"Experience: {self.experience_level}",
            f"Seniority: {candidate_tier_label(self.experience_tier())}",
            f"Target years: {self.target_years_min or 'auto'}-{self.target_years_max or 'auto'}",
            f"Skills: {', '.join(skills)}",
            f"Domains: {', '.join(self.domains)}" if self.domains else "",
            f"Preferred roles: {', '.join(self.preferred_roles)}",
            f"Location: {self.preferred_location or self.location}",
        ]
        for project in self.projects[:6]:
            stack = ", ".join(project.tech_stack) if project.tech_stack else ""
            line = f"Project: {project.name}"
            if stack:
                line += f" [{stack}]"
            if project.description:
                line += f" — {project.description[:300]}"
            parts.append(line)
        for exp in self.experience[:6]:
            tech = ", ".join(exp.technologies) if exp.technologies else ""
            line = f"Experience: {exp.title} at {exp.company}"
            if exp.duration:
                line += f" ({exp.duration})"
            if tech:
                line += f" [{tech}]"
            body = exp.description or "; ".join(exp.bullets[:4])
            if body:
                line += f" — {body[:400]}"
            parts.append(line)
        return "\n".join(p for p in parts if p)

    def embedding_query_text(self) -> str:
        """Retrieval-optimized candidate text (prefixed for BGE in embeddings service)."""
        skills = self.all_skills()
        roles = self.preferred_roles or ([self.role] if self.role else [])
        parts = [
            " | ".join(roles[:4]) if roles else self.role,
            f"Experience level: {self.experience_level}",
            f"Skills: {', '.join(skills[:40])}",
        ]
        if self.domains:
            parts.append(f"Domains: {', '.join(self.domains[:8])}")
        if self.summary:
            parts.append(self.summary[:500])
        for exp in self.experience[:4]:
            snippet = exp.title
            if exp.technologies:
                snippet += f" ({', '.join(exp.technologies[:8])})"
            elif exp.description:
                snippet += f" ({exp.description[:120]})"
            parts.append(snippet)
        for project in self.projects[:3]:
            stack = ", ".join(project.tech_stack[:8]) if project.tech_stack else ""
            parts.append(f"{project.name} {stack}".strip())
        return ". ".join(p for p in parts if p.strip())


class JobListing(BaseModel):
    """A normalized job from any source."""

    source: str = ""
    company: str = ""
    title: str = ""
    description: str = ""
    requirements: str = ""
    nice_to_have: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: str = ""
    required_years_min: Optional[int] = None
    seniority_tier: Optional[int] = None
    employment_type: str = ""
    remote_policy: str = ""
    location: str = ""
    salary: str = ""
    apply_url: str = ""
    content_hash: str = ""
    posted_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    def _trim_description(self, limit: int = 4000) -> str:
        body = self.requirements or self.description
        if self.requirements and self.description and self.description not in self.requirements:
            body = f"{self.requirements}\n{self.description}"
        body = _JOB_BOILERPLATE_RE.sub(" ", body or "")
        return " ".join(body.split())[:limit]

    def match_text(self) -> str:
        """Text used for LLM matching and display."""
        seniority = self.experience or "Not specified"
        parts = [
            f"{self.title} at {self.company}",
            f"Seniority: {seniority}",
            f"Location: {self.location}",
        ]
        if self.employment_type:
            parts.append(f"Type: {self.employment_type}")
        if self.remote_policy:
            parts.append(f"Remote: {self.remote_policy}")
        if self.skills:
            parts.append(f"Skills: {', '.join(self.skills)}")
        if self.requirements:
            parts.append(f"Requirements: {self.requirements[:3000]}")
        if self.nice_to_have:
            parts.append(f"Nice to have: {self.nice_to_have[:1500]}")
        parts.append(self._trim_description())
        return "\n".join(parts)

    def embedding_passage_text(self) -> str:
        """Retrieval-optimized job text (prefixed for BGE in embeddings service)."""
        parts = [f"{self.title} at {self.company}"]
        if self.experience:
            parts.append(self.experience)
        if self.required_years_min is not None:
            parts.append(f"{self.required_years_min}+ years")
        if self.skills:
            parts.append(", ".join(self.skills[:30]))
        if self.requirements:
            parts.append(self.requirements[:2000])
        else:
            parts.append(self._trim_description(2500))
        if self.nice_to_have:
            parts.append(self.nice_to_have[:800])
        return ". ".join(p for p in parts if p.strip())


class Recommendation(str, Enum):
    HIGHLY_RECOMMENDED = "Highly Recommended"
    CONSIDER = "Consider"
    SKIP = "Skip"


class MatchResult(BaseModel):
    """Explainable match between a profile and a job (FR-4)."""

    job: JobListing
    match_score: int = 0  # 0-100
    embed_score: float = 0.0
    skill_score: float = 0.0
    rerank_score: float = 0.0
    llm_score: float = 0.0
    seniority_compatible: bool = True
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
