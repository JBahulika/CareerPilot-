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


class TheMuseSource:
    """The Muse public jobs API (no API key)."""

    name = "themuse"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = search_terms(profile).split()[0] if search_terms(profile) else "engineer"
        try:
            payload = get_scrape_client().get_json(
                "https://www.themuse.com/api/public/jobs",
                source_id=self.name,
                params={
                    "page": 1,
                    "descending": "true",
                    "category": "Software Engineering",
                    "level": "Entry Level,Mid Level,Senior Level",
                },
            )
            raw = payload.get("results") or []
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"The Muse aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
            logger.error(f"The Muse failed: {exc}")
            return []

        jobs: list[JobListing] = []
        q = query.lower()
        for item in raw:
            title = item.get("name") or ""
            company = (item.get("company") or {}).get("name") or ""
            desc = strip_html(item.get("contents") or "")
            hay = f"{title} {desc}".lower()
            if q and q not in hay and not any(
                w in hay for w in search_terms(profile).lower().split() if len(w) > 3
            ):
                # Keep a portion of unfiltered results so empty queries still return jobs
                if len(jobs) >= max(3, limit // 3):
                    continue
            locs = item.get("locations") or []
            location = ", ".join(
                loc.get("name", "") for loc in locs if isinstance(loc, dict) and loc.get("name")
            ) or "Remote"
            refs = item.get("refs") or {}
            apply_url = refs.get("landing_page") or ""
            cats = item.get("categories") or []
            skills = [
                c.get("name", "") for c in cats if isinstance(c, dict) and c.get("name")
            ]
            jobs.append(
                build_job(
                    source=self.name,
                    company=company,
                    title=title,
                    description=desc,
                    skills=skills,
                    location=location,
                    apply_url=apply_url,
                    posted_at=parse_posted_at(item.get("publication_date")),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class WeWorkRemotelySource:
    """We Work Remotely public programming jobs RSS."""

    name = "weworkremotely"
    FEED_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = get_scrape_client().get(
                self.FEED_URL,
                source_id=self.name,
                accept="application/rss+xml,application/xml,text/xml,*/*",
            )
            items = _parse_rss_items(resp.text)
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"We Work Remotely aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
            logger.error(f"We Work Remotely failed: {exc}")
            return []

        query_words = [w for w in search_terms(profile).lower().split() if len(w) > 2]
        jobs: list[JobListing] = []
        for item in items:
            title = item.get("title") or ""
            desc = strip_html(item.get("description") or "")
            hay = f"{title} {desc}".lower()
            if query_words and not any(w in hay for w in query_words):
                continue
            company = ""
            role = title
            if ":" in title:
                company, role = [p.strip() for p in title.split(":", 1)]
            jobs.append(
                build_job(
                    source=self.name,
                    company=company or "Remote",
                    title=role or title,
                    description=desc,
                    location="Remote",
                    apply_url=item.get("link") or "",
                    posted_at=parse_posted_at(item.get("pubDate")),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class WorkingNomadsSource:
    """Working Nomads public exposed_jobs JSON."""

    name = "workingnomads"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            raw = get_scrape_client().get_json(
                "https://www.workingnomads.com/api/exposed_jobs/",
                source_id=self.name,
            )
            if not isinstance(raw, list):
                raw = raw.get("jobs") or raw.get("results") or []
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"Working Nomads aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
            logger.error(f"Working Nomads failed: {exc}")
            return []

        query_words = [w for w in search_terms(profile).lower().split() if len(w) > 2]
        jobs: list[JobListing] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("position") or ""
            desc = strip_html(item.get("description") or item.get("excerpt") or "")
            hay = f"{title} {desc}".lower()
            if query_words and not any(w in hay for w in query_words):
                continue
            tags = item.get("tags") or item.get("category") or []
            if isinstance(tags, str):
                skills = [t.strip() for t in tags.split(",") if t.strip()]
            else:
                skills = [str(t) for t in tags if t]
            jobs.append(
                build_job(
                    source=self.name,
                    company=item.get("company_name") or item.get("company") or "",
                    title=title,
                    description=desc,
                    skills=skills,
                    location=item.get("location") or "Remote",
                    apply_url=item.get("url") or item.get("apply_url") or "",
                    posted_at=parse_posted_at(
                        item.get("pub_date") or item.get("published") or item.get("date")
                    ),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


def _parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        def _text(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""

        items.append(
            {
                "title": _text("title"),
                "link": _text("link"),
                "description": _text("description"),
                "pubDate": _text("pubDate"),
            }
        )
    return items


def _finalize(jobs, profile, allow_stretch, flex_years, source_name) -> list[JobListing]:
    jobs = annotate_and_filter_jobs(
        jobs, profile, allow_stretch=allow_stretch, flex_years=flex_years
    )
    jobs = sort_and_filter_recent(jobs)
    logger.info(f"{source_name}: {len(jobs)} jobs after filters")
    return jobs
