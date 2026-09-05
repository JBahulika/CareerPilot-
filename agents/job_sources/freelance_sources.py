"""Freelance marketplace adapters (API / RSS / Playwright).

Prefer public JSON/RSS. Playwright boards are best-effort and never solve captchas.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from agents.job_sources.api_sources import _finalize, _parse_rss_items
from agents.job_sources.common import (
    build_job,
    parse_posted_at,
    search_location,
    search_queries,
    split_limit_across_queries,
    strip_html,
)
from core.logging import get_logger
from models.schemas import JobListing
from services.scrape_http import CaptchaBlockedError, RateLimitedError, get_scrape_client
from services.source_health import get_source_health_registry

logger = get_logger(__name__)

_GENERIC_CARD_SELECTORS = [
    "article",
    "li[class*='job']",
    "div[class*='job-card']",
    "div[class*='JobCard']",
    "div[class*='jobCard']",
    "div[data-test*='job']",
    "div[data-testid*='job']",
    "a[href*='/job']",
]


def _format_search_url(pattern: str, query: str, location: str) -> str:
    q = quote_plus(query)
    slug = quote_plus(query).replace("+", "-").lower()
    loc = quote_plus(location) if location else ""
    return (
        pattern.replace("{query}", q)
        .replace("{query_slug}", slug)
        .replace("{location}", loc)
    )


@dataclass(frozen=True)
class PlaywrightBoardSpec:
    id: str
    display_name: str
    apply_base: str
    url_pattern: str
    selectors: tuple[str, ...]
    enabled_by_default: bool = False
    region: str = "global"
    notes: str = "Best-effort Playwright; never solves captchas"

    def registry_row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.display_name,
            "method": "scrape",
            "safety": "scrape_risky",
            "enabled_by_default": self.enabled_by_default,
            "region": self.region,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RssBoardSpec:
    id: str
    display_name: str
    feed_url: str
    apply_base: str
    enabled_by_default: bool = True
    region: str = "global"
    notes: str = "Public RSS feed"

    def registry_row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.display_name,
            "method": "rss",
            "safety": "api",
            "enabled_by_default": self.enabled_by_default,
            "region": self.region,
            "notes": self.notes,
        }


# Major marketplaces default-on; long-tail / login-walled boards stay opt-in
# so a default scan does not spawn dozens of Playwright sessions.
FREELANCE_PLAYWRIGHT_SPECS: tuple[PlaywrightBoardSpec, ...] = (
    PlaywrightBoardSpec(
        id="upwork",
        display_name="Upwork",
        apply_base="https://www.upwork.com",
        url_pattern="https://www.upwork.com/nx/search/jobs/?q={query}&sort=recency",
        selectors=(
            "article[data-test='JobTile']",
            "section[data-test='JobTile']",
            "article.job-tile",
            "[data-ev-sublocation='job_feed_tile']",
        ),
        enabled_by_default=True,
        notes="Best-effort Playwright (RSS retired 2024); never solves captchas",
    ),
    PlaywrightBoardSpec(
        id="guru",
        display_name="Guru",
        apply_base="https://www.guru.com",
        url_pattern="https://www.guru.com/d/jobs/q/{query_slug}/",
        selectors=(".jobRecord", ".job-listing", "div.record", "article"),
        enabled_by_default=True,
    ),
    PlaywrightBoardSpec(
        id="peopleperhour",
        display_name="PeoplePerHour",
        apply_base="https://www.peopleperhour.com",
        url_pattern="https://www.peopleperhour.com/freelance-jobs?q={query}",
        selectors=(".job-list-item", "[data-qa='job-card']", "article", "li.job"),
        enabled_by_default=True,
    ),
    PlaywrightBoardSpec(
        id="internshala",
        display_name="Internshala",
        apply_base="https://internshala.com",
        url_pattern="https://internshala.com/internships/keywords-{query_slug}/",
        selectors=(
            ".individual_internship",
            ".internship_meta",
            "div.container-item",
            "div[id*='internship']",
        ),
        enabled_by_default=True,
        region="india",
        notes="Public internship/freelance SERP; Playwright; never solves captchas",
    ),
    PlaywrightBoardSpec(
        id="truelancer",
        display_name="Truelancer",
        apply_base="https://www.truelancer.com",
        url_pattern="https://www.truelancer.com/freelance-jobs?search={query}",
        selectors=(".job-item", ".jobList", "div.job-card", "article"),
        enabled_by_default=True,
        region="india",
    ),
    PlaywrightBoardSpec(
        id="workana",
        display_name="Workana",
        apply_base="https://www.workana.com",
        url_pattern="https://www.workana.com/jobs?query={query}",
        selectors=("article.project", ".project-item", "div.project-card", "article"),
        enabled_by_default=True,
        region="latam",
    ),
    PlaywrightBoardSpec(
        id="freelancermap",
        display_name="freelancermap",
        apply_base="https://www.freelancermap.com",
        url_pattern="https://www.freelancermap.com/project/search?query={query}",
        selectors=("div.project-item", "article.project", "li.project", "article"),
        enabled_by_default=True,
        region="eu",
    ),
    PlaywrightBoardSpec(
        id="worknhire",
        display_name="WorknHire",
        apply_base="https://www.worknhire.com",
        url_pattern="https://www.worknhire.com/jobs?q={query}",
        selectors=("div.job-list", "div.job-card", "article", "li"),
        enabled_by_default=True,
        region="india",
    ),
    PlaywrightBoardSpec(
        id="fiverr",
        display_name="Fiverr",
        apply_base="https://www.fiverr.com",
        url_pattern="https://www.fiverr.com/search/gigs?query={query}",
        selectors=("div.gig-card-layout", "article", "div[class*='gig']"),
        notes="Gig marketplace (not buyer requests); login-walled RFQs skipped",
    ),
    PlaywrightBoardSpec(
        id="toptal",
        display_name="Toptal",
        apply_base="https://www.toptal.com",
        url_pattern="https://www.toptal.com/freelance-jobs",
        selectors=("article", "div[class*='job']", "li[class*='job']"),
        notes="Invite-heavy; public freelance-jobs page only",
    ),
    PlaywrightBoardSpec(
        id="malt",
        display_name="Malt",
        apply_base="https://www.malt.com",
        url_pattern="https://www.malt.com/s?q={query}",
        selectors=("article", "div[class*='mission']", "li[class*='job']"),
        region="eu",
    ),
    PlaywrightBoardSpec(
        id="twago",
        display_name="Twago",
        apply_base="https://www.twago.com",
        url_pattern="https://www.twago.com/s/?q={query}",
        selectors=("article", "div.project", "li[class*='job']"),
        region="eu",
    ),
    PlaywrightBoardSpec(
        id="contra",
        display_name="Contra",
        apply_base="https://contra.com",
        url_pattern="https://contra.com/search?q={query}",
        selectors=("article", "a[href*='/opportunity']", "div[class*='job']"),
    ),
    PlaywrightBoardSpec(
        id="arc",
        display_name="Arc.dev",
        apply_base="https://arc.dev",
        url_pattern="https://arc.dev/remote-jobs?search={query}",
        selectors=("article", "div[class*='job']", "a[href*='/job']"),
    ),
    PlaywrightBoardSpec(
        id="turing",
        display_name="Turing",
        apply_base="https://www.turing.com",
        url_pattern="https://www.turing.com/jobs?search={query}",
        selectors=("article", "div[class*='job']", "a[href*='/job']"),
    ),
    PlaywrightBoardSpec(
        id="lemonio",
        display_name="Lemon.io",
        apply_base="https://lemon.io",
        url_pattern="https://lemon.io/for-developers/",
        selectors=("article", "div[class*='job']", "section"),
    ),
    PlaywrightBoardSpec(
        id="braintrust",
        display_name="Braintrust",
        apply_base="https://www.usebraintrust.com",
        url_pattern="https://www.usebraintrust.com/talent/opportunities?q={query}",
        selectors=("article", "div[class*='job']", "a[href*='/job']"),
    ),
    PlaywrightBoardSpec(
        id="gunio",
        display_name="Gun.io",
        apply_base="https://www.gun.io",
        url_pattern="https://www.gun.io/jobs",
        selectors=("article", "div[class*='job']", "a[href*='/job']"),
    ),
    PlaywrightBoardSpec(
        id="codementor",
        display_name="Codementor",
        apply_base="https://www.codementor.io",
        url_pattern="https://www.codementor.io/freelance-jobs",
        selectors=("article", "div[class*='job']", "li[class*='job']"),
    ),
    PlaywrightBoardSpec(
        id="onlinejobsph",
        display_name="OnlineJobs.ph",
        apply_base="https://www.onlinejobs.ph",
        url_pattern="https://www.onlinejobs.ph/jobseekers/jobsearch?jobkeyword={query}",
        selectors=("div.jobpost", "div.job-item", "article", "li"),
        region="ph",
    ),
    PlaywrightBoardSpec(
        id="outsourcely",
        display_name="Outsourcely",
        apply_base="https://www.outsourcely.com",
        url_pattern="https://www.outsourcely.com/remote-workers",
        selectors=("article", "div[class*='job']", "li"),
    ),
    PlaywrightBoardSpec(
        id="authenticjobs",
        display_name="Authentic Jobs",
        apply_base="https://authenticjobs.com",
        url_pattern="https://authenticjobs.com/?search_keywords={query}",
        selectors=("article", "li.job", "div.job"),
    ),
    PlaywrightBoardSpec(
        id="ninetyninedesigns",
        display_name="99designs",
        apply_base="https://99designs.com",
        url_pattern="https://99designs.com/contests",
        selectors=("article", "div[class*='contest']", "li"),
        notes="Design contests (not classic job posts); Playwright",
    ),
    PlaywrightBoardSpec(
        id="crowdspring",
        display_name="crowdSPRING",
        apply_base="https://www.crowdspring.com",
        url_pattern="https://www.crowdspring.com/contests/",
        selectors=("article", "div[class*='contest']", "li"),
        notes="Design contests; Playwright",
    ),
    PlaywrightBoardSpec(
        id="dribbble",
        display_name="Dribbble Jobs",
        apply_base="https://dribbble.com",
        url_pattern="https://dribbble.com/jobs?utf8=%E2%9C%93&keyword={query}",
        selectors=("article", "li.job", "div[class*='job']"),
    ),
    PlaywrightBoardSpec(
        id="flexjobs",
        display_name="FlexJobs",
        apply_base="https://www.flexjobs.com",
        url_pattern="https://www.flexjobs.com/search?search={query}&location={location}",
        selectors=("article", "li.job", "div.job"),
        notes="Many listings behind paywall; Playwright public SERP only",
    ),
    PlaywrightBoardSpec(
        id="sribulancer",
        display_name="Sribulancer",
        apply_base="https://www.sribulancer.com",
        url_pattern="https://www.sribulancer.com/en/jobs?q={query}",
        selectors=("article", "div.job", "li"),
        region="sea",
    ),
    PlaywrightBoardSpec(
        id="andela",
        display_name="Andela",
        apply_base="https://andela.com",
        url_pattern="https://andela.com",
        selectors=("article", "a[href*='job']", "div[class*='job']"),
    ),
    PlaywrightBoardSpec(
        id="revelo",
        display_name="Revelo",
        apply_base="https://www.revelo.com",
        url_pattern="https://www.revelo.com",
        selectors=("article", "a[href*='job']", "div[class*='job']"),
        region="latam",
    ),
    PlaywrightBoardSpec(
        id="ateam",
        display_name="A.Team",
        apply_base="https://www.a.team",
        url_pattern="https://www.a.team",
        selectors=("article", "a[href*='mission']", "div[class*='job']"),
    ),
)

FREELANCE_RSS_SPECS: tuple[RssBoardSpec, ...] = (
    RssBoardSpec(
        id="jobspresso",
        display_name="Jobspresso",
        feed_url="https://jobspresso.co/remote-work/feed/",
        apply_base="https://jobspresso.co",
        enabled_by_default=True,
        notes="Public remote/freelance RSS",
    ),
)


FREELANCER_COM_META: dict[str, object] = {
    "id": "freelancer",
    "name": "Freelancer.com",
    "method": "api",
    "safety": "api",
    "enabled_by_default": True,
    "region": "global",
    "notes": "Public projects API (no key)",
}


def freelance_registry_rows() -> list[dict[str, object]]:
    rows = [dict(FREELANCER_COM_META)]
    rows.extend(spec.registry_row() for spec in FREELANCE_RSS_SPECS)
    rows.extend(spec.registry_row() for spec in FREELANCE_PLAYWRIGHT_SPECS)
    return rows


def freelance_referers() -> dict[str, str]:
    refs = {str(FREELANCER_COM_META["id"]): "https://www.freelancer.com/"}
    for spec in FREELANCE_RSS_SPECS:
        refs[spec.id] = spec.apply_base.rstrip("/") + "/"
    for spec in FREELANCE_PLAYWRIGHT_SPECS:
        refs[spec.id] = spec.apply_base.rstrip("/") + "/"
    return refs


class FreelancerComSource:
    """Freelancer.com public active-projects API (no OAuth required for listings)."""

    name = "freelancer"
    API_URL = "https://www.freelancer.com/api/projects/0.1/projects/active/"

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        queries = search_queries(profile)[:3]
        quotas = split_limit_across_queries(limit, len(queries))
        jobs: list[JobListing] = []
        seen: set[str] = set()
        for query, quota in zip(queries, quotas):
            if quota <= 0 or len(jobs) >= limit:
                break
            try:
                raw = get_scrape_client().get_json(
                    self.API_URL,
                    source_id=self.name,
                    params={
                        "query": query,
                        "limit": min(max(quota, 10), 50),
                        "full_description": "true",
                        "job_details": "true",
                    },
                )
            except (CaptchaBlockedError, RateLimitedError) as exc:
                logger.error(f"Freelancer.com aborted: {exc}")
                break
            except Exception as exc:  # noqa: BLE001
                get_source_health_registry().record(self.name, "error", str(exc))
                logger.error(f"Freelancer.com failed ({query!r}): {exc}")
                continue

            result = raw.get("result") if isinstance(raw, dict) else None
            projects = []
            if isinstance(result, dict):
                projects = result.get("projects") or []
            elif isinstance(raw, dict):
                projects = raw.get("projects") or []
            if not isinstance(projects, list):
                projects = []

            for item in projects:
                if len(jobs) >= limit or not isinstance(item, dict):
                    break
                title = item.get("title") or ""
                if not title:
                    continue
                seo = item.get("seo_url") or str(item.get("id") or "")
                apply_url = f"https://www.freelancer.com/projects/{seo}" if seo else ""
                desc = strip_html(
                    item.get("description")
                    or item.get("preview_description")
                    or title
                )
                budget = item.get("budget") or {}
                currency = item.get("currency") or {}
                sign = currency.get("sign") or currency.get("code") or ""
                salary = ""
                if isinstance(budget, dict) and (budget.get("minimum") or budget.get("maximum")):
                    lo = budget.get("minimum") or ""
                    hi = budget.get("maximum") or ""
                    kind = item.get("type") or ""
                    salary = f"{sign}{lo}-{hi} {kind}".strip()
                skills: list[str] = []
                jobs_field = item.get("jobs") or []
                if isinstance(jobs_field, list):
                    for tag in jobs_field:
                        if isinstance(tag, dict):
                            label = str(tag.get("name") or "").strip()
                        else:
                            label = str(tag).strip()
                        if label:
                            skills.append(label)
                loc_obj = item.get("location") or {}
                country = ""
                if isinstance(loc_obj, dict):
                    country_obj = loc_obj.get("country") or {}
                    if isinstance(country_obj, dict):
                        country = country_obj.get("name") or ""
                job = build_job(
                    source=self.name,
                    company="Freelancer.com client",
                    title=title,
                    description=desc,
                    skills=[s for s in skills if s],
                    location=country or "Remote",
                    salary=salary,
                    apply_url=apply_url,
                    apply_base="https://www.freelancer.com",
                    posted_at=parse_posted_at(
                        item.get("time_submitted") or item.get("submitdate")
                    ),
                )
                if job.content_hash in seen:
                    continue
                seen.add(job.content_hash)
                jobs.append(job)
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class RssFreelanceSource:
    def __init__(self, spec: RssBoardSpec):
        self.name = spec.id
        self.spec = spec

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        try:
            resp = get_scrape_client().get(
                self.spec.feed_url,
                source_id=self.name,
                accept="application/rss+xml,application/xml,text/xml,*/*",
            )
            items = _parse_rss_items(resp.text)
        except (CaptchaBlockedError, RateLimitedError) as exc:
            logger.error(f"{self.spec.display_name} aborted: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            get_source_health_registry().record(self.name, "error", str(exc))
            logger.error(f"{self.spec.display_name} failed: {exc}")
            return []

        from services.skills import listing_matches_profile_keywords

        jobs: list[JobListing] = []
        for item in items:
            title = item.get("title") or ""
            desc = strip_html(item.get("description") or "")
            if not listing_matches_profile_keywords(profile, title, desc):
                continue
            jobs.append(
                build_job(
                    source=self.name,
                    company=self.spec.display_name,
                    title=title,
                    description=desc or title,
                    location="Remote",
                    apply_url=item.get("link") or "",
                    apply_base=self.spec.apply_base,
                    posted_at=parse_posted_at(item.get("pubDate")),
                )
            )
            if len(jobs) >= limit:
                break
        return _finalize(jobs, profile, allow_stretch, flex_years, self.name)


class PlaywrightFreelanceSource:
    def __init__(self, spec: PlaywrightBoardSpec):
        self.name = spec.id
        self.spec = spec

    def fetch(self, profile, limit, *, allow_stretch=False, flex_years=None) -> list[JobListing]:
        from agents.job_sources.scrape_sources import (
            _dedupe_jobs,
            _finalize_scrape,
            _playwright_fetch_cards,
            _playwright_queries,
        )

        loc = search_location(profile)
        queries = _playwright_queries(profile)
        quotas = split_limit_across_queries(max(limit, 20), len(queries))
        jobs: list[JobListing] = []
        selectors = list(self.spec.selectors) + _GENERIC_CARD_SELECTORS
        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue
            url = _format_search_url(self.spec.url_pattern, query, loc)
            cards = _playwright_fetch_cards(
                url,
                selectors,
                max(quota, 12),
                source_id=self.name,
            )
            for card in cards:
                jobs.append(
                    build_job(
                        source=self.name,
                        company=card.get("company") or self.spec.display_name,
                        title=card.get("title") or "",
                        description=card.get("description") or "",
                        location=card.get("location") or loc or "Remote",
                        apply_url=card.get("apply_url") or "",
                        apply_base=self.spec.apply_base,
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


def build_freelance_sources() -> list:
    sources: list = [FreelancerComSource()]
    sources.extend(RssFreelanceSource(spec) for spec in FREELANCE_RSS_SPECS)
    sources.extend(PlaywrightFreelanceSource(spec) for spec in FREELANCE_PLAYWRIGHT_SPECS)
    return sources
