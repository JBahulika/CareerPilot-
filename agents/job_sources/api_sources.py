"""Public API job board adapters (no browser required)."""

from __future__ import annotations

from datetime import datetime

import requests

from agents.job_sources.common import (
    annotate_and_filter_jobs,
    build_job,
    parse_posted_at,
    search_terms,
    sort_and_filter_recent,
    strip_html,
)
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)


class RemotiveSource:
    name = "remotive"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = search_terms(profile)
        try:
            resp = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": query, "limit": limit},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("jobs", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Remotive failed: {exc}")
            return []

        jobs = [
            build_job(
                source=self.name,
                company=item.get("company_name", ""),
                title=item.get("title", ""),
                description=strip_html(item.get("description", "")),
                skills=item.get("tags", []) or [],
                location=item.get("candidate_required_location", "Remote"),
                salary=item.get("salary", "") or "",
                apply_url=item.get("url", ""),
                posted_at=parse_posted_at(item.get("publication_date")),
            )
            for item in raw[:limit]
        ]
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class RemoteOKSource:
    name = "remoteok"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = requests.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "CareerPilot/1.0"},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()
            if raw and isinstance(raw[0], str):
                raw = raw[1:]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"RemoteOK failed: {exc}")
            return []

        query = search_terms(profile).lower()
        jobs: list[JobListing] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = item.get("position") or item.get("title") or ""
            desc = strip_html(item.get("description", ""))
            haystack = f"{title} {desc}".lower()
            if query and not any(w in haystack for w in query.split() if len(w) > 2):
                continue
            jobs.append(
                build_job(
                    source=self.name,
                    company=item.get("company", ""),
                    title=title,
                    description=desc,
                    skills=[t.strip() for t in (item.get("tags") or []) if t],
                    location=item.get("location", "Remote"),
                    salary=str(item.get("salary_min", "") or ""),
                    apply_url=item.get("url") or item.get("apply_url", ""),
                    posted_at=parse_posted_at(item.get("date") or item.get("epoch")),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class ArbeitnowSource:
    name = "arbeitnow"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = requests.get(
                "https://www.arbeitnow.com/api/job-board-api",
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Arbeitnow failed: {exc}")
            return []

        query = search_terms(profile).lower()
        jobs: list[JobListing] = []
        for item in raw:
            title = item.get("title", "")
            desc = strip_html(item.get("description", ""))
            if query and not any(w in f"{title} {desc}".lower() for w in query.split() if len(w) > 2):
                continue
            jobs.append(
                build_job(
                    source=self.name,
                    company=item.get("company_name", ""),
                    title=title,
                    description=desc,
                    skills=item.get("tags", []) or [],
                    location=item.get("location", ""),
                    apply_url=item.get("url", ""),
                    posted_at=parse_posted_at(item.get("created_at")),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class JobicySource:
    name = "jobicy"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = search_terms(profile).split()[0] if search_terms(profile) else "engineer"
        try:
            resp = requests.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={"count": limit, "tag": query},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("jobs", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Jobicy failed: {exc}")
            return []

        jobs = [
            build_job(
                source=self.name,
                company=item.get("companyName", ""),
                title=item.get("jobTitle", ""),
                description=strip_html(item.get("jobDescription", "")),
                skills=[item.get("jobIndustry", "")] if item.get("jobIndustry") else [],
                location=item.get("jobGeo", "Remote"),
                salary=item.get("annualSalaryMin", "") or "",
                apply_url=item.get("url", ""),
                posted_at=parse_posted_at(item.get("pubDate")),
            )
            for item in raw[:limit]
        ]
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class HimalayasSource:
    name = "himalayas"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = requests.get(
                "https://himalayas.app/jobs/api",
                params={"limit": limit},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("jobs", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Himalayas failed: {exc}")
            return []

        query = search_terms(profile).lower()
        jobs: list[JobListing] = []
        for item in raw:
            title = item.get("title", "")
            desc = strip_html(item.get("description", ""))
            if query and not any(w in f"{title} {desc}".lower() for w in query.split() if len(w) > 2):
                continue
            jobs.append(
                build_job(
                    source=self.name,
                    company=item.get("companyName", ""),
                    title=title,
                    description=desc,
                    skills=item.get("categories", []) or [],
                    location="Remote",
                    apply_url=item.get("applicationLink", "") or item.get("slug", ""),
                    posted_at=parse_posted_at(item.get("pubDate")),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


def _finalize(jobs, profile, allow_stretch, flex_years, source_name) -> list[JobListing]:
    jobs = prepare_scraped_jobs(jobs)
    logger.info(f"{source_name}: {len(jobs)} jobs after recency filter")
    return jobs
