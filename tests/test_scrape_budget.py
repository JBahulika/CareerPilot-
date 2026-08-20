"""Tests for scrape budgets and skill+role search queries."""

from __future__ import annotations

from datetime import datetime

from agents.job_sources.budget import allocate_scrape_budgets, source_weight
from agents.job_sources.common import (
    early_relevance_score,
    job_identity_key,
    search_queries,
    search_terms,
    split_limit_across_queries,
)
from models.schemas import JobListing, UserProfile


def test_even_budgets_same_requested_across_sources():
    ids = ["remotive", "themuse", "linkedin", "indeed"]
    budgets = allocate_scrape_budgets(ids, 100)
    assert sum(budgets.values()) == 100
    # Even split: differ by at most 1
    vals = list(budgets.values())
    assert max(vals) - min(vals) <= 1
    assert all(v == 25 for v in vals)


def test_weighted_budgets_still_available():
    ids = ["remotive", "themuse", "linkedin", "indeed"]
    budgets = allocate_scrape_budgets(ids, 100, weighted=True)
    assert sum(budgets.values()) == 100
    assert budgets["remotive"] > budgets["linkedin"]
    assert source_weight("remotive") > source_weight("linkedin")


def test_budget_remainder_distributed():
    ids = ["a", "b", "c"]
    budgets = allocate_scrape_budgets(ids, 10)
    assert sum(budgets.values()) == 10
    assert max(budgets.values()) - min(budgets.values()) <= 1


def test_search_queries_include_skills_and_roles():
    profile = UserProfile(
        role="AI Engineer",
        preferred_roles=["AI Engineer", "ML Engineer"],
        skills=["pytorch", "langchain"],
        experience_level="Fresher",
        target_years_min=0,
        target_years_max=1,
    )
    queries = search_queries(profile, max_queries=6)
    assert 1 <= len(queries) <= 6
    primary = search_terms(profile)
    assert primary == queries[0]
    joined = " | ".join(queries).lower()
    assert "pytorch" in joined or "langchain" in joined
    assert "ai engineer" in joined or "ml engineer" in joined
    assert "entry level graduate" not in primary.lower()


def test_senior_queries_skip_junior():
    profile = UserProfile(
        role="AI Engineer",
        experience_level="5+ years",
        target_years_min=5,
        target_years_max=15,
        skills=["python"],
    )
    joined = " ".join(search_queries(profile)).lower()
    assert "junior" not in joined


def test_split_limit_across_queries():
    parts = split_limit_across_queries(10, 3)
    assert sum(parts) == 10
    assert len(parts) == 3


def test_job_identity_prefers_url():
    job = JobListing(
        source="x",
        company="Acme",
        title="Eng",
        description="d",
        apply_url="https://example.com/jobs/1?ref=a",
        content_hash="h",
        scraped_at=datetime.utcnow(),
    )
    assert job_identity_key(job).startswith("url:https://example.com/jobs/1")


def test_early_relevance_prefers_skill_overlap():
    profile = UserProfile(role="ML Engineer", skills=["pytorch", "fastapi", "python"])
    strong = JobListing(
        source="x",
        company="A",
        title="ML Engineer",
        description="Build models with pytorch and fastapi",
        skills=["pytorch"],
        content_hash="a",
        scraped_at=datetime.utcnow(),
    )
    weak = JobListing(
        source="x",
        company="B",
        title="Sales Associate",
        description="Cold calling",
        skills=[],
        content_hash="b",
        scraped_at=datetime.utcnow(),
    )
    assert early_relevance_score(strong, profile) > early_relevance_score(weak, profile)
