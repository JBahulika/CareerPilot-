"""Deterministic skill and role relevance checks.

Complements embedding/LLM matching with word-boundary skill hits and blocks
obviously unrelated tech stacks (e.g. ABAP when the profile has no SAP/ABAP).
"""

from __future__ import annotations

import re

from models.schemas import JobListing, UserProfile

# Enterprise stacks that should not match unless the candidate lists them.
_UNRELATED_ENTERPRISE = frozenset(
    {
        "abap",
        "sap",
        "mainframe",
        "cobol",
        "peoplesoft",
        "workday",
        "salesforce admin",
        "dynamics 365",
    }
)

_SKILL_ALIASES: dict[str, list[str]] = {
    "ml": ["machine learning", "machine-learning"],
    "ai": ["artificial intelligence"],
    "nlp": ["natural language processing", "natural language"],
    "cv": ["computer vision"],
    "dsa": ["data structures", "algorithms"],
    "llm": ["large language model", "large language models"],
    "rag": ["retrieval augmented", "retrieval-augmented"],
    "js": ["javascript"],
    "ts": ["typescript"],
    "py": ["python"],
    "k8s": ["kubernetes"],
    "kube": ["kubernetes"],
    "postgres": ["postgresql"],
    "mongo": ["mongodb"],
    "tf": ["tensorflow"],
    "pt": ["pytorch"],
    "react.js": ["react"],
    "reactjs": ["react"],
    "node.js": ["nodejs", "node"],
    "next.js": ["nextjs"],
    "vue.js": ["vue"],
    "langchain": ["lang graph", "langgraph"],
    "fastapi": ["fast api"],
    "scikit-learn": ["sklearn"],
}

# Related skills — a hit on the job side counts if the profile has any related term.
_SKILL_RELATED: dict[str, list[str]] = {
    "react": ["javascript", "typescript", "frontend", "next.js", "nextjs"],
    "pytorch": ["python", "deep learning", "machine learning", "ml"],
    "tensorflow": ["python", "deep learning", "machine learning", "ml"],
    "langchain": ["python", "llm", "rag", "langgraph"],
    "fastapi": ["python", "rest", "api", "backend"],
    "django": ["python", "backend", "web"],
    "kubernetes": ["docker", "devops", "cloud"],
    "aws": ["cloud", "devops", "ec2", "s3"],
    "sql": ["postgresql", "mysql", "database"],
}

_WORD_RE = re.compile(r"[a-z0-9+#.]+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text or "") if len(t) > 1}


def _expand_skill(skill: str) -> set[str]:
    normalized = skill.strip().lower()
    if not normalized:
        return set()
    out = {normalized, *_tokens(normalized)}
    for token in list(out):
        for alias in _SKILL_ALIASES.get(token, []):
            out.add(alias.lower())
            out.update(_tokens(alias))
        for related in _SKILL_RELATED.get(token, []):
            out.add(related.lower())
            out.update(_tokens(related))
    return out


def normalize_skill(skill: str) -> str:
    """Return a canonical lowercase form for display/comparison."""
    key = skill.strip().lower()
    for canonical, aliases in _SKILL_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    return key


def profile_skill_terms(profile: UserProfile) -> set[str]:
    terms: set[str] = set()
    for skill in profile.all_skills():
        terms.update(_expand_skill(skill))
    for exp in profile.experience:
        for tech in exp.technologies:
            terms.update(_expand_skill(tech))
    for project in profile.projects:
        for tech in project.tech_stack:
            terms.update(_expand_skill(tech))
    for role in (*profile.preferred_roles, profile.role):
        terms.update(_tokens(role))
    return terms


def role_search_terms(profile: UserProfile) -> list[str]:
    """Primary role phrases used for scraper queries and relevance."""
    roles = [r.strip() for r in profile.preferred_roles if r.strip()]
    if not roles and profile.role.strip():
        roles = [profile.role.strip()]
    if not roles:
        roles = ["software engineer"]
    return roles


def _word_boundary_hit(term: str, haystack: str) -> bool:
    if len(term) <= 2:
        return False
    pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, haystack, re.IGNORECASE))


def skill_hits_in_text(profile: UserProfile, text: str) -> int:
    haystack = text.lower()
    hits = 0
    seen: set[str] = set()
    for skill in profile.all_skills():
        for term in _expand_skill(skill):
            if term in seen:
                continue
            if _word_boundary_hit(term, haystack):
                hits += 1
                seen.add(term)
                break
    return hits


_TECH_ROLE_WORDS = frozenset(
    {"engineer", "developer", "analyst", "scientist", "architect", "programmer"}
)


def role_relevant(job: JobListing, profile: UserProfile) -> bool:
    """Job title/description should align with target roles or core skills."""
    haystack = (
        f"{job.title} {job.description} {job.requirements} {' '.join(job.skills)}"
    ).lower()
    roles = role_search_terms(profile)

    role_hit = any(
        _word_boundary_hit(token, haystack)
        for role in roles
        for token in _tokens(role)
        if len(token) > 2
    )
    if role_hit:
        return True

    profile_role_text = " ".join(roles).lower()
    if any(w in haystack for w in _TECH_ROLE_WORDS) and any(
        w in profile_role_text for w in _TECH_ROLE_WORDS
    ):
        return True

    return skill_hits_in_text(profile, haystack) >= 2


def has_unrelated_enterprise_stack(job: JobListing, profile: UserProfile) -> bool:
    """True when the job is dominated by enterprise tech the candidate does not have."""
    profile_terms = profile_skill_terms(profile)
    haystack = (
        f"{job.title} {job.description} {job.requirements} {' '.join(job.skills)}"
    ).lower()

    for stack in _UNRELATED_ENTERPRISE:
        if stack not in haystack:
            continue
        if stack in profile_terms:
            continue
        if any(stack in term for term in profile_terms):
            continue
        return True
    return False


def filter_matched_skills(profile: UserProfile, claimed: list[str]) -> list[str]:
    """Keep only LLM-claimed skills that truthfully exist on the profile."""
    profile_terms = profile_skill_terms(profile)
    kept: list[str] = []
    for skill in claimed:
        skill_terms = _expand_skill(skill)
        if skill_terms & profile_terms:
            kept.append(skill)
    return kept


def deterministic_skill_overlap(profile: UserProfile, job: JobListing) -> int:
    """0-100 score from word-boundary skill overlap between profile and job."""
    haystack = (
        f"{job.title} {job.description} {job.requirements} {' '.join(job.skills)}"
    )
    skills = profile.all_skills()
    if not skills:
        return 0
    hits = skill_hits_in_text(profile, haystack)
    return min(100, int(100 * hits / max(len(skills), 1)))
