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


# Soft-skill / culture fluff — never show these as "missing skills".
_SOFT_SKILL_DENY = frozenset(
    {
        "communication",
        "communicate",
        "communicator",
        "english",
        "fluency",
        "fluent",
        "reliability",
        "reliable",
        "dependable",
        "self-organizational",
        "self-organisation",
        "self-organization",
        "organizational",
        "organisation",
        "organization",
        "team player",
        "teamwork",
        "collaborative",
        "collaboration",
        "passionate",
        "passion",
        "motivated",
        "self-motivated",
        "proactive",
        "detail-oriented",
        "details oriented",
        "culture fit",
        "cultural fit",
        "ownership",
        "accountability",
        "attitude",
        "mindset",
        "soft skill",
        "soft skills",
        "interpersonal",
        "written communication",
        "verbal communication",
        "problem solving",
        "problem-solving",
        "critical thinking",
        "time management",
        "multitask",
        "multi-task",
        "work ethic",
        "positive attitude",
        "fast learner",
        "quick learner",
        "independent",
        "autonomous",
        "self starter",
        "self-starter",
    }
)

# Sales / GTM / partner process — not technical stack gaps.
_SALES_PROCESS_DENY = frozenset(
    {
        "solution selling",
        "solutions selling",
        "pre-sales",
        "presales",
        "pre sales",
        "post-sales",
        "postsales",
        "post sales",
        "champion building",
        "champion-building",
        "partner enablement",
        "partner solutions",
        "account management",
        "account manager",
        "business development",
        "relationship building",
        "stakeholder management",
        "customer success",
        "quota",
        "pipeline",
        "evangelism",
        "evangelist",
        "gtm",
        "go-to-market",
        "go to market",
        "sales engineering activities",
        "selling skills",
        "sales methodology",
        "consultative selling",
        "opportunity management",
        "rfp",
        "proposal writing",
    }
)

# Concrete tech/product tokens — keep even if phrase is long.
_TECH_TOKEN_RE = re.compile(
    r"(?:"
    r"sase|sse|ztna|casb|swg|"
    r"python|java|kotlin|golang|go\b|rust|ruby|scala|typescript|javascript|"
    r"node\.?js|react|vue|angular|fastapi|django|flask|"
    r"pytorch|tensorflow|keras|scikit|sklearn|xgboost|huggingface|"
    r"aws|gcp|azure|databricks|snowflake|spark|kafka|airflow|"
    r"docker|kubernetes|k8s|terraform|ansible|"
    r"mlflow|unity catalog|delta lake|dbt|tableau|power bi|"
    r"postgresql|mysql|mongodb|redis|elasticsearch|"
    r"langchain|langgraph|openai|llm|rag|nlp|opencv|"
    r"c\+\+|sql|nosql|graphql|rest api"
    r")",
    re.IGNORECASE,
)

_YEARS_GAP_RE = re.compile(
    r"\d+\s*\+?\s*years?|\bseniority\b|\bexperience\b.*\byears?\b",
    re.IGNORECASE,
)

_SALES_ROLE_TITLE_RE = re.compile(
    r"\b("
    r"pre[\s-]?sales|post[\s-]?sales|sales engineer|"
    r"solutions? engineer|partner solutions|solution selling|"
    r"account executive|business development|customer success|"
    r"sales manager"
    r")\b",
    re.IGNORECASE,
)

_AIML_IC_RE = re.compile(
    r"\b("
    r"machine learning|deep learning|data scien|ml engineer|ai engineer|"
    r"artificial intelligence|computer vision|nlp|llm|pytorch|tensorflow|"
    r"aiml|ai/ml"
    r")\b",
    re.IGNORECASE,
)


def _has_tech_token(text: str) -> bool:
    return bool(_TECH_TOKEN_RE.search(text or ""))


def _is_sales_process_phrase(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(deny in lowered for deny in _SALES_PROCESS_DENY):
        # Keep pure tech tokens like "SASE/SSE" even if nearby fluff was concatenated
        if _has_tech_token(lowered) and not any(
            s in lowered
            for s in (
                "selling",
                "champion",
                "pre-sales",
                "presales",
                "post-sales",
                "postsales",
                "enablement",
            )
        ):
            return False
        # Mixed "SASE and solution selling" → drop whole claim (LLM should list SASE alone)
        if any(
            s in lowered
            for s in (
                "selling",
                "champion",
                "pre-sales",
                "presales",
                "post-sales",
                "postsales",
                "enablement",
                "account management",
                "business development",
            )
        ):
            return True
        return True
    return False


def _is_soft_skill_phrase(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return True
    if any(deny in lowered for deny in _SOFT_SKILL_DENY):
        return True
    if _is_sales_process_phrase(lowered):
        return True
    # Long prose JD sentences without tech tokens → likely soft/process fluff
    if len(lowered) > 60 and not _has_tech_token(lowered) and not _YEARS_GAP_RE.search(
        lowered
    ):
        return True
    return False


def is_sales_or_gtm_role(job: JobListing) -> bool:
    """True for sales / pre-sales / partner solutions / CS-style titles."""
    title = job.title or ""
    return bool(_SALES_ROLE_TITLE_RE.search(title))


def profile_is_technical_ic(profile: UserProfile) -> bool:
    """Heuristic: AI/ML/data IC profile without sales domain markers."""
    blob = " ".join(
        [
            profile.role or "",
            " ".join(profile.preferred_roles),
            " ".join(profile.skills),
            " ".join(profile.technical_skills),
            " ".join(profile.domains),
            profile.summary or "",
        ]
    )
    if _SALES_ROLE_TITLE_RE.search(blob):
        return False
    if any(
        t in blob.lower()
        for t in ("pre-sales", "presales", "sales engineer", "account executive")
    ):
        return False
    return bool(_AIML_IC_RE.search(blob))


def is_senior_leadership_title(job: JobListing) -> bool:
    """Principal / Lead / Staff / Director — too senior for entry candidates."""
    title = (job.title or "").lower()
    return bool(
        re.search(
            r"\b(principal|staff|director|vp|vice president|head of|partner)\b",
            title,
        )
        or re.search(r"\blead\b", title)
    )


def _profile_covers_missing(profile: UserProfile, claim: str) -> bool:
    """True when the candidate already lists this (e.g. English on resume)."""
    lowered = claim.strip().lower()
    if not lowered:
        return True
    blob = " ".join(
        [
            profile.summary or "",
            " ".join(profile.soft_skills),
            " ".join(profile.skills),
            " ".join(profile.technical_skills),
            " ".join(profile.certifications),
            profile.summary_text(),
        ]
    ).lower()
    if "english" in lowered and "english" in blob:
        return True
    claim_terms = _expand_skill(claim)
    if claim_terms & profile_skill_terms(profile):
        return True
    return False


def filter_missing_skills(profile: UserProfile, claimed: list[str]) -> list[str]:
    """Keep technical/experience gaps only — drop soft skills and fluff."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw in claimed:
        skill = (raw or "").strip()
        if not skill:
            continue
        key = skill.lower()
        if key in seen:
            continue
        if _is_soft_skill_phrase(skill):
            continue
        if _profile_covers_missing(profile, skill):
            continue
        # Prefer short tokens; trim overly long JD copy but keep years gaps
        if len(skill) > 60 and not _YEARS_GAP_RE.search(skill):
            continue
        seen.add(key)
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
