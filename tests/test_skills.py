"""Tests for skill relevance and false-positive blocking."""

from __future__ import annotations

from agents.job_sources.common import content_hash
from agents.filter_agent import JobFilterAgent
from models.schemas import JobListing, UserProfile
from services.skills import (
    filter_matched_skills,
    filter_missing_skills,
    has_unrelated_enterprise_stack,
    role_relevant,
)

def _job(title: str, desc: str = "", skills=None) -> JobListing:
    return JobListing(
        title=title,
        company="Acme",
        description=desc,
        skills=skills or [],
        content_hash=content_hash("Acme", title, desc),
    )


def _aiml_profile() -> UserProfile:
    return UserProfile(
        experience_level="0-1 years",
        target_years_min=0,
        target_years_max=1,
        skills=[
            "Python",
            "PyTorch",
            "TensorFlow",
            "LangChain",
            "Machine Learning",
        ],
        preferred_roles=["AI Engineer", "Machine Learning Engineer"],
    )


def test_abap_job_blocked_for_aiml_profile():
    profile = _aiml_profile()
    job = _job("SAP ABAP Developer", "ABAP and SAP required", skills=["ABAP", "SAP"])
    assert has_unrelated_enterprise_stack(job, profile)
    kept = JobFilterAgent().run([job], profile, strict_experience=True).jobs
    assert len(kept) == 0


def test_aiml_job_relevant_for_aiml_profile():
    profile = _aiml_profile()
    job = _job("Junior ML Engineer", "Python pytorch machine learning", skills=["Python"])
    assert role_relevant(job, profile)
    assert not has_unrelated_enterprise_stack(job, profile)


def test_aiml_profile_matches_data_analyst_via_skills():
    profile = _aiml_profile()
    profile.skills = list(profile.skills) + ["SQL", "Pandas"]
    job = _job(
        "Junior Data Analyst",
        "Python SQL pandas dashboards and basic machine learning",
        skills=["Python", "SQL"],
    )
    assert role_relevant(job, profile)


def test_skill_first_queries_prefer_resume_skills():
    from services.skills import listing_matches_profile_keywords, skill_search_terms

    profile = _aiml_profile()
    profile.skills = ["Python", "SQL", "Pandas", "PyTorch", "FastAPI", "Docker"]
    terms = skill_search_terms(profile, limit=8)
    assert any(t.lower() == "python" for t in terms)
    assert any(t.lower() == "sql" for t in terms)
    assert listing_matches_profile_keywords(
        profile,
        "Data Analyst",
        "Python SQL pandas visualization",
    )


def test_focus_field_aiml_excludes_unrelated_titles():
    from services.job_fields import effective_fields
    from services.skills import listing_matches_profile_keywords, role_relevant

    profile = _aiml_profile()
    profile.focus_field = "aiml"
    profile.skills = list(profile.skills) + ["SQL", "Pandas"]

    assert effective_fields(profile) == ["aiml"]
    assert role_relevant(
        _job("Junior ML Engineer", "python pytorch machine learning"),
        profile,
    )
    assert not role_relevant(
        _job("Frontend Engineer", "react typescript ui development"),
        profile,
    )
    assert listing_matches_profile_keywords(
        profile,
        "ML Engineer",
        "pytorch tensorflow",
    )
    assert not listing_matches_profile_keywords(
        profile,
        "Frontend Engineer",
        "react typescript css",
    )


def test_focus_field_data_science_narrows_search_queries():
    from agents.job_sources.common import search_queries

    profile = _aiml_profile()
    profile.focus_field = "data_science"
    joined = " ".join(search_queries(profile)).lower()
    assert "data scientist" in joined or "applied scientist" in joined


def test_filter_matched_skills_rejects_hallucinated_abap():
    profile = _aiml_profile()
    claimed = ["Python", "ABAP", "PyTorch"]
    filtered = filter_matched_skills(profile, claimed)
    assert "Python" in filtered
    assert "PyTorch" in filtered
    assert "ABAP" not in filtered


def test_filter_missing_skills_strips_soft_skills():
    profile = _aiml_profile()
    profile.summary = "English (Professional Proficiency), Hindi"
    claimed = [
        "Clear and effective communication in English",
        "Reliability",
        "Strong self-organizational skills",
        "Node.js",
        "TypeScript",
        "4+ years of software development experience",
        "Ruby",
    ]
    filtered = filter_missing_skills(profile, claimed)
    assert "Node.js" in filtered
    assert "TypeScript" in filtered
    assert "Ruby" in filtered
    assert any("4+" in x or "years" in x.lower() for x in filtered)
    joined = " ".join(filtered).lower()
    assert "english" not in joined
    assert "reliability" not in joined
    assert "organizational" not in joined
    assert "communication" not in joined


def test_filter_missing_skills_drops_english_when_on_profile():
    profile = _aiml_profile()
    profile.soft_skills = ["English (Professional Proficiency)"]
    filtered = filter_missing_skills(profile, ["English fluency", "Golang"])
    assert filtered == ["Golang"]

def test_filter_missing_skills_saarc_style_keeps_only_tech():
    profile = _aiml_profile()
    claimed = [
        'Pre-Sales Engineering & Champion Building',
        'Solution Selling',
        'SASE/SSE',
        'Post-Sales Engineering Activities',
        'Unity Catalog',
        'MLflow',
    ]
    filtered = filter_missing_skills(profile, claimed)
    joined = ' '.join(filtered).lower()
    assert 'sase' in joined or 'sse' in joined
    assert 'unity catalog' in joined
    assert 'mlflow' in joined
    assert 'selling' not in joined
    assert 'champion' not in joined
    assert 'pre-sales' not in joined and 'presales' not in joined
    assert 'post-sales' not in joined and 'postsales' not in joined


def test_sales_role_detection():
    from services.skills import is_sales_or_gtm_role, profile_is_technical_ic

    job = _job('Principal Partner Solutions Engineer, SAARC')
    assert is_sales_or_gtm_role(job)
    assert profile_is_technical_ic(_aiml_profile())
    assert not is_sales_or_gtm_role(_job('Junior Machine Learning Engineer'))
