"""Playwright + public search API job board scrapers (best-effort).

Indeed: prefers Indeed's public GraphQL search API (same approach as JobSpy),
with Playwright SERP as fallback.

Naukri: loads the public search page and captures the site's own
``jobapi/v3/search`` JSON response (no captcha solving). Falls back to DOM cards.

Other boards: Playwright card scrape. Captchas are never solved.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote_plus

import httpx

from agents.job_sources.common import (
    annotate_and_filter_jobs,
    build_job,
    parse_posted_at,
    search_location,
    search_queries,
    search_terms,
    sort_and_filter_recent,
    split_limit_across_queries,
    strip_html,
)
from core.logging import get_logger
from models.schemas import JobListing, UserProfile

logger = get_logger(__name__)

# Playwright / board search fan-out
_PLAYWRIGHT_MAX_QUERIES = 4

# Public Indeed mobile/app GraphQL key (widely used by open-source scrapers e.g. JobSpy).
_INDEED_API_KEY = "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8"
_INDEED_GQL = "https://apis.indeed.com/graphql"


def _playwright_fetch_cards(
    url: str, selectors: list[str], limit: int, *, source_id: str = ""
) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright package missing. Run setup_careerpilot.bat "
            "or: pip install playwright && playwright install chromium"
        ) from None

    from core.config import settings
    from services.cookies import load_playwright_cookies, source_has_cookies
    from services.scrape_http import assert_page_not_captcha, playwright_user_agent

    use_cookies = bool(source_id and source_has_cookies(source_id))
    wait_ms = 5000 if use_cookies else 3500
    if use_cookies and bool(getattr(settings, "scrape_cookies_strict", True)):
        # Extra polite pause before cookie-authenticated browser traffic
        import time as _time

        lo = max(0, int(getattr(settings, "scrape_cookie_min_delay_ms", 1500)))
        hi = max(lo, int(getattr(settings, "scrape_cookie_max_delay_ms", 4000)))
        _time.sleep((lo + hi) / 2000.0)

    results: list[dict] = []
    try:
        with sync_playwright() as p:
            try:
                browser = _playwright_launch_browser(p)
            except Exception as launch_exc:  # noqa: BLE001
                msg = str(launch_exc)
                if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
                    raise RuntimeError(
                        "Playwright Chromium not installed — Indeed/Naukri/LinkedIn "
                        "scrapes need it. Run: .venv\\Scripts\\python -m playwright install chromium "
                        "(or re-run setup_careerpilot.bat)"
                    ) from launch_exc
                raise
            context = browser.new_context(
                user_agent=playwright_user_agent(),
                locale="en-IN",
                viewport={"width": 1365, "height": 900},
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
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
            # Lazy SERPs (LinkedIn / Glassdoor / Indeed) need scroll to hydrate cards
            for _ in range(3):
                try:
                    page.mouse.wheel(0, 1800)
                except Exception:
                    break
                page.wait_for_timeout(800)
            cards = []
            for sel in selectors:
                cards = page.query_selector_all(sel)
                if cards:
                    break
            # Only treat as captcha wall when no listing cards rendered
            if not cards:
                try:
                    assert_page_not_captcha(
                        page.content(), source_id=source_id or "playwright", url=url
                    )
                except Exception:
                    browser.close()
                    raise
            for card in cards[: max(limit, 1)]:
                text = card.inner_text().strip()
                if not text:
                    continue
                lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                link_el = (
                    card.query_selector(
                        "a[href*='/jobs/'], a[href*='job'], h2 a, a.jcs-JobTitle, a.title"
                    )
                    or card.query_selector("a")
                )
                href = (link_el.get_attribute("href") or "") if link_el else ""
                parsed = _parse_card_fields(lines, source_id=source_id)
                results.append(
                    {
                        "title": parsed["title"],
                        "company": parsed["company"],
                        "location": parsed["location"],
                        "description": text,
                        "apply_url": href,
                        "posted_hint": parsed.get("posted_hint", ""),
                    }
                )
            browser.close()
    except Exception as exc:  # noqa: BLE001
        from services.scrape_http import CaptchaBlockedError

        if isinstance(exc, CaptchaBlockedError):
            logger.warning(f"Playwright captcha_blocked for {url}: {exc}")
            return []
        if isinstance(exc, RuntimeError) and "Playwright" in str(exc):
            raise
        logger.error(f"Playwright scrape failed for {url}: {exc}")
    return results


def _parse_card_fields(lines: list[str], *, source_id: str = "") -> dict[str, str]:
    """Best-effort title/company/location from board card text lines."""
    import re

    title = lines[0] if lines else ""
    company = lines[1] if len(lines) > 1 else ""
    location = lines[2] if len(lines) > 2 else ""
    posted_hint = ""

    if source_id == "naukri":
        # title / company / rating / Reviews / 3-7 Yrs / Bengaluru / ... / 3 weeks ago
        company = lines[1] if len(lines) > 1 else ""
        location = ""
        for ln in lines[2:]:
            low = ln.lower()
            if re.fullmatch(r"\d+(?:\.\d+)?", ln):
                continue
            if "review" in low:
                continue
            if re.search(r"\d+\s*-\s*\d+\s*yrs?", low) or re.search(r"\d+\+?\s*yrs?", low):
                continue
            if re.search(r"\b(ago|today|just now|few hours)\b", low):
                posted_hint = ln
                continue
            if low in {"save", "apply", "remote", "hybrid", "prefers women"}:
                continue
            # First remaining short line is usually the city
            if not location and len(ln) < 60 and not ln.lower().startswith("expertise"):
                location = ln
                break
        if not location:
            location = "India"

    elif source_id == "indeed":
        # title / company / location / Full-time / optional date
        for ln in lines[2:]:
            low = ln.lower()
            if re.search(r"\b(ago|today|just posted|posted)\b", low):
                posted_hint = ln
            if low in {"full-time", "part-time", "contract", "temporary", "internship"}:
                continue
            if not location or location.lower() in {"full-time", "part-time"}:
                if len(ln) < 80:
                    location = ln
                    break

    return {
        "title": title,
        "company": company,
        "location": location,
        "posted_hint": posted_hint,
    }


def _naukri_location_slug(profile: UserProfile) -> str:
    """Naukri URLs want a short city slug (bangalore), not 'Bengaluru, Karnataka, India'."""
    from services.location import resolve_cities

    loc = search_location(profile)
    if not loc:
        return ""
    cities = resolve_cities(loc)
    if cities:
        # Naukri historically uses Bangalore spelling
        slug_map = {"bengaluru": "bangalore", "gurugram": "gurgaon", "delhi": "delhi"}
        raw = slug_map.get(cities[0].canonical, cities[0].canonical)
        return raw.replace(" ", "-")
    # fallback: first comma segment
    return loc.split(",")[0].strip().lower().replace(" ", "-")


def _playwright_launch_browser(p):  # type: ignore[no-untyped-def]
    """Prefer system Chrome when present (less bot-blocked than stock Chromium)."""
    args = ["--disable-blink-features=AutomationControlled"]
    try:
        return p.chromium.launch(headless=True, channel="chrome", args=args)
    except Exception:
        return p.chromium.launch(headless=True, args=args)


def _indeed_host(profile: UserProfile) -> str:
    """Prefer India Indeed when the profile location looks Indian."""
    loc = (search_location(profile) or "").lower()
    india_markers = (
        "india",
        "bengaluru",
        "bangalore",
        "mumbai",
        "delhi",
        "hyderabad",
        "chennai",
        "pune",
        "kolkata",
        "gurgaon",
        "gurugram",
        "noida",
        "ahmedabad",
        "jaipur",
        "kochi",
        "coimbatore",
    )
    if any(m in loc for m in india_markers):
        return "https://in.indeed.com"
    return "https://www.indeed.com"


def _indeed_country_code(profile: UserProfile) -> str:
    return "IN" if _indeed_host(profile).startswith("https://in.") else "US"


def _indeed_graphql_jobs(
    profile: UserProfile, query: str, limit: int
) -> list[JobListing]:
    """Fetch Indeed via public GraphQL with cursor pagination (JobSpy-style).

    Pulls multiple pages (up to 100/page) so seniority/location filters still
    leave a healthy set — a single page of date-sorted seniors looked "empty".
    """
    host = _indeed_host(profile)
    country = _indeed_country_code(profile)
    loc = search_location(profile)
    where = loc.split(",")[0].strip() if loc else ""
    safe_q = (query or "").replace("\\", "\\\\").replace('"', '\\"').strip()
    what_line = f'what: "{safe_q}"' if safe_q else ""
    # Wider radius than 50mi — India metros sprawl; matches website "distance" feel
    radius = 100 if country == "IN" else 50
    loc_line = (
        f'location: {{where: "{where.replace(chr(34), "")}", radius: {radius}, radiusUnit: MILES}}'
        if where
        else ""
    )

    target = max(int(limit), 60)
    max_pages = 5
    page_size = 100
    cursor: str | None = None
    jobs: list[JobListing] = []
    seen_keys: set[str] = set()

    headers = {
        "Host": "apis.indeed.com",
        "content-type": "application/json",
        "indeed-api-key": _INDEED_API_KEY,
        "accept": "application/json",
        "indeed-locale": "en-IN" if country == "IN" else "en-US",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1"
        ),
        "indeed-app-info": (
            "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone"
        ),
        "indeed-co": country,
    }

    for page in range(max_pages):
        if len(jobs) >= target:
            break
        cursor_line = f'cursor: "{cursor}"' if cursor else ""
        # RELEVANCE matches what users see in the app/search box; DATE alone
        # over-indexes brand-new senior postings.
        gql = f"""
        query GetJobData {{
          jobSearch(
            {what_line}
            {loc_line}
            limit: {page_size}
            {cursor_line}
            sort: RELEVANCE
          ) {{
            pageInfo {{
              nextCursor
            }}
            results {{
              job {{
                key
                title
                datePublished
                description {{ html }}
                location {{
                  city
                  admin1Code
                  countryCode
                  formatted {{ short }}
                }}
                employer {{ name }}
              }}
            }}
          }}
        }}
        """
        try:
            resp = httpx.post(
                _INDEED_GQL, headers=headers, json={"query": gql}, timeout=30.0
            )
            if resp.status_code != 200:
                logger.warning(
                    f"indeed GraphQL HTTP {resp.status_code} page={page + 1}"
                )
                break
            payload = resp.json()
            if payload.get("errors"):
                logger.warning(
                    f"indeed GraphQL errors: {str(payload['errors'])[:200]}"
                )
            block = (payload.get("data") or {}).get("jobSearch") or {}
            results = block.get("results") or []
            next_cursor = (block.get("pageInfo") or {}).get("nextCursor")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"indeed GraphQL failed page={page + 1}: {exc}")
            break

        if not results:
            break

        for row in results:
            job = (row or {}).get("job") or {}
            key = job.get("key") or ""
            title = job.get("title") or ""
            if not title or (key and key in seen_keys):
                continue
            if key:
                seen_keys.add(key)
            employer = (job.get("employer") or {}).get("name") or ""
            loc_obj = job.get("location") or {}
            location = (
                ((loc_obj.get("formatted") or {}).get("short"))
                or ", ".join(
                    x
                    for x in (
                        loc_obj.get("city"),
                        loc_obj.get("admin1Code"),
                        loc_obj.get("countryCode"),
                    )
                    if x
                )
            )
            desc_html = ((job.get("description") or {}).get("html")) or ""
            posted = None
            ts = job.get("datePublished")
            if isinstance(ts, (int, float)) and ts > 0:
                try:
                    posted = datetime.utcfromtimestamp(float(ts) / 1000.0)
                except (OSError, OverflowError, ValueError):
                    posted = None
            apply_url = f"{host}/viewjob?jk={key}" if key else host
            jobs.append(
                build_job(
                    source="indeed",
                    company=employer,
                    title=title,
                    description=strip_html(desc_html) or title,
                    location=location,
                    apply_url=apply_url,
                    apply_base=host,
                    posted_at=posted,
                )
            )

        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    logger.info(
        f"indeed GraphQL returned {len(jobs)} for {safe_q!r} "
        f"(target={target}, country={country})"
    )
    return jobs


def _naukri_jobs_from_payloads(
    payloads: list[dict], *, limit: int
) -> list[JobListing]:
    """Flatten Naukri jobapi payloads into JobListing rows (deduped by jdURL)."""
    jobs: list[JobListing] = []
    seen: set[str] = set()
    for data in payloads:
        for item in data.get("jobDetails") or []:
            if len(jobs) >= limit:
                return jobs
            title = item.get("title") or ""
            company = item.get("companyName") or ""
            if not title:
                continue
            jd_url = item.get("jdURL") or ""
            key = str(jd_url or item.get("jobId") or title)
            if key in seen:
                continue
            seen.add(key)
            apply_url = (
                jd_url
                if str(jd_url).startswith("http")
                else f"https://www.naukri.com{jd_url}"
            )
            placeholders = item.get("placeholders") or []
            location = "India"
            for ph in placeholders:
                if (ph or {}).get("type") == "location" and ph.get("label"):
                    location = str(ph["label"])
                    break
            skills_raw = item.get("tagsAndSkills") or ""
            skills = [s.strip() for s in str(skills_raw).split(",") if s.strip()]
            posted = parse_posted_at(item.get("footerPlaceholderLabel"))
            if posted is None and item.get("createdDate"):
                try:
                    posted = datetime.utcfromtimestamp(
                        float(item["createdDate"]) / 1000.0
                    )
                except (OSError, OverflowError, ValueError, TypeError):
                    posted = None
            jobs.append(
                build_job(
                    source="naukri",
                    company=company,
                    title=title,
                    description=strip_html(item.get("jobDescription") or "") or title,
                    skills=skills,
                    location=location,
                    apply_url=apply_url,
                    apply_base="https://www.naukri.com",
                    posted_at=posted,
                )
            )
    return jobs


def _naukri_capture_api_jobs(url: str, limit: int) -> list[JobListing]:
    """Load Naukri SERP in Playwright and capture the page's own jobapi JSON.

    Visits page 1–3 of the SERP (``…-jobs-in-city`` / ``…-jobs-in-city-2``)
    so we get closer to what the website shows than a single XHR snapshot.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    from services.scrape_http import playwright_user_agent

    capture_limit = max(int(limit) * 3, 40)
    base = url.rstrip("/")
    # Strip trailing -N page suffix if present so we can walk pages cleanly
    import re

    base = re.sub(r"-\d+$", "", base)
    page_urls = [base] + [f"{base}-{n}" for n in (2, 3)]
    captured: list[dict] = []
    try:
        with sync_playwright() as p:
            browser = _playwright_launch_browser(p)
            context = browser.new_context(
                user_agent=playwright_user_agent(),
                locale="en-IN",
                viewport={"width": 1365, "height": 900},
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = context.new_page()

            def _on_response(response) -> None:  # type: ignore[no-untyped-def]
                try:
                    if "jobapi/v3/search" not in response.url:
                        return
                    if response.status != 200:
                        return
                    data = response.json()
                    if isinstance(data, dict) and data.get("jobDetails"):
                        captured.append(data)
                except Exception:
                    return

            page.on("response", _on_response)
            for page_url in page_urls:
                if len(_naukri_jobs_from_payloads(captured, limit=capture_limit)) >= capture_limit:
                    break
                page.goto(page_url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2200)
                for _ in range(2):
                    try:
                        page.mouse.wheel(0, 1600)
                    except Exception:
                        break
                    page.wait_for_timeout(900)
                page.wait_for_timeout(1800)
            browser.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"naukri API capture failed: {exc}")
        return []

    if not captured:
        return []

    jobs = _naukri_jobs_from_payloads(captured, limit=capture_limit)
    logger.info(f"naukri jobapi capture returned {len(jobs)} across {len(captured)} payloads")
    return jobs

def _finalize_scrape(jobs, profile, allow_stretch, flex_years, source_name) -> list[JobListing]:
    # Stamp undated scrape hits so a fail-closed recency window does not
    # discard every SERP card that omitted a parseable date.
    now = datetime.utcnow()
    for job in jobs:
        if job.posted_at is None:
            job.posted_at = now

    jobs = annotate_and_filter_jobs(
        jobs, profile, allow_stretch=allow_stretch, flex_years=flex_years
    )
    before_recency = len(jobs)
    recent = sort_and_filter_recent(jobs)
    # Naukri (and some Indeed results) often date 4–14d old; a 3-day default
    # window would make a healthy scrape look "broken". Prefer annotated set.
    if before_recency and not recent:
        logger.info(
            f"{source_name}: recency window dropped all {before_recency} jobs; "
            "keeping seniority/location-filtered set"
        )
        jobs = jobs
    else:
        jobs = recent
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
        queries = _playwright_queries(profile)
        # Don't starve each query with tiny quotas — pull a full page-worth
        # per query, then filter/dedupe down to ``limit``.
        per_query = max(80, int(limit))
        jobs: list[JobListing] = []

        for query in queries:
            jobs.extend(_indeed_graphql_jobs(profile, query, per_query))
            if len(jobs) >= limit * 4:
                break
        jobs = _dedupe_jobs(jobs)

        # Fallback: Playwright SERP if API returned nothing
        if not jobs:
            loc = search_location(profile)
            host = _indeed_host(profile)
            logger.info("indeed: GraphQL empty — falling back to Playwright SERP")
            from agents.job_sources.common import coerce_posted_at

            quotas = split_limit_across_queries(max(limit, 30), len(queries))
            for query, quota in zip(queries, quotas):
                if quota <= 0:
                    continue
                q = quote_plus(query)
                url = f"{host}/jobs?q={q}&sort=date"
                if loc:
                    url += f"&l={quote_plus(loc.split(',')[0].strip())}"
                cards = _playwright_fetch_cards(
                    url,
                    [
                        ".job_seen_beacon",
                        "div.job_seen_beacon",
                        "a.jcs-JobTitle",
                        "#mosaic-provider-jobcards li",
                        "div[data-jk]",
                        ".jobsearch-ResultsList li",
                    ],
                    max(quota, 15),
                    source_id=self.name,
                )
                for card in cards:
                    href = card["apply_url"] or ""
                    if href.startswith("/"):
                        href = f"{host}{href}"
                    jobs.append(
                        build_job(
                            source=self.name,
                            company=card["company"],
                            title=card["title"],
                            description=card["description"],
                            location=card.get("location", ""),
                            apply_url=href,
                            apply_base=host,
                            posted_at=coerce_posted_at(
                                fallback_text=card.get("posted_hint")
                                or card.get("description", "")[:400]
                            ),
                        )
                    )
        # Mild stretch by default for board scrapes so mid-senior titles near
        # the profile band are not wiped when the SERP skews senior.
        flex = flex_years if flex_years is not None else 2
        return _finalize_scrape(
            _dedupe_jobs(jobs)[: max(limit * 3, limit)],
            profile,
            True,
            flex,
            self.name,
        )[:limit]


class NaukriSource:
    name = "naukri"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        loc_slug = _naukri_location_slug(profile)
        queries = _playwright_queries(profile)
        per_query = max(40, int(limit))
        jobs: list[JobListing] = []

        # Primary: let Naukri's page call jobapi, capture JSON (no captcha solve)
        for query in queries:
            slug = quote_plus(query).replace("+", "-").lower()
            url = (
                f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
                if loc_slug
                else f"https://www.naukri.com/{slug}-jobs"
            )
            jobs.extend(_naukri_capture_api_jobs(url, per_query))
            if len(jobs) >= limit * 3:
                break

        jobs = _dedupe_jobs(jobs)

        # Fallback: DOM cards if network capture missed jobapi
        if not jobs:
            logger.info("naukri: jobapi capture empty — falling back to DOM cards")
            quotas = split_limit_across_queries(max(limit, 30), len(queries))
            for query, quota in zip(queries, quotas):
                if quota <= 0:
                    continue
                slug = quote_plus(query).replace("+", "-").lower()
                url = (
                    f"https://www.naukri.com/{slug}-jobs-in-{loc_slug}"
                    if loc_slug
                    else f"https://www.naukri.com/{slug}-jobs"
                )
                cards = _playwright_fetch_cards(
                    url,
                    [
                        ".srp-jobtuple-wrapper",
                        ".cust-job-tuple",
                        "div.srp-jobtuple-wrapper",
                        "article.jobTuple",
                        "div[data-job-id]",
                        ".jobTuple",
                    ],
                    max(quota, 20),
                    source_id=self.name,
                )
                for card in cards:
                    from agents.job_sources.common import coerce_posted_at

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
                            apply_base="https://www.naukri.com",
                            posted_at=coerce_posted_at(
                                fallback_text=card.get("posted_hint")
                                or card.get("description", "")[:400]
                            ),
                        )
                    )
        flex = flex_years if flex_years is not None else 2
        return _finalize_scrape(
            _dedupe_jobs(jobs)[: max(limit * 3, limit)],
            profile,
            True,
            flex,
            self.name,
        )[:limit]


class LinkedInSource:
    name = "linkedin"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        queries = _playwright_queries(profile)
        # Guest LinkedIn SERP is thin; oversample cards then filter down
        quotas = split_limit_across_queries(max(limit, 25), len(queries))
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
                [
                    ".base-card",
                    "li.jobs-search__results-list div",
                    "div.job-search-card",
                    "div.base-search-card",
                    "ul.jobs-search__results-list li",
                ],
                max(quota, 15),
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
        flex = flex_years if flex_years is not None else 2
        return _finalize_scrape(
            _dedupe_jobs(jobs)[: max(limit * 2, limit)],
            profile,
            True,
            flex,
            self.name,
        )[:limit]


class GlassdoorSource:
    name = "glassdoor"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        loc = search_location(profile)
        queries = _playwright_queries(profile)
        quotas = split_limit_across_queries(max(limit, 25), len(queries))
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
                [
                    "li.react-job-listing",
                    "article.JobCard",
                    "div[data-test='jobListing']",
                    "li[data-test='jobListing']",
                    "ul.JobsList_jobsList__lqjnz li",
                ],
                max(quota, 15),
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
        flex = flex_years if flex_years is not None else 2
        return _finalize_scrape(
            _dedupe_jobs(jobs)[: max(limit * 2, limit)],
            profile,
            True,
            flex,
            self.name,
        )[:limit]
