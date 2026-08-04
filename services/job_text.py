"""Job description normalization and section extraction."""

from __future__ import annotations

import re

from models.schemas import JobListing
from services.seniority import infer_job_required_years, infer_job_tier

_REQUIREMENTS_HEADERS = re.compile(
    r"(?im)^(?:requirements?|qualifications?|must have|what you.ll need|"
    r"what we.re looking for|minimum qualifications?)\s*:?\s*$"
)
_NICE_HEADERS = re.compile(
    r"(?im)^(?:nice to have|preferred qualifications?|bonus|pluses?)\s*:?\s*$"
)
_REMOTE_RE = re.compile(
    r"\b(fully remote|remote-first|hybrid|on-?site|office-based)\b", re.IGNORECASE
)
_EMPLOYMENT_RE = re.compile(
    r"\b(full[\s-]?time|part[\s-]?time|contract|internship|freelance)\b", re.IGNORECASE
)


def _split_sections(description: str) -> tuple[str, str, str]:
    if not description:
        return "", "", ""
    lines = description.splitlines()
    req_lines: list[str] = []
    nice_lines: list[str] = []
    body_lines: list[str] = []
    mode = "body"
    for line in lines:
        stripped = line.strip()
        if _REQUIREMENTS_HEADERS.match(stripped):
            mode = "req"
            continue
        if _NICE_HEADERS.match(stripped):
            mode = "nice"
            continue
        if mode == "req":
            req_lines.append(line)
        elif mode == "nice":
            nice_lines.append(line)
        else:
            body_lines.append(line)
    requirements = "\n".join(req_lines).strip()
    nice = "\n".join(nice_lines).strip()
    body = "\n".join(body_lines).strip()
    return body, requirements, nice


def _infer_remote_policy(text: str, location: str) -> str:
    haystack = f"{text} {location}".lower()
    match = _REMOTE_RE.search(haystack)
    if match:
        return match.group(1).strip()
    if "remote" in haystack:
        return "remote"
    return ""


def _infer_employment_type(text: str, title: str) -> str:
    haystack = f"{title} {text}".lower()
    match = _EMPLOYMENT_RE.search(haystack)
    return match.group(1).strip() if match else ""


def enrich_job_listing(job: JobListing) -> JobListing:
    """Populate structured fields used for filtering and retrieval."""
    body, requirements, nice = _split_sections(job.description)
    if not job.requirements and requirements:
        job.requirements = requirements
    if not job.nice_to_have and nice:
        job.nice_to_have = nice
    if requirements and job.description == body:
        pass
    elif not job.requirements and body:
        job.requirements = body[:3000]

    if job.required_years_min is None:
        job.required_years_min = infer_job_required_years(job)
    if job.seniority_tier is None:
        job.seniority_tier = infer_job_tier(job)
    if not job.remote_policy:
        job.remote_policy = _infer_remote_policy(job.description, job.location)
    if not job.employment_type:
        job.employment_type = _infer_employment_type(job.description, job.title)
    return job
