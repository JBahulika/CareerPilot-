"""Tests for flexible experience year matching."""

from __future__ import annotations

from models.schemas import JobListing, UserProfile
from services.seniority import is_job_compatible_with_profile, is_years_compatible


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
