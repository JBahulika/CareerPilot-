"""Tests for apply-URL normalization and the guaranteed-link fallback."""

from __future__ import annotations

from agents.job_sources.common import (
    build_job,
    ensure_apply_url,
    normalize_apply_url,
    search_fallback_url,
)


def test_absolute_url_is_kept():
    url = "https://boards.example.com/jobs/42"
    assert normalize_apply_url(url) == url


def test_root_relative_url_joined_to_base():
    assert (
        normalize_apply_url("/jobs/42", base="https://www.indeed.com")
        == "https://www.indeed.com/jobs/42"
    )


def test_bare_slug_joined_to_base():
    assert (
        normalize_apply_url("ml-engineer-acme", base="https://himalayas.app/jobs")
        == "https://himalayas.app/jobs/ml-engineer-acme"
    )


def test_empty_url_without_base_returns_empty():
    assert normalize_apply_url("", base="") == ""
    assert normalize_apply_url("some-slug", base="") == ""


def test_search_fallback_is_valid_link():
    url = search_fallback_url("Acme", "ML Engineer")
    assert url.startswith("https://www.google.com/search?q=")
    assert "ML" in url and "Acme" in url


def test_ensure_apply_url_falls_back_to_search():
    # No usable link and no base -> guaranteed search link.
    url = ensure_apply_url("", base="", company="Acme", title="ML Engineer")
    assert url.startswith("https://www.google.com/search?q=")


def test_build_job_always_has_a_link():
    job = build_job(
        source="jobicy",
        company="Acme",
        title="ML Engineer",
        description="Build models",
        apply_url="",
    )
    assert job.apply_url  # never empty
    job2 = build_job(
        source="himalayas",
        company="Acme",
        title="ML Engineer",
        description="Build models",
        apply_url="ml-engineer-acme",
        apply_base="https://himalayas.app/jobs",
    )
    assert job2.apply_url == "https://himalayas.app/jobs/ml-engineer-acme"
