"""Tests for job source registry."""

from __future__ import annotations

from agents.job_sources.registry import POPULAR_JOB_SITES, get_source, list_sources


def test_popular_job_sites_list():
    ids = {s["id"] for s in POPULAR_JOB_SITES}
    assert "remotive" in ids
    assert "indeed" in ids
    assert "naukri" in ids
    assert "linkedin" in ids
    assert len(POPULAR_JOB_SITES) >= 8


def test_get_source_all():
    source = get_source("all")
    assert source.name == "all"


def test_list_sources_includes_aggregate():
    sources = list_sources()
    assert any(s["id"] == "all" for s in sources)
