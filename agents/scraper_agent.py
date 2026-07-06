"""Job Scraper Agent (FR-3, FR-7).

Uses a pluggable ``JobSource`` adapter so new sites can be added without
touching pipeline logic. Two adapters ship with the MVP:

- ``RemotiveSource``  : public JSON API, zero scraping (default, dev-friendly).
- ``WellfoundSource`` : Playwright-driven scrape of Wellfound role search.

All sources normalize results to ``JobListing`` and dedup via a content hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import requests

from core.config import settings
from core.logging import get_logger
from models.schemas import JobListing, UserProfile
from services.seniority import (
    experience_label_for_job,
    infer_candidate_tier,
    is_job_compatible_with_profile,
)

logger = get_logger(__name__)

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _content_hash(company: str, title: str, description: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{description[:500].strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(" ", text or "").replace("&nbsp;", " ").strip()


def _search_terms(profile: UserProfile) -> str:
    terms = profile.preferred_roles or [profile.role]
    base = " ".join(t for t in terms if t).strip() or "software engineer"
    tier = infer_candidate_tier(profile)
    if tier <= 1:
        return f"{base} junior entry level graduate"
    if tier == 2:
        return f"{base} mid level"
    return base


def _annotate_and_filter_jobs(
    jobs: list[JobListing],
    profile: UserProfile,
    *,
    allow_stretch: bool = False,
) -> list[JobListing]:
    """Populate experience labels and drop level-incompatible listings."""
    kept: list[JobListing] = []
    for job in jobs:
        job.experience = experience_label_for_job(job)
        if is_job_compatible_with_profile(job, profile, allow_stretch=allow_stretch):
            kept.append(job)
        else:
            logger.info(
                f"Scraper: dropped '{job.title}' — level mismatch "
                f"({job.experience})"
            )
    return kept


class JobSource(Protocol):
    name: str

    def fetch(
        self,
        profile: UserProfile,
        limit: int,
        *,
        allow_stretch: bool = False,
    ) -> list[JobListing]:
        ...


class RemotiveSource:
    name = "remotive"

    def fetch(
        self,
        profile: UserProfile,
        limit: int,
        *,
        allow_stretch: bool = False,
    ) -> list[JobListing]:
        query = _search_terms(profile)
        logger.info(f"Remotive: searching '{query}' (limit {limit})")
        try:
            resp = requests.get(
                REMOTIVE_API,
                params={"search": query, "limit": limit},
                timeout=30,
            )
            resp.raise_for_status()
            raw_jobs = resp.json().get("jobs", [])
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Remotive fetch failed: {exc}")
            return []

        jobs: list[JobListing] = []
        for item in raw_jobs[:limit]:
            description = _strip_html(item.get("description", ""))
            company = item.get("company_name", "")
            title = item.get("title", "")
            jobs.append(
                JobListing(
                    source=self.name,
                    company=company,
                    title=title,
                    description=description,
                    skills=item.get("tags", []) or [],
                    location=item.get("candidate_required_location", "Remote"),
                    salary=item.get("salary", "") or "",
                    apply_url=item.get("url", ""),
                    content_hash=_content_hash(company, title, description),
                )
            )
        jobs = _annotate_and_filter_jobs(jobs, profile, allow_stretch=allow_stretch)
        logger.info(f"Remotive: fetched {len(jobs)} jobs after level filter")
        return jobs


class WellfoundSource:
    """Best-effort Playwright scrape of Wellfound role search.

    Wellfound is JS-heavy and rate-limited; failures degrade gracefully to an
    empty list so the pipeline can fall back to Remotive.
    """

    name = "wellfound"

    def fetch(
        self,
        profile: UserProfile,
        limit: int,
        *,
        allow_stretch: bool = False,
    ) -> list[JobListing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed; cannot use Wellfound source.")
            return []

        role_slug = (_search_terms(profile).split(" ")[0] or "engineer").lower()
        url = f"https://wellfound.com/role/{role_slug}"
        logger.info(f"Wellfound: scraping {url} (limit {limit})")

        jobs: list[JobListing] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                cards = page.query_selector_all("[data-test='JobSearchResult'], .styles_component__Ns_gK")
                for card in cards[:limit]:
                    text = card.inner_text().strip()
                    if not text:
                        continue
                    lines = [ln for ln in text.split("\n") if ln.strip()]
                    title = lines[0] if lines else ""
                    company = lines[1] if len(lines) > 1 else ""
                    link_el = card.query_selector("a")
                    apply_url = (link_el.get_attribute("href") or "") if link_el else ""
                    if apply_url and apply_url.startswith("/"):
                        apply_url = f"https://wellfound.com{apply_url}"
                    jobs.append(
                        JobListing(
                            source=self.name,
                            company=company,
                            title=title,
                            description=text,
                            location="",
                            apply_url=apply_url,
                            content_hash=_content_hash(company, title, text),
                        )
                    )
                browser.close()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Wellfound scrape failed: {exc}")
            return []

        jobs = _annotate_and_filter_jobs(jobs, profile, allow_stretch=allow_stretch)
        logger.info(f"Wellfound: fetched {len(jobs)} jobs after level filter")
        return jobs


_SOURCES: dict[str, JobSource] = {
    RemotiveSource.name: RemotiveSource(),
    WellfoundSource.name: WellfoundSource(),
}


def get_source(name: str) -> JobSource:
    return _SOURCES.get(name, _SOURCES["remotive"])


class JobScraperAgent:
    def run(
        self,
        profile: UserProfile,
        limit: int = 100,
        source_name: str | None = None,
        allow_stretch: bool = False,
    ) -> list[JobListing]:
        source_name = source_name or settings.job_source
        source = get_source(source_name)
        jobs = source.fetch(profile, limit, allow_stretch=allow_stretch)

        # Fall back to Remotive if the primary source returned nothing.
        if not jobs and source_name != "remotive":
            logger.warning(f"'{source_name}' returned no jobs; falling back to Remotive.")
            jobs = get_source("remotive").fetch(
                profile, limit, allow_stretch=allow_stretch
            )

        jobs = self._dedup(jobs)
        self._snapshot(jobs, source_name)
        return jobs

    @staticmethod
    def _dedup(jobs: list[JobListing]) -> list[JobListing]:
        seen: set[str] = set()
        unique: list[JobListing] = []
        for job in jobs:
            if job.content_hash in seen:
                continue
            seen.add(job.content_hash)
            unique.append(job)
        return unique

    @staticmethod
    def _snapshot(jobs: list[JobListing], source_name: str) -> None:
        """Persist a raw JSON snapshot for debugging."""
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = Path(settings.jobs_dir) / f"{source_name}_{stamp}.json"
        try:
            path.write_text(
                json.dumps([j.model_dump(mode="json") for j in jobs], indent=2),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not write job snapshot: {exc}")
