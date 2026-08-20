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


# Optional Profile/Run dropdown: narrow discovery to a career field.
# id "" / "any" = skill-first across all tech roles.
# Base labels/search come from services.job_fields; overlays add role/skill hints.
_FOCUS_OVERLAYS: dict[str, dict[str, object]] = {
    "aiml": {
        "roles": (
            "AI Engineer",
            "ML Engineer",
            "Machine Learning Engineer",
            "NLP Engineer",
            "Computer Vision Engineer",
            "MLOps Engineer",
            "Applied Scientist",
            "Research Scientist",
        ),
        "skill_hints": (
            "pytorch",
            "tensorflow",
            "machine learning",
            "deep learning",
            "langchain",
            "llm",
            "nlp",
            "opencv",
            "transformers",
            "scikit-learn",
            "rag",
        ),
        "title_hints": (
            "ai engineer",
            "ml engineer",
            "machine learning",
            "deep learning",
            "nlp",
            "computer vision",
            "mlops",
            "llm",
            "applied scientist",
            "research scientist",
        ),
    },
    "data_science": {
        "roles": (
            "Data Scientist",
            "Applied Scientist",
            "Research Scientist",
            "ML Engineer",
        ),
        "skill_hints": (
            "python",
            "pandas",
            "numpy",
            "scikit-learn",
            "statistics",
            "machine learning",
            "sql",
            "pytorch",
            "tensorflow",
        ),
        "title_hints": (
            "data scientist",
            "applied scientist",
            "research scientist",
            "machine learning",
        ),
    },
    "data_analytics": {
        "roles": (
            "Data Analyst",
            "Business Intelligence Analyst",
            "Analytics Engineer",
            "BI Developer",
        ),
        "skill_hints": (
            "sql",
            "tableau",
            "power bi",
            "excel",
            "pandas",
            "looker",
            "dbt",
            "analytics",
        ),
        "title_hints": (
            "data analyst",
            "business intelligence",
            "analytics engineer",
            "bi analyst",
            "bi developer",
        ),
    },
    "data_engineering": {
        "roles": (
            "Data Engineer",
            "Analytics Engineer",
            "ETL Developer",
        ),
        "skill_hints": (
            "spark",
            "airflow",
            "kafka",
            "sql",
            "etl",
            "snowflake",
            "databricks",
            "dbt",
            "python",
        ),
        "title_hints": (
            "data engineer",
            "analytics engineer",
            "etl",
            "pipeline",
        ),
    },
    "software": {
        "roles": (
            "Software Engineer",
            "Backend Engineer",
            "Full Stack Developer",
            "Python Developer",
            "API Developer",
        ),
        "skill_hints": (
            "python",
            "fastapi",
            "django",
            "javascript",
            "typescript",
            "react",
            "java",
            "docker",
            "aws",
        ),
        "title_hints": (
            "software engineer",
            "backend",
            "full stack",
            "fullstack",
            "python developer",
            "web developer",
        ),
    },
    "backend": {
        "roles": ("Backend Engineer", "Python Developer", "API Developer"),
        "skill_hints": ("python", "fastapi", "django", "flask", "java", "node"),
        "title_hints": ("backend", "back-end", "api developer", "python developer"),
    },
}


def focus_field_options() -> list[dict[str, str]]:
    """UI-friendly id/label pairs for the focus-field dropdown."""
    from services.job_fields import JOB_FIELD_OPTIONS

    return [
        {"id": "any", "label": "Any (skill-first — all matching skills)"},
        *JOB_FIELD_OPTIONS,
    ]


def normalize_focus_field(value: str | None) -> str:
    from services.job_fields import JOB_FIELDS

    raw = (value or "").strip().lower()
    if not raw or raw in {"any", "all", "none"}:
        return ""
    return raw if raw in JOB_FIELDS else ""


def get_focus_field_meta(profile: UserProfile) -> dict[str, object] | None:
    from services.job_fields import JOB_FIELDS

    fid = normalize_focus_field(getattr(profile, "focus_field", "") or "")
    if not fid:
        return None
    field = JOB_FIELDS.get(fid)
    if field is None:
        return None
    overlay = _FOCUS_OVERLAYS.get(fid, {})
    return {
        "id": field.id,
        "label": field.label,
        "roles": overlay.get("roles") or field.search_terms,
        "skill_hints": overlay.get("skill_hints") or field.keywords,
        "title_hints": overlay.get("title_hints") or field.keywords,
        "search_terms": field.search_terms,
        "keywords": field.keywords,
    }


def focus_field_label(profile: UserProfile) -> str:
    meta = get_focus_field_meta(profile)
    if meta is None:
        return "Any (skill-first)"
    return str(meta["label"])


# Adjacent titles to expand scrape coverage (AIML ↔ data/analytics, etc.).
_ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "aiml": (
        "AI Engineer",
        "ML Engineer",
        "Machine Learning Engineer",
        "Data Scientist",
        "Data Analyst",
        "Data Engineer",
        "Analytics Engineer",
        "NLP Engineer",
        "Computer Vision Engineer",
        "MLOps Engineer",
        "Research Scientist",
        "Applied Scientist",
        "Business Intelligence Analyst",
        "Python Developer",
    ),
    "data": (
        "Data Analyst",
        "Data Scientist",
        "Data Engineer",
        "Analytics Engineer",
        "Business Intelligence Analyst",
        "BI Developer",
        "ML Engineer",
    ),
    "software": (
        "Software Engineer",
        "Backend Engineer",
        "Full Stack Developer",
        "Python Developer",
        "API Developer",
    ),
}

_AIML_SKILL_MARKERS = (
    "pytorch",
    "tensorflow",
    "langchain",
    "langgraph",
    "llm",
    "machine learning",
    "deep learning",
    "nlp",
    "computer vision",
    "scikit",
    "sklearn",
    "xgboost",
    "huggingface",
    "transformers",
    "opencv",
    "rag",
)

_DATA_SKILL_MARKERS = (
    "sql",
    "tableau",
    "power bi",
    "pandas",
    "numpy",
    "excel",
    "dbt",
    "snowflake",
    "spark",
    "analytics",
    "etl",
)

_AIML_TITLE_HINTS = (
    "ai engineer",
    "ml engineer",
    "machine learning",
    "data scientist",
    "data analyst",
    "data engineer",
    "nlp",
    "computer vision",
    "deep learning",
    "analytics engineer",
    "applied scientist",
    "research scientist",
    "mlops",
    "business intelligence",
)


def profile_looks_aiml(profile: UserProfile) -> bool:
    blob = " ".join(
        [
            *profile.skills,
            *profile.preferred_roles,
            profile.role,
            profile.summary or "",
        ]
    ).lower()
    if any(k in blob for k in _AIML_SKILL_MARKERS):
        return True
    return any(h in blob for h in ("ai engineer", "ml engineer", "aiml", "ai/ml"))


def profile_looks_data(profile: UserProfile) -> bool:
    blob = " ".join([*profile.skills, *profile.preferred_roles, profile.role]).lower()
    if any(k in blob for k in _DATA_SKILL_MARKERS):
        return True
    return any(h in blob for h in ("data analyst", "data scientist", "data engineer"))


def adjacent_role_terms(profile: UserProfile) -> list[str]:
    """Expanded role family for scrape queries (not only exact preferred titles)."""
    primary = role_search_terms(profile)
    out: list[str] = []
    seen: set[str] = set()

    def _add(role: str) -> None:
        clean = " ".join(role.split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)

    for role in primary:
        _add(role)

    focus = get_focus_field_meta(profile)
    if focus:
        for role in focus.get("roles") or ():
            _add(str(role))
        return out

    if profile_looks_aiml(profile):
        for role in _ROLE_FAMILIES["aiml"]:
            _add(role)
    elif profile_looks_data(profile):
        for role in _ROLE_FAMILIES["data"]:
            _add(role)
    else:
        # Generic software / tech IC — still expand a little
        for role in _ROLE_FAMILIES["software"]:
            _add(role)

    return out


def skill_search_terms(profile: UserProfile, *, limit: int = 10) -> list[str]:
    """Skills from the resume to drive board search (skill-first discovery).

    When ``focus_field`` is set, prefer skills that belong to that field.
    """
    deny = {
        "communication",
        "teamwork",
        "leadership",
        "english",
        "hindi",
        "soft skills",
        "problem solving",
        "ms office",
    }
    picked: list[str] = []
    seen: set[str] = set()
    focus = get_focus_field_meta(profile)
    focus_hints = {
        str(h).lower() for h in (focus.get("skill_hints") or ())  # type: ignore[union-attr]
    } if focus else set()

    def _add(skill: str) -> None:
        token = " ".join(skill.strip().split())
        key = token.lower()
        if len(token) < 2 or key in deny or key in seen:
            return
        seen.add(key)
        picked.append(token)

    all_skills = list(profile.all_skills())
    # Pass 1: skills that match the optional focus field
    if focus_hints:
        for skill in all_skills:
            key = skill.strip().lower()
            if key in focus_hints or any(h in key or key in h for h in focus_hints):
                _add(skill)
            if len(picked) >= limit:
                return picked[:limit]

    for skill in all_skills:
        _add(skill)
        if len(picked) >= limit:
            return picked[:limit]

    catalog = list(focus_hints) if focus_hints else [
        "python",
        "sql",
        "pytorch",
        "tensorflow",
        "machine learning",
        "langchain",
        "pandas",
        "fastapi",
        "aws",
        "azure",
        "docker",
        "nlp",
        "tableau",
        "power bi",
        "scikit-learn",
        "opencv",
    ]
    have = {s.strip().lower() for s in all_skills if s.strip()}
    for skill in catalog:
        if skill in have or any(skill in h for h in have):
            _add(skill)
        if len(picked) >= limit:
            break
    return picked[:limit]


def listing_matches_profile_keywords(
    profile: UserProfile,
    title: str,
    description: str = "",
) -> bool:
    """Skill-first keep rule; optional focus_field narrows to that domain."""
    hay = f"{title} {description}".lower()
    if not hay.strip():
        return False

    focus = get_focus_field_meta(profile)
    if focus:
        title_hints = [str(h).lower() for h in (focus.get("title_hints") or ())]
        skill_hints = [str(h).lower() for h in (focus.get("skill_hints") or ())]
        title_hit = any(h in hay for h in title_hints)
        focus_skill_hit = False
        for skill in profile.all_skills():
            key = skill.strip().lower()
            if not any(h in key or key in h for h in skill_hints):
                continue
            if _word_boundary_hit(key, hay) or any(
                _word_boundary_hit(h, hay) for h in _expand_skill(skill) if len(h) > 2
            ):
                focus_skill_hit = True
                break
        return title_hit or focus_skill_hit

    hits = skill_hits_in_text(profile, hay)
    if hits >= 1:
        return True

    for role in adjacent_role_terms(profile)[:8]:
        if role.lower() in hay:
            return True
    return False


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
    {
        "engineer",
        "developer",
        "analyst",
        "scientist",
        "architect",
        "programmer",
        "mlops",
    }
)


def role_relevant(job: JobListing, profile: UserProfile) -> bool:
    """Skill-first relevance; optional focus_field narrows to that career field."""
    from services.job_fields import effective_fields, job_matches_any_field

    # Explicit field focus: keep only jobs that match the selected field
    if normalize_focus_field(getattr(profile, "focus_field", "") or ""):
        return job_matches_any_field(job, effective_fields(profile), profile)

    haystack = (
        f"{job.title} {job.description} {job.requirements} {' '.join(job.skills)}"
    ).lower()
    title_l = (job.title or "").lower()

    hits = skill_hits_in_text(profile, haystack)
    if hits >= 1:
        return True

    # Title-family fallback (no skill overlap in the snippet)
    for role in adjacent_role_terms(profile)[:12]:
        if role.lower() in haystack:
            return True

    if profile_looks_aiml(profile) or profile_looks_data(profile):
        if any(h in title_l for h in _AIML_TITLE_HINTS):
            return True

    roles = role_search_terms(profile)
    role_hit = any(
        _word_boundary_hit(token, haystack)
        for role in roles
        for token in _tokens(role)
        if len(token) > 2 and token not in {"level", "mid"}
    )
    if role_hit and any(w in haystack for w in _TECH_ROLE_WORDS):
        return True

    return False


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
