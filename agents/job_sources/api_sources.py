"""Public API job board adapters (no browser required)."""

from __future__ import annotations

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
from services.scrape_http import CaptchaBlockedError, RateLimitedError, get_scrape_client
from services.source_health import get_source_health_registry

logger = get_logger(__name__)


class RemotiveSource:
    name = "remotive"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = search_terms(profile)
        try:
            raw = get_scrape_client().get_json(
                "https://remotive.com/api/remote-jobs",
                source_id=self.name,
                params={"search": query, "limit": limit},
            ).get("jobs", [])
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"Remotive aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
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
            raw = get_scrape_client().get_json(
                "https://remoteok.com/api",
                source_id=self.name,
            )
            if raw and isinstance(raw[0], str):
                raw = raw[1:]
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"RemoteOK aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
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
            raw = get_scrape_client().get_json(
                "https://www.arbeitnow.com/api/job-board-api",
                source_id=self.name,
            ).get("data", [])
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"Arbeitnow aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
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
            raw = get_scrape_client().get_json(
                "https://jobicy.com/api/v2/remote-jobs",
                source_id=self.name,
                params={"count": limit, "tag": query},
            ).get("jobs", [])
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"Jobicy aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
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
            raw = get_scrape_client().get_json(
                "https://himalayas.app/jobs/api",
                source_id=self.name,
                params={"limit": limit},
            ).get("jobs", [])
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"Himalayas aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
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
    jobs = annotate_and_filter_jobs(
        jobs, profile, allow_stretch=allow_stretch, flex_years=flex_years
    )
    jobs = sort_and_filter_recent(jobs)
    logger.info(f"{source_name}: {len(jobs)} jobs after filters")
    return jobs
