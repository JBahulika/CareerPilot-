"""Pluggable job board sources and aggregate scraping."""

from agents.job_sources.registry import POPULAR_JOB_SITES, get_source, list_sources
from agents.job_sources.aggregate import AggregateSource

__all__ = ["POPULAR_JOB_SITES", "AggregateSource", "get_source", "list_sources"]
