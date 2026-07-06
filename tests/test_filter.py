"""Tests for the JobFilterAgent rules."""

from __future__ import annotations

from agents.filter_agent import JobFilterAgent
from agents.job_sources.common import content_hash as _content_hash
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
    profile = UserProfile(skills=["python"], experience_level="3-5 years")
    kept = JobFilterAgent().run([job, job], profile)
    assert len(kept) == 1


def test_relevance_drops_unrelated_roles():
    profile = UserProfile(
        skills=["python"], preferred_roles=["AI Engineer"], experience_level="3-5 years"
    )
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
    profile = UserProfile(
        skills=["python"], preferred_location="Bangalore", experience_level="3-5 years"
    )
    jobs = [_job("Python Engineer", "python", location="Remote")]
    kept = JobFilterAgent().run(jobs, profile)
    assert len(kept) == 1


def test_fresher_profile_rejects_senior_jobs():
    profile = UserProfile(experience_level="Fresher", skills=["python", "machine learning"])
    jobs = [
        _job("Junior Developer", "python ml entry level"),
        _job("Senior Staff Engineer", "5+ years python required"),
        _job("Graduate ML Engineer", "python ml for new grads"),
    ]
    kept = JobFilterAgent().run(jobs, profile, strict_experience=True)
    titles = [j.title for j in kept]
    assert "Senior Staff Engineer" not in titles
    assert "Junior Developer" in titles
    assert "Graduate ML Engineer" in titles


def test_strict_experience_can_be_disabled():
    profile = UserProfile(experience_level="Fresher", skills=["python"])
    jobs = [_job("Senior Engineer", "python senior role")]
    kept = JobFilterAgent().run(jobs, profile, strict_experience=False)
    assert len(kept) == 1
