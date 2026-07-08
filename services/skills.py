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
}

_WORD_RE = re.compile(r"[a-z0-9+#.]+", re.IGNORECASE)

# Titles that are almost never AIML/software roles for our users.
_EXCLUDED_TITLE_PATTERNS = [
    r"\bproposal\s+manager\b",
    r"\brisk\s+manager\b",
    r"\baccount\s+manager\b",
    r"\bsales\s+(?:manager|rep|executive)\b",
    r"\bmarketing\s+(?:manager|lead|director|operations)\b",
    r"\blifecycle\s+operations\b",
    r"\bcustomer\s+(?:support|success)\b",
    r"\brecruiter\b",
    r"\bhr\s+(?:manager|generalist)\b",
    r"\baccountant\b",
    r"\blawyer\b",
    r"\btruck\s+driver\b",
    r"\bnurse\b",
    r"\bcontent\s+writer\b",
    r"\bprogram\s+manager\b(?!.*\b(?:engineer|technical|ml|ai)\b)",
]

_TECH_TITLE_WORDS = frozenset(
    {
        "engineer",
        "developer",
        "scientist",
        "analyst",
        "architect",
        "programmer",
        "intern",
        "graduate",
        "researcher",
    }
)

_AIML_STRONG_TERMS = frozenset(
    {
        "ai",
        "ml",
        "aiml",
        "machine learning",
        "deep learning",
        "artificial intelligence",
        "nlp",
        "llm",
        "rag",
        "pytorch",
        "tensorflow",
        "langchain",
        "langgraph",
        "computer vision",
        "data scientist",
        "ml engineer",
        "ai engineer",
    }
)

_AIML_DOMAIN_TERMS = frozenset(
    {
        "ai",
        "ml",
        "machine",
        "learning",
        "deep",
        "nlp",
        "llm",
        "rag",
        "pytorch",
        "tensorflow",
        "computer",
        "vision",
        "scientist",
        "artificial",
        "aiml",
        "langchain",
        "langgraph",
    }
)

_SHORT_SKILL_TERMS = frozenset({"ai", "ml", "cv", "nlp", "llm", "rag", "dsa"})


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
    return out


def profile_skill_terms(profile: UserProfile) -> set[str]:
    terms: set[str] = set()
    for skill in profile.skills:
        terms.update(_expand_skill(skill))
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


def search_queries(profile: UserProfile) -> list[str]:
    """Distinct search strings for job board APIs (most specific first)."""
    from services.job_fields import effective_fields, search_queries_for_fields

    return search_queries_for_fields(effective_fields(profile), profile)


def _word_boundary_hit(term: str, haystack: str) -> bool:
    if len(term) < 2:
        return False
    if term in _SHORT_SKILL_TERMS:
        pattern = rf"\b{re.escape(term)}\b"
        return bool(re.search(pattern, haystack, re.IGNORECASE))
    if len(term) <= 2:
        return False
    pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, haystack, re.IGNORECASE))


def _aiml_hits(text: str) -> int:
    lowered = text.lower()
    hits = 0
    for term in _AIML_STRONG_TERMS:
        if " " in term:
            if term in lowered:
                hits += 1
        elif _word_boundary_hit(term, lowered):
            hits += 1
    return hits


def is_excluded_job_title(title: str) -> bool:
    lowered = (title or "").lower()
    return any(re.search(p, lowered) for p in _EXCLUDED_TITLE_PATTERNS)


def _profile_is_aiml_focused(profile: UserProfile) -> bool:
    blob = " ".join([*profile.preferred_roles, profile.role, *profile.skills]).lower()
    return any(
        term in blob
        for term in (
            "ai",
            "ml",
            "machine learning",
            "aiml",
            "llm",
            "deep learning",
            "pytorch",
            "tensorflow",
            "langchain",
        )
    )


def is_relevant_job_posting(job: JobListing, profile: UserProfile) -> bool:
    """Strict gate: is this job posting in the right domain for this profile?"""
    if is_excluded_job_title(job.title):
        return False

    if has_unrelated_enterprise_stack(job, profile):
        return False

    from services.job_fields import effective_fields, job_matches_any_field

    fields = effective_fields(profile)
    if job_matches_any_field(job, fields, profile):
        return True

    return role_relevant(job, profile)


def matches_scrape_keywords(job: JobListing, profile: UserProfile) -> bool:
    """Used during scraping to drop obvious noise before the filter stage."""
    return is_relevant_job_posting(job, profile)


def skill_hits_in_text(profile: UserProfile, text: str) -> int:
    haystack = text.lower()
    hits = 0
    seen: set[str] = set()
    for skill in profile.skills:
        for term in _expand_skill(skill):
            if term in seen:
                continue
            if _word_boundary_hit(term, haystack):
                hits += 1
                seen.add(term)
    return hits


_TECH_ROLE_WORDS = frozenset(
    {"engineer", "developer", "analyst", "scientist", "architect", "programmer"}
)


def role_relevant(job: JobListing, profile: UserProfile) -> bool:
    """Job title/description should align with target roles or core skills."""
    if is_excluded_job_title(job.title):
        return False

    haystack = f"{job.title} {job.description} {' '.join(job.skills)}".lower()
    roles = role_search_terms(profile)

    role_hit = any(
        _word_boundary_hit(token, haystack)
        for role in roles
        for token in _tokens(role)
        if len(token) >= 2
    )
    if role_hit:
        return True

    profile_role_text = " ".join(roles).lower()
    if any(w in haystack for w in _TECH_ROLE_WORDS) and any(
        w in profile_role_text for w in _TECH_ROLE_WORDS
    ):
        return True

    if skill_hits_in_text(profile, haystack) >= 2:
        return True

    return False


def has_unrelated_enterprise_stack(job: JobListing, profile: UserProfile) -> bool:
    """True when the job is dominated by enterprise tech the candidate does not have."""
    profile_terms = profile_skill_terms(profile)
    haystack = f"{job.title} {job.description} {' '.join(job.skills)}".lower()

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
    haystack = f"{job.title} {job.description} {' '.join(job.skills)}"
    if not profile.skills:
        return 0
    hits = skill_hits_in_text(profile, haystack)
    return min(100, int(100 * hits / max(len(profile.skills), 1)))
