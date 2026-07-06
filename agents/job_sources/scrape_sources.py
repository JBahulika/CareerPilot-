"""Playwright-based job board scrapers (best-effort)."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote_plus

from agents.job_sources.common import (
    annotate_and_filter_jobs,
    build_job,
    search_location,
    search_terms,
    sort_and_filter_recent,
)
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)


def _playwright_fetch_cards(url: str, selectors: list[str], limit: int) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed.")
        return []

    results: list[dict] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            cards = []
            for sel in selectors:
                cards = page.query_selector_all(sel)
                if cards:
                    break
            for card in cards[:limit]:
                text = card.inner_text().strip()
                if not text:
                    continue
                lines = [ln for ln in text.split("\n") if ln.strip()]
                link_el = card.query_selector("a")
                href = (link_el.get_attribute("href") or "") if link_el else ""
                results.append(
                    {
                        "title": lines[0] if lines else "",
                        "company": lines[1] if len(lines) > 1 else "",
                        "location": lines[2] if len(lines) > 2 else "",
                        "description": text,
                        "apply_url": href,
                    }
                )
            browser.close()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Playwright scrape failed for {url}: {exc}")
    return results


def _finalize_scrape(jobs, profile, allow_stretch, flex_years, source_name) -> list[JobListing]:
    jobs = annotate_and_filter_jobs(
        jobs, profile, allow_stretch=allow_stretch, flex_years=flex_years
    )
    jobs = sort_and_filter_recent(jobs)
    logger.info(f"{source_name}: {len(jobs)} jobs after filters")
    return jobs


class WellfoundSource:
    name = "wellfound"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        role = (search_terms(profile).split(" ")[0] or "engineer").lower()
        url = f"https://wellfound.com/role/{role}"
        cards = _playwright_fetch_cards(
            url,
            ["[data-test='JobSearchResult']", ".styles_component__Ns_gK", "div[data-testid*='job']"],
            limit,
        )
        now = datetime.utcnow()
        jobs = []
        for card in cards:
            apply_url = card["apply_url"]
            if apply_url.startswith("/"):
                apply_url = f"https://wellfound.com{apply_url}"
            jobs.append(
                build_job(
                    source=self.name,
                    company=card["company"],
                    title=card["title"],
                    description=card["description"],
                    location=card.get("location", ""),
                    apply_url=apply_url,
                    posted_at=now,
                )
            )
        return _finalize_scrape(jobs, profile, allow_stretch, flex_years, self.name)


class IndeedSource:
    name = "indeed"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = quote_plus(search_terms(profile))
        loc = search_location(profile)
        url = f"https://www.indeed.com/jobs?q={query}&sort=date"
        if loc:
            url += f"&l={quote_plus(loc)}"
        cards = _playwright_fetch_cards(
            url,
            [".job_seen_beacon", ".jobsearch-ResultsList li", "div[data-jk]"],
            limit,
        )
        jobs = [
            build_job(
                source=self.name,
                company=card["company"],
                title=card["title"],
                description=card["description"],
                location=card.get("location", ""),
                apply_url=f"https://www.indeed.com{card['apply_url']}"
                if card["apply_url"].startswith("/")
                else card["apply_url"],
            )
            for card in cards
        ]
        return _finalize_scrape(jobs, profile, allow_stretch, flex_years, self.name)


class NaukriSource:
    name = "naukri"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = quote_plus(search_terms(profile))
        loc = search_location(profile)
        slug = query.replace("+", "-")
        if loc:
            loc_slug = quote_plus(loc).replace("+", "-").lower()
            url = f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
        else:
            url = f"https://www.naukri.com/{slug}-jobs"
        cards = _playwright_fetch_cards(
            url,
            [".cust-job-tuple", ".srp-jobtuple-wrapper", "article.jobTuple"],
            limit,
        )
        jobs = [
            build_job(
                source=self.name,
                company=card["company"],
                title=card["title"],
                description=card["description"],
                location=card.get("location") or (loc or "India"),
                apply_url=card["apply_url"] if card["apply_url"].startswith("http") else f"https://www.naukri.com{card['apply_url']}",
            )
            for card in cards
        ]
        return _finalize_scrape(jobs, profile, allow_stretch, flex_years, self.name)


class LinkedInSource:
    name = "linkedin"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = quote_plus(search_terms(profile))
        loc = search_location(profile)
        url = f"https://www.linkedin.com/jobs/search/?keywords={query}&sortBy=DD"
        if loc:
            url += f"&location={quote_plus(loc)}"
        cards = _playwright_fetch_cards(
            url,
            [".base-card", "li.jobs-search__results-list div", "div.job-search-card"],
            limit,
        )
        jobs = [
            build_job(
                source=self.name,
                company=card["company"],
                title=card["title"],
                description=card["description"],
                location=card.get("location", ""),
                apply_url=card["apply_url"] if card["apply_url"].startswith("http") else "",
            )
            for card in cards
        ]
        return _finalize_scrape(jobs, profile, allow_stretch, flex_years, self.name)


class GlassdoorSource:
    name = "glassdoor"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        query = quote_plus(search_terms(profile))
        loc = search_location(profile)
        url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&sortBy=date"
        if loc:
            url += f"&locKeyword={quote_plus(loc)}"
        cards = _playwright_fetch_cards(
            url,
            ["li.react-job-listing", "article.JobCard", "div[data-test='jobListing']"],
            limit,
        )
        jobs = [
            build_job(
                source=self.name,
                company=card["company"],
                title=card["title"],
                description=card["description"],
                location=card.get("location", ""),
                apply_url=card["apply_url"] if card["apply_url"].startswith("http") else "",
            )
            for card in cards
        ]
        return _finalize_scrape(jobs, profile, allow_stretch, flex_years, self.name)
