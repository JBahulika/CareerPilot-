"""Job field taxonomy for multi-field search and relevance filtering.

Each field maps to scraper search terms and deterministic relevance keywords.
Users may select multiple fields; a job passes when it matches ANY selected field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from models.schemas import JobListing, UserProfile

_WORD_RE = re.compile(r"[a-z0-9+#.]+", re.IGNORECASE)
_SHORT_TERMS = frozenset({"ai", "ml", "cv", "nlp", "llm", "rag", "qa", "ui", "ux"})

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
        "tester",
    }
)


@dataclass(frozen=True)
class JobFieldDef:
    id: str
    label: str
    search_terms: tuple[str, ...]
    keywords: tuple[str, ...]
    infer_signals: tuple[str, ...]


JOB_FIELDS: dict[str, JobFieldDef] = {
    "aiml": JobFieldDef(
        id="aiml",
        label="AI / Machine Learning",
        search_terms=(
            "machine learning engineer",
            "AI engineer",
            "ML engineer",
            "deep learning engineer",
            "NLP engineer",
            "LLM engineer",
        ),
        keywords=(
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
        ),
        infer_signals=(
            "ai engineer",
            "ml engineer",
            "machine learning",
            "deep learning",
            "pytorch",
            "tensorflow",
            "langchain",
            "llm",
            "nlp",
            "aiml",
        ),
    ),
    "data_science": JobFieldDef(
        id="data_science",
        label="Data Science",
        search_terms=("data scientist", "analytics engineer", "data analyst"),
        keywords=(
            "data scientist",
            "data science",
            "analytics",
            "statistics",
            "data analyst",
            "business intelligence",
        ),
        infer_signals=("data scientist", "data science", "analytics", "statistics"),
    ),
    "backend": JobFieldDef(
        id="backend",
        label="Backend Engineering",
        search_terms=("backend engineer", "python developer", "java developer"),
        keywords=(
            "backend",
            "back-end",
            "api",
            "microservices",
            "django",
            "flask",
            "fastapi",
            "node.js",
            "spring boot",
        ),
        infer_signals=("backend", "api developer", "django", "flask", "fastapi"),
    ),
    "frontend": JobFieldDef(
        id="frontend",
        label="Frontend Engineering",
        search_terms=("frontend engineer", "react developer", "ui developer"),
        keywords=(
            "frontend",
            "front-end",
            "react",
            "vue",
            "angular",
            "typescript",
            "javascript",
            "ui engineer",
        ),
        infer_signals=("frontend", "react", "vue", "angular", "ui developer"),
    ),
    "fullstack": JobFieldDef(
        id="fullstack",
        label="Full Stack",
        search_terms=("full stack engineer", "fullstack developer"),
        keywords=("full stack", "fullstack", "full-stack"),
        infer_signals=("full stack", "fullstack", "full-stack"),
    ),
    "devops": JobFieldDef(
        id="devops",
        label="DevOps / SRE",
        search_terms=("devops engineer", "site reliability engineer", "platform engineer"),
        keywords=(
            "devops",
            "sre",
            "site reliability",
            "kubernetes",
            "docker",
            "ci/cd",
            "terraform",
            "ansible",
        ),
        infer_signals=("devops", "sre", "kubernetes", "terraform", "ci/cd"),
    ),
    "mobile": JobFieldDef(
        id="mobile",
        label="Mobile Development",
        search_terms=("android developer", "ios engineer", "mobile developer"),
        keywords=("android", "ios", "flutter", "react native", "kotlin", "swift", "mobile"),
        infer_signals=("android", "ios", "flutter", "react native", "mobile developer"),
    ),
    "cloud": JobFieldDef(
        id="cloud",
        label="Cloud / Infrastructure",
        search_terms=("cloud engineer", "cloud architect", "infrastructure engineer"),
        keywords=("aws", "gcp", "azure", "cloud engineer", "cloud architect", "infrastructure"),
        infer_signals=("aws", "gcp", "azure", "cloud engineer", "cloud architect"),
    ),
    "qa": JobFieldDef(
        id="qa",
        label="QA / Testing",
        search_terms=("qa engineer", "test automation engineer", "sdet"),
        keywords=(
            "qa engineer",
            "quality assurance",
            "test automation",
            "selenium",
            "sdet",
            "software tester",
        ),
        infer_signals=("qa", "test automation", "selenium", "sdet", "quality assurance"),
    ),
    "software": JobFieldDef(
        id="software",
        label="General Software",
        search_terms=("software engineer", "software developer"),
        keywords=("software engineer", "software developer", "engineer", "developer"),
        infer_signals=(),
    ),
}

JOB_FIELD_OPTIONS: list[dict[str, str]] = [
    {"id": f.id, "label": f.label} for f in JOB_FIELDS.values()
]

# When matching AIML, reject titles dominated by other engineering domains.
_AIML_EXCLUDED_TITLE_PATTERNS = (
    r"\bfrontend\b",
    r"\bquality\s+engineer\b",
    r"\bqa\s+engineer\b",
    r"\bfull[\s-]?stack\b",
    r"\brails\b",
    r"\bdevops\b",
    r"\bsre\b",
    r"\bproduct\s+engineer\b",
)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text or "") if len(t) > 1}


def _word_boundary_hit(term: str, haystack: str) -> bool:
    if len(term) < 2:
        return False
    if term in _SHORT_TERMS:
        return bool(re.search(rf"\b{re.escape(term)}\b", haystack, re.IGNORECASE))
    if len(term) <= 2:
        return False
    return bool(re.search(rf"\b{re.escape(term)}\b", haystack, re.IGNORECASE))


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lowered = text.lower()
    hits = 0
    for term in keywords:
        if " " in term:
            if term in lowered:
                hits += 1
        elif _word_boundary_hit(term, lowered):
            hits += 1
    return hits


def _has_tech_title(title: str) -> bool:
    return any(_word_boundary_hit(w, title) for w in _TECH_TITLE_WORDS)


def _profile_blob(profile: UserProfile) -> str:
    return " ".join(
        [
            profile.role,
            *profile.preferred_roles,
            *profile.skills,
            *[p.name for p in profile.projects],
            *[e.title for e in profile.experience],
        ]
    ).lower()


def infer_fields_from_profile(profile: UserProfile) -> list[str]:
    """Guess job fields from resume content. Falls back to general software."""
    blob = _profile_blob(profile)
    matched: list[str] = []
    for field in JOB_FIELDS.values():
        if field.id == "software":
            continue
        if any(signal in blob for signal in field.infer_signals):
            matched.append(field.id)
    if not matched:
        matched = ["software"]
    return matched


def effective_fields(profile: UserProfile) -> list[str]:
    """User-selected fields, or inferred when unset."""
    selected = [f for f in profile.preferred_fields if f in JOB_FIELDS]
    if selected:
        return selected
    return infer_fields_from_profile(profile)


def field_labels(fields: list[str]) -> list[str]:
    return [JOB_FIELDS[f].label for f in fields if f in JOB_FIELDS]


def search_queries_for_fields(fields: list[str], profile: UserProfile) -> list[str]:
    """Union of role phrases and field search terms, deduped."""
    roles = [r.strip() for r in profile.preferred_roles if r.strip()]
    if not roles and profile.role.strip():
        roles = [profile.role.strip()]
    if not roles:
        roles = ["software engineer"]

    queries: list[str] = list(roles)
    for field_id in fields:
        field = JOB_FIELDS.get(field_id)
        if field:
            queries.extend(field.search_terms)

    if "aiml" in fields:
        from services.seniority import infer_candidate_tier

        tier = infer_candidate_tier(profile)
        if tier <= 1:
            queries.extend(
                [
                    "junior machine learning engineer",
                    "graduate AI engineer",
                    "entry level ML engineer",
                ]
            )

    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(q.strip())
    return out


def _job_matches_field(job: JobListing, field_id: str, profile: UserProfile) -> bool:
    field = JOB_FIELDS.get(field_id)
    if not field:
        return False

    title = (job.title or "").lower()
    haystack = f"{job.title} {job.description} {' '.join(job.skills)}".lower()

    if field_id == "aiml":
        if _keyword_hits(title, field.keywords) == 0 and any(
            re.search(p, title) for p in _AIML_EXCLUDED_TITLE_PATTERNS
        ):
            return False
        title_hits = _keyword_hits(job.title, field.keywords)
        if title_hits >= 1 and _has_tech_title(title):
            return True
        for role in profile.preferred_roles + ([profile.role] if profile.role else []):
            role_lower = role.lower().strip()
            if len(role_lower) > 5 and role_lower in title:
                return True
            role_tokens = [t for t in _tokens(role) if len(t) >= 2]
            if len(role_tokens) >= 2 and all(_word_boundary_hit(t, title) for t in role_tokens[:3]):
                return True
        if _word_boundary_hit("ml", title) or "machine learning" in title:
            return _has_tech_title(title)
        return _keyword_hits(haystack, field.keywords) >= 2

    if field_id == "software":
        if _has_tech_title(title):
            return True
        return _keyword_hits(haystack, field.keywords) >= 1

    title_hits = _keyword_hits(job.title, field.keywords)
    if title_hits >= 1:
        return True
    if _keyword_hits(haystack, field.keywords) >= 2:
        return True

    for role in profile.preferred_roles + ([profile.role] if profile.role else []):
        role_tokens = [t for t in _tokens(role) if len(t) >= 2]
        if role_tokens and all(_word_boundary_hit(t, haystack) for t in role_tokens[:3]):
            field_tokens = [t for t in _tokens(field.label) if len(t) >= 3]
            if field_tokens and any(_word_boundary_hit(t, haystack) for t in field_tokens):
                return True

    return False


def job_matches_any_field(
    job: JobListing, fields: list[str], profile: UserProfile
) -> bool:
    """OR logic: job is relevant if it matches any selected field."""
    if not fields:
        return False
    return any(_job_matches_field(job, field_id, profile) for field_id in fields)


def title_relevance_for_fields(job: JobListing, fields: list[str]) -> float:
    """0-1 title relevance score against selected fields (best field wins)."""
    title = (job.title or "").lower()
    if not title or not fields:
        return 0.0

    best = 0.0
    for field_id in fields:
        field = JOB_FIELDS.get(field_id)
        if not field:
            continue
        hits = _keyword_hits(job.title, field.keywords)
        if hits >= 2:
            best = max(best, 0.95)
        elif hits == 1:
            best = max(best, 0.8)
        elif field_id == "software" and _has_tech_title(title):
            best = max(best, 0.7)
        for term in field.keywords:
            if " " in term and term in title:
                best = max(best, 1.0)
    return best
