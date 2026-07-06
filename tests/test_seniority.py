"""Tests for experience-level / seniority inference."""

from __future__ import annotations

from models.schemas import JobListing, UserProfile
from services.seniority import (
    infer_candidate_tier,
    infer_job_tier,
    infer_job_tier_from_text,
    is_compatible,
    is_job_compatible_with_profile,
)


def test_fresher_candidate_tier():
    profile = UserProfile(experience_level="Fresher")
    assert infer_candidate_tier(profile) == 0


def test_senior_job_tier_from_title():
    assert infer_job_tier_from_text("Senior AI Engineer", "Python required") >= 3


def test_entry_job_tier_from_title():
    assert infer_job_tier_from_text("Junior ML Engineer", "") <= 1


def test_fresher_not_compatible_with_senior_job():
    assert is_compatible(0, 4) is False


def test_fresher_compatible_with_junior_job():
    assert is_compatible(0, 1) is True


def test_years_required_bumps_job_tier():
    tier = infer_job_tier_from_text(
        "Software Engineer", "Minimum 7 years of experience required"
    )
    assert tier >= 3


def test_job_compatibility_integration():
    profile = UserProfile(experience_level="Fresher", skills=["python"])
    senior_job = JobListing(
        title="Senior Staff Engineer",
        description="5+ years Python experience",
    )
    junior_job = JobListing(
        title="Graduate ML Engineer",
        description="Entry level role for new graduates",
    )
    assert is_job_compatible_with_profile(senior_job, profile) is False
    assert is_job_compatible_with_profile(junior_job, profile) is True


def test_allow_stretch_permits_extra_tier():
    assert is_compatible(0, 2, allow_stretch=True) is True
    assert is_compatible(0, 4, allow_stretch=True) is False


def test_infer_job_tier_accepts_job_listing():
    job = JobListing(title="Lead Backend Engineer", description="")
    assert infer_job_tier(job) >= 4
