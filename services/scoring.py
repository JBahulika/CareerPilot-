"""Deterministic relevance scoring for scraped jobs.

Produces an explainable 0-100 fit score used to rank jobs at scrape time,
before the (expensive) embedding/LLM matcher runs. Combining several cheap
signals here means the most relevant jobs bubble to the top and the matcher
spends its budget on the best candidates.

Signal weights (sum to 100):
    title relevance      35   role/AIML signal in the *title* is the strongest cue
    skill overlap        25   profile skills found in the posting
    seniority proximity  20   how close the job level is to the candidate
    recency              12   newer postings score higher
    location fit          8   preferred location or acceptable remote
"""

from __future__ import annotations

from datetime import datetime, timedelta

from models.schemas import JobListing, UserProfile
from services.location import effective_location, is_remote_location, locations_match
from services.seniority import (
    infer_candidate_tier,
    infer_job_tier,
)
from services.skills import (
    _aiml_hits,  # noqa: PLC2701 - internal reuse, single source of truth
    _profile_is_aiml_focused,
    deterministic_skill_overlap,
    is_excluded_job_title,
    role_search_terms,
)

_W_TITLE = 35
_W_SKILLS = 25
_W_SENIORITY = 20
_W_RECENCY = 12
_W_LOCATION = 8


def _title_relevance(job: JobListing, profile: UserProfile) -> float:
    """0-1: how strongly the title signals the candidate's target domain/role."""
    title = (job.title or "").lower()
    if not title:
        return 0.0

    score = 0.0
    # Exact/!partial preferred-role phrase in the title is the best signal.
    for role in role_search_terms(profile):
        role_lower = role.lower().strip()
        if role_lower and role_lower in title:
            score = max(score, 1.0)

    if _profile_is_aiml_focused(profile):
        hits = _aiml_hits(job.title)
        if hits >= 2:
            score = max(score, 0.95)
        elif hits == 1:
            score = max(score, 0.8)
    else:
        # Non-AIML: reward generic tech-role words in the title.
        for word in ("engineer", "developer", "scientist", "analyst", "architect"):
            if word in title:
                score = max(score, 0.7)
                break

    return score


def _seniority_proximity(job: JobListing, profile: UserProfile) -> float:
    """1.0 when tiers match, decaying with distance."""
    cand = infer_candidate_tier(profile)
    job_tier = infer_job_tier(job)
    distance = abs(cand - job_tier)
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.7
    if distance == 2:
        return 0.35
    return 0.0


def _recency(job: JobListing) -> float:
    """1.0 for fresh (<=2 days), decaying to 0 by ~30 days."""
    posted = job.posted_at or job.scraped_at
    if posted is None:
        return 0.3
    age = datetime.utcnow() - posted
    if age <= timedelta(days=2):
        return 1.0
    if age >= timedelta(days=30):
        return 0.0
    return max(0.0, 1.0 - (age - timedelta(days=2)) / timedelta(days=28))


def _location_fit(job: JobListing, profile: UserProfile) -> float:
    pref = effective_location(profile)
    location = job.location or ""
    if job.remote or is_remote_location(location):
        return 1.0 if profile.include_remote else 0.2
    if not pref:
        return 0.6
    if not location.strip():
        return 0.4
    return 1.0 if locations_match(location, pref) else 0.2


def relevance_score(job: JobListing, profile: UserProfile) -> int:
    """Composite 0-100 fit score for a scraped job against the profile."""
    if is_excluded_job_title(job.title):
        return 0

    title = _title_relevance(job, profile)
    skills = deterministic_skill_overlap(profile, job) / 100.0
    seniority = _seniority_proximity(job, profile)
    recency = _recency(job)
    location = _location_fit(job, profile)

    total = (
        _W_TITLE * title
        + _W_SKILLS * skills
        + _W_SENIORITY * seniority
        + _W_RECENCY * recency
        + _W_LOCATION * location
    )
    return max(0, min(100, round(total)))
