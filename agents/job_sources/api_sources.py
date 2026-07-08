"""Public API job board adapters (no browser required)."""

from __future__ import annotations

from agents.job_sources.common import (
    build_job,
    http_get,
    parse_posted_at,
    prepare_scraped_jobs,
    search_queries,
    strip_html,
)
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)


def _as_type(value) -> str:
    """Normalize a job-type value that may be a str or list into a label."""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v).replace("_", " ").strip() for v in value if v)
    return str(value or "").replace("_", " ").strip()


def _finalize(jobs, profile, allow_stretch, flex_years, source_name) -> list[JobListing]:
    jobs = prepare_scraped_jobs(jobs, profile)
    logger.info(f"{source_name}: {len(jobs)} jobs after relevance + recency filter")
    return jobs


class RemotiveSource:
    name = "remotive"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        seen: set[str] = set()
        jobs: list[JobListing] = []
        per_query = max(15, limit // max(len(search_queries(profile)), 1))

        for query in search_queries(profile)[:4]:
            if len(jobs) >= limit:
                break
            try:
                resp = http_get(
                    "https://remotive.com/api/remote-jobs",
                    params={"search": query, "limit": per_query},
                )
                raw = resp.json().get("jobs", [])
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Remotive search '{query}' failed: {exc}")
                continue

            for item in raw:
                job = build_job(
                    source=self.name,
                    company=item.get("company_name", ""),
                    title=item.get("title", ""),
                    description=strip_html(item.get("description", "")),
                    skills=item.get("tags", []) or [],
                    location=item.get("candidate_required_location", "Remote"),
                    salary=item.get("salary", "") or "",
                    apply_url=item.get("url", ""),
                    apply_base="https://remotive.com",
                    job_type=_as_type(item.get("job_type")),
                    remote=True,
                    posted_at=parse_posted_at(item.get("publication_date")),
                )
                if job.content_hash in seen:
                    continue
                seen.add(job.content_hash)
                jobs.append(job)
                if len(jobs) >= limit:
                    break

        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class RemoteOKSource:
    name = "remoteok"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = http_get("https://remoteok.com/api")
            raw = resp.json()
            if raw and isinstance(raw[0], str):
                raw = raw[1:]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"RemoteOK failed: {exc}")
            return []

        jobs: list[JobListing] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = item.get("position") or item.get("title") or ""
            desc = strip_html(item.get("description", ""))
            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            salary = ""
            if salary_min and salary_max:
                salary = f"${salary_min:,} - ${salary_max:,}"
            elif salary_min:
                salary = f"${salary_min:,}+"
            job = build_job(
                source=self.name,
                company=item.get("company", ""),
                title=title,
                description=desc,
                skills=[t.strip() for t in (item.get("tags") or []) if t],
                location=item.get("location", "Remote"),
                salary=salary,
                apply_url=item.get("url") or item.get("apply_url", ""),
                apply_base="https://remoteok.com",
                remote=True,
                posted_at=parse_posted_at(item.get("date") or item.get("epoch")),
            )
            jobs.append(job)
            if len(jobs) >= limit * 4:
                break
        return _finalize(jobs[: limit * 4], profile, allow_stretch, flex_years, self.name)


class ArbeitnowSource:
    name = "arbeitnow"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = http_get("https://www.arbeitnow.com/api/job-board-api")
            raw = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Arbeitnow failed: {exc}")
            return []

        jobs: list[JobListing] = []
        for item in raw:
            jobs.append(
                build_job(
                    source=self.name,
                    company=item.get("company_name", ""),
                    title=item.get("title", ""),
                    description=strip_html(item.get("description", "")),
                    skills=item.get("tags", []) or [],
                    location=item.get("location", ""),
                    apply_url=item.get("url", ""),
                    apply_base="https://www.arbeitnow.com",
                    job_type=_as_type(item.get("job_types")),
                    remote=bool(item.get("remote")),
                    posted_at=parse_posted_at(item.get("created_at")),
                )
            )
            if len(jobs) >= limit * 4:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class JobicySource:
    name = "jobicy"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        jobs: list[JobListing] = []
        tags = ["ai", "machine-learning", "data-science", "python"]
        per_tag = max(10, limit // len(tags))

        for tag in tags:
            try:
                resp = http_get(
                    "https://jobicy.com/api/v2/remote-jobs",
                    params={"count": per_tag, "tag": tag},
                )
                raw = resp.json().get("jobs", [])
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Jobicy tag '{tag}' failed: {exc}")
                continue

            for item in raw:
                industry = item.get("jobIndustry")
                skills = industry if isinstance(industry, list) else (
                    [industry] if industry else []
                )
                jobs.append(
                    build_job(
                        source=self.name,
                        company=item.get("companyName", ""),
                        title=item.get("jobTitle", ""),
                        description=strip_html(item.get("jobDescription", "")),
                        skills=skills,
                        location=item.get("jobGeo", "Remote"),
                        salary=item.get("annualSalaryMin", "") or "",
                        apply_url=item.get("url", ""),
                        apply_base="https://jobicy.com",
                        job_type=_as_type(item.get("jobType")),
                        remote=True,
                        posted_at=parse_posted_at(item.get("pubDate")),
                    )
                )

        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class HimalayasSource:
    name = "himalayas"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = http_get(
                "https://himalayas.app/jobs/api",
                params={"limit": limit * 4},
            )
            raw = resp.json().get("jobs", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Himalayas failed: {exc}")
            return []

        jobs = []
        for item in raw:
            # Prefer the real application link; else resolve the slug to the
            # canonical Himalayas posting page (a bare slug is not a URL).
            apply_url = item.get("applicationLink", "") or item.get("slug", "")
            jobs.append(
                build_job(
                    source=self.name,
                    company=item.get("companyName", ""),
                    title=item.get("title", ""),
                    description=strip_html(item.get("description", "")),
                    skills=item.get("categories", []) or [],
                    location=item.get("locationRestrictions") or "Remote",
                    salary=item.get("salaryRange", "") or "",
                    apply_url=apply_url,
                    apply_base="https://himalayas.app/jobs",
                    remote=True,
                    posted_at=parse_posted_at(item.get("pubDate")),
                )
            )
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)
