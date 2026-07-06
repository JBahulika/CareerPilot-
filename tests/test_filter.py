"""Tests for the JobFilterAgent rules."""

from __future__ import annotations

from agents.filter_agent import JobFilterAgent
from agents.scraper_agent import _content_hash
from models.schemas import JobListing, UserProfile


def _job(title: str, desc: str = "", location: str = "Remote", skills=None) -> JobListing:
    return JobListing(
        title=title,
        company="Acme",
        description=desc,
        location=location,
        skills=skills or [],
        content_hash=_content_hash("Acme", title, desc),
    )


def test_dedup_removes_identical_jobs():
    job = _job("AI Engineer", "python ml")
    kept = JobFilterAgent().run([job, job], UserProfile(skills=["python"]))
    assert len(kept) == 1


def test_relevance_drops_unrelated_roles():
    profile = UserProfile(skills=["python"], preferred_roles=["AI Engineer"])
    jobs = [_job("AI Engineer", "python required"), _job("Truck Driver", "cdl license")]
    kept = JobFilterAgent().run(jobs, profile)
    titles = [j.title for j in kept]
    assert "AI Engineer" in titles
    assert "Truck Driver" not in titles


def test_exclude_internships():
    profile = UserProfile(skills=["python"])
    jobs = [_job("Python Intern", "python internship"), _job("Python Engineer", "python")]
    kept = JobFilterAgent().run(jobs, profile, exclude_internships=True)
    assert all("Intern" not in j.title for j in kept)


def test_location_preference_allows_remote():
    profile = UserProfile(skills=["python"], preferred_location="Bangalore")
    jobs = [_job("Python Engineer", "python", location="Remote")]
    kept = JobFilterAgent().run(jobs, profile)
    assert len(kept) == 1
