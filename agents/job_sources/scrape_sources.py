"""Playwright-based job board scrapers (best-effort).

Same approach as pre–Phase 2: open the search URL, wait, parse card selectors.
Captchas are never solved; if the page is a wall, card selectors usually yield
zero results and the source simply contributes nothing.

Uses up to 2 focused search queries (budget split) instead of one mega-string.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from agents.job_sources.common import (
    annotate_and_filter_jobs,
    build_job,
    search_location,
    search_queries,
    search_terms,
    sort_and_filter_recent,
    split_limit_across_queries,
)
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)

# Playwright is expensive — cap multi-query fan-out (still cover adjacent roles).
_PLAYWRIGHT_MAX_QUERIES = 3


def _playwright_fetch_cards(
    url: str, selectors: list[str], limit: int, *, source_id: str = ""
) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed.")
        return []

    from core.config import settings
    from services.cookies import load_playwright_cookies, source_has_cookies
    from services.scrape_http import assert_page_not_captcha, playwright_user_agent

    use_cookies = bool(source_id and source_has_cookies(source_id))
    wait_ms = 5000 if use_cookies else 3000
    if use_cookies and bool(getattr(settings, "scrape_cookies_strict", True)):
        # Extra polite pause before cookie-authenticated browser traffic
        import time as _time

        lo = max(0, int(getattr(settings, "scrape_cookie_min_delay_ms", 1500)))
        hi = max(lo, int(getattr(settings, "scrape_cookie_max_delay_ms", 4000)))
        _time.sleep((lo + hi) / 2000.0)

    results: list[dict] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=playwright_user_agent())
            if use_cookies:
                cookies = load_playwright_cookies(source_id)
                if cookies:
                    try:
                        context.add_cookies(cookies)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            f"{source_id}: could not apply cookies to browser "
                            f"(check domain/path); continuing without: {type(exc).__name__}"
                        )
            page = context.new_page()
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            try:
                assert_page_not_captcha(page.content(), source_id=source_id or "playwright", url=url)
            except Exception:
                browser.close()
                raise
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
        from services.scrape_http import CaptchaBlockedError

        if isinstance(exc, CaptchaBlockedError):
            logger.warning(f"Playwright captcha_blocked for {url}: {exc}")
            return []
        logger.error(f"Playwright scrape failed for {url}: {exc}")
    return results


def _finalize_scrape(jobs, profile, allow_stretch, flex_years, source_name) -> list[JobListing]:
    jobs = annotate_and_filter_jobs(
        jobs, profile, allow_stretch=allow_stretch, flex_years=flex_years
    )
    jobs = sort_and_filter_recent(jobs)
    logger.info(f"{source_name}: {len(jobs)} jobs after filters")
    return jobs


def _dedupe_jobs(jobs: list[JobListing]) -> list[JobListing]:
    seen: set[str] = set()
    out: list[JobListing] = []
    for job in jobs:
        if job.content_hash in seen:
            continue
        seen.add(job.content_hash)
        out.append(job)
    return out


def _playwright_queries(profile: UserProfile) -> list[str]:
    return search_queries(profile)[:_PLAYWRIGHT_MAX_QUERIES]


class WellfoundSource:
    name = "wellfound"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        role = (search_terms(profile).split(" ")[0] or "engineer").lower()
        url = f"https://wellfound.com/role/{role}"
        cards = _playwright_fetch_cards(
            url,
            ["[data-test='JobSearchResult']", ".styles_component__Ns_gK", "div[data-testid*='job']"],
            limit,
            source_id=self.name,
        )
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
                )
            )
        return _finalize_scrape(jobs, profile, allow_stretch, flex_years, self.name)


class IndeedSource:
    name = "indeed"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        queries = _playwright_queries(profile)
        quotas = split_limit_across_queries(limit, len(queries))
        jobs: list[JobListing] = []
        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue
            q = quote_plus(query)
            url = f"https://www.indeed.com/jobs?q={q}&sort=date"
            if loc:
                url += f"&l={quote_plus(loc)}"
            cards = _playwright_fetch_cards(
                url,
                [".job_seen_beacon", ".jobsearch-ResultsList li", "div[data-jk]"],
                quota,
                source_id=self.name,
            )
            for card in cards:
                jobs.append(
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
                )
        return _finalize_scrape(
            _dedupe_jobs(jobs)[:limit], profile, allow_stretch, flex_years, self.name
        )


class NaukriSource:
    name = "naukri"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        queries = _playwright_queries(profile)
        quotas = split_limit_across_queries(limit, len(queries))
        jobs: list[JobListing] = []
        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue
            slug = quote_plus(query).replace("+", "-")
            if loc:
                loc_slug = quote_plus(loc).replace("+", "-").lower()
                url = f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
            else:
                url = f"https://www.naukri.com/{slug}-jobs"
            cards = _playwright_fetch_cards(
                url,
                [".cust-job-tuple", ".srp-jobtuple-wrapper", "article.jobTuple"],
                quota,
                source_id=self.name,
            )
            for card in cards:
                jobs.append(
                    build_job(
                        source=self.name,
                        company=card["company"],
                        title=card["title"],
                        description=card["description"],
                        location=card.get("location") or (loc or "India"),
                        apply_url=card["apply_url"]
                        if card["apply_url"].startswith("http")
                        else f"https://www.naukri.com{card['apply_url']}",
                    )
                )
        return _finalize_scrape(
            _dedupe_jobs(jobs)[:limit], profile, allow_stretch, flex_years, self.name
        )


class LinkedInSource:
    name = "linkedin"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        queries = _playwright_queries(profile)
        quotas = split_limit_across_queries(limit, len(queries))
        jobs: list[JobListing] = []
        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue
            q = quote_plus(query)
            url = f"https://www.linkedin.com/jobs/search/?keywords={q}&sortBy=DD"
            if loc:
                url += f"&location={quote_plus(loc)}"
            cards = _playwright_fetch_cards(
                url,
                [".base-card", "li.jobs-search__results-list div", "div.job-search-card"],
                quota,
                source_id=self.name,
            )
            for card in cards:
                jobs.append(
                    build_job(
                        source=self.name,
                        company=card["company"],
                        title=card["title"],
                        description=card["description"],
                        location=card.get("location", ""),
                        apply_url=card["apply_url"],
                        apply_base="https://www.linkedin.com",
                    )
                )
        return _finalize_scrape(
            _dedupe_jobs(jobs)[:limit], profile, allow_stretch, flex_years, self.name
        )


class GlassdoorSource:
    name = "glassdoor"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        queries = _playwright_queries(profile)
        quotas = split_limit_across_queries(limit, len(queries))
        jobs: list[JobListing] = []
        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue
            q = quote_plus(query)
            url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&sortBy=date"
            if loc:
                url += f"&locKeyword={quote_plus(loc)}"
            cards = _playwright_fetch_cards(
                url,
                ["li.react-job-listing", "article.JobCard", "div[data-test='jobListing']"],
                quota,
                source_id=self.name,
            )
            for card in cards:
                jobs.append(
                    build_job(
                        source=self.name,
                        company=card["company"],
                        title=card["title"],
                        description=card["description"],
                        location=card.get("location", ""),
                        apply_url=card["apply_url"],
                        apply_base="https://www.glassdoor.com",
                    )
                )
        return _finalize_scrape(
            _dedupe_jobs(jobs)[:limit], profile, allow_stretch, flex_years, self.name
        )
