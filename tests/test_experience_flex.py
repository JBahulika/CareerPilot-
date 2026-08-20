"""Tests for flexible experience year matching."""

from __future__ import annotations

from models.schemas import JobListing, UserProfile
from services.seniority import (
    infer_job_required_years,
    is_job_compatible_with_profile,
    is_years_compatible,
)


def test_target_years_range_accepts_nearby_jobs():
    profile = UserProfile(
        experience_level="Fresher",
        target_years_min=0,
        target_years_max=2,
    )
    entry_job = JobListing(title="Junior Dev", description="0-1 years experience")
    senior_job = JobListing(title="Senior Dev", description="minimum 8 years experience")
    assert is_years_compatible(profile, entry_job, flex_years=2)
    assert not is_years_compatible(profile, senior_job, flex_years=1)


def test_flexible_profile_accepts_mid_with_stretch():
    profile = UserProfile(
        experience_level="Fresher",
        target_years_min=0,
        target_years_max=2,
    )
    job = JobListing(title="Engineer", description="3 years experience required")
    assert is_job_compatible_with_profile(job, profile, flex_years=2, allow_stretch=True)


def test_plus_years_parsed_and_blocked_for_entry_with_flex_1():
    profile = UserProfile(
        experience_level="0-1 years",
        target_years_min=0,
        target_years_max=1,
        flex_years=1,
    )
    job = JobListing(
        title="Software Engineer",
        description="Looking for candidates with 5+ years in Python.",
    )
    assert infer_job_required_years(job) == 5
    assert is_years_compatible(profile, job, flex_years=1) is False
    assert is_job_compatible_with_profile(job, profile, flex_years=1) is False


def test_year_range_uses_lower_bound():
    job = JobListing(
        title="Backend Engineer",
        description="Requirements: 3-5 years of professional experience.",
    )
    assert infer_job_required_years(job) >= 3


def test_flex_1_allows_one_year_above_max():
    profile = UserProfile(target_years_min=0, target_years_max=1)
    job = JobListing(title="Eng", description="2 years of experience required")
    assert is_years_compatible(profile, job, flex_years=1) is True
    job3 = JobListing(title="Eng", description="3 years of experience required")
    assert is_years_compatible(profile, job3, flex_years=1) is False
