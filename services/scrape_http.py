"""Safe scrape HTTP client (Phase 2 + Phase 5/6).

Browser-like headers, jittered delays, concurrency limits, retries with backoff.
Optional proxies (Phase 5) and board cookies with stricter limits (Phase 6).
Detects captcha/challenge pages and aborts that request — never solves captchas.
"""

from __future__ import annotations

import random
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

import httpx

from core.config import settings
from core.logging import get_logger
from services.source_health import get_source_health_registry
from services.proxies import next_proxy_url, proxies_enabled
from services.cookies import load_cookie_header, source_has_cookies

logger = get_logger(__name__)

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_CAPTCHA_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bcaptcha\b",
        r"recaptcha",
        r"hcaptcha",
        r"cf-challenge",
        r"challenge-platform",
        r"attention required",
        r"just a moment",
        r"verify you are (a )?human",
        r"are you a robot",
        r"enable javascript and cookies",
        r"access denied",
        r"/cdn-cgi/challenge",
    )
]

_SITE_REFERERS: dict[str, str] = {
    "remotive": "https://remotive.com/",
    "remoteok": "https://remoteok.com/",
    "arbeitnow": "https://www.arbeitnow.com/",
    "jobicy": "https://jobicy.com/",
    "himalayas": "https://himalayas.app/",
    "themuse": "https://www.themuse.com/",
    "weworkremotely": "https://weworkremotely.com/",
    "workingnomads": "https://www.workingnomads.com/",
    "wellfound": "https://wellfound.com/",
    "indeed": "https://www.indeed.com/",
    "naukri": "https://www.naukri.com/",
    "linkedin": "https://www.linkedin.com/",
    "glassdoor": "https://www.glassdoor.com/",
}


class CaptchaBlockedError(RuntimeError):
    """Raised when a response looks like a captcha/challenge page."""

    def __init__(self, source_id: str, detail: str = "") -> None:
        self.source_id = source_id
        self.status = "captcha_blocked"
        super().__init__(detail or f"{source_id}: captcha_blocked")


class RateLimitedError(RuntimeError):
    def __init__(self, source_id: str, detail: str = "") -> None:
        self.source_id = source_id
        self.status = "rate_limited"
        super().__init__(detail or f"{source_id}: rate_limited")


@dataclass
class ScrapeResponse:
    status_code: int
    text: str
    headers: Mapping[str, str]
    url: str

    def json(self) -> Any:
        import json

        return json.loads(self.text)


def looks_like_captcha(text: str, *, status_code: int | None = None) -> bool:
    """Heuristic captcha/challenge detection. Fail closed — never solve."""
    if not text:
        return False
    sample = text[:8000]
    if any(p.search(sample) for p in _CAPTCHA_PATTERNS):
        # Avoid false positives on normal job text mentioning "captcha" rarely;
        # require challenge-ish context or short interstitial pages.
        if len(sample) < 2500 or status_code in {403, 429, 503}:
            return True
        challenge_hits = sum(1 for p in _CAPTCHA_PATTERNS if p.search(sample))
        return challenge_hits >= 2
    return False


def browser_headers(
    *,
    source_id: str | None = None,
    referer: str | None = None,
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
) -> dict[str, str]:
    ref = referer
    if not ref and source_id:
        ref = _SITE_REFERERS.get(source_id)
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if ref:
        headers["Referer"] = ref
    return headers


class SafeScrapeClient:
    """Shared polite HTTP client for API + scrape job sources."""

    def __init__(self) -> None:
        self._sema = threading.Semaphore(max(1, settings.scrape_max_concurrency))
        cookie_conc = max(1, int(getattr(settings, "scrape_cookie_max_concurrency", 1)))
        self._cookie_sema = threading.Semaphore(cookie_conc)
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def _uses_strict_cookies(self, source_id: str) -> bool:
        if not source_has_cookies(source_id):
            return False
        return bool(getattr(settings, "scrape_cookies_strict", True))

    def _jitter_delay(self, *, source_id: str | None = None) -> None:
        use_cookie = bool(source_id and self._uses_strict_cookies(source_id))
        if use_cookie:
            lo = max(0, int(getattr(settings, "scrape_cookie_min_delay_ms", 1500)))
            hi = max(lo, int(getattr(settings, "scrape_cookie_max_delay_ms", 4000)))
        else:
            lo = max(0, settings.scrape_min_delay_ms)
            hi = max(lo, settings.scrape_max_delay_ms)
        delay_ms = random.randint(lo, hi) if hi > 0 else 0
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            need = delay_ms / 1000.0
            if elapsed < need:
                time.sleep(need - elapsed)
            self._last_request_at = time.monotonic()

    @staticmethod
    def _429_sleep_seconds(attempt: int, retry_after: str | None = None) -> float:
        """Stronger 429 backoff: honor Retry-After when present, else exponential."""
        if retry_after:
            try:
                # Retry-After as seconds (integer) or ignore HTTP-date form
                secs = float(retry_after.strip())
                if secs >= 0:
                    base = getattr(settings, "scrape_429_base_delay_ms", 2000) / 1000.0
                    cap = getattr(settings, "scrape_429_max_delay_ms", 60000) / 1000.0
                    return min(cap, max(secs, base)) + random.random()
            except ValueError:
                pass
        base_ms = max(100, int(getattr(settings, "scrape_429_base_delay_ms", 2000)))
        cap_ms = max(base_ms, int(getattr(settings, "scrape_429_max_delay_ms", 60000)))
        delay = (base_ms / 1000.0) * (2**attempt) + random.uniform(0.0, 1.0)
        return min(cap_ms / 1000.0, delay)

    def _httpx_client(self, timeout: float) -> httpx.Client:
        kwargs: dict = {"timeout": timeout, "follow_redirects": True}
        if proxies_enabled():
            proxy = next_proxy_url()
            if proxy:
                # httpx >=0.28 uses proxy=; older used proxies=
                try:
                    return httpx.Client(proxy=proxy, **kwargs)
                except TypeError:
                    return httpx.Client(
                        proxies={"http://": proxy, "https://": proxy},
                        **kwargs,
                    )
        return httpx.Client(**kwargs)

    def get(
        self,
        url: str,
        *,
        source_id: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float = 30.0,
        accept: str = "application/json,text/plain,*/*",
        referer: str | None = None,
    ) -> ScrapeResponse:
        health = get_source_health_registry()
        merged = browser_headers(source_id=source_id, referer=referer, accept=accept)
        if headers:
            merged.update(headers)
        cookie_header = load_cookie_header(source_id)
        if cookie_header and "Cookie" not in merged and "cookie" not in {
            k.lower() for k in merged
        }:
            merged["Cookie"] = cookie_header

        max_retries = max(0, settings.scrape_max_retries)
        rate_retries = max(max_retries, int(getattr(settings, "scrape_429_max_retries", 5)))
        last_exc: Exception | None = None
        rate_attempts = 0
        strict_cookies = self._uses_strict_cookies(source_id)

        for attempt in range(max(rate_retries, max_retries) + 1):
            self._sema.acquire()
            cookie_held = False
            if strict_cookies:
                self._cookie_sema.acquire()
                cookie_held = True
            try:
                self._jitter_delay(source_id=source_id)
                with self._httpx_client(timeout) as client:
                    resp = client.get(url, params=params, headers=merged)
                body = resp.text or ""
                if looks_like_captcha(body, status_code=resp.status_code):
                    health.record(source_id, "captcha_blocked", f"challenge at {urlparse(url).netloc}")
                    logger.warning(f"{source_id}: captcha_blocked — aborting (never solving)")
                    raise CaptchaBlockedError(source_id, f"challenge page from {url}")

                if resp.status_code == 429:
                    health.record(source_id, "rate_limited", f"HTTP 429 attempt={rate_attempts}")
                    rate_attempts += 1
                    if rate_attempts <= rate_retries:
                        retry_after = resp.headers.get("Retry-After") or resp.headers.get(
                            "retry-after"
                        )
                        sleep_for = self._429_sleep_seconds(rate_attempts - 1, retry_after)
                        logger.warning(
                            f"{source_id}: HTTP 429 — backing off {sleep_for:.1f}s "
                            f"(attempt {rate_attempts}/{rate_retries})"
                        )
                        time.sleep(sleep_for)
                        continue
                    raise RateLimitedError(source_id, "HTTP 429")

                if resp.status_code >= 500:
                    health.record(source_id, "error", f"HTTP {resp.status_code}")
                    if attempt < max_retries:
                        time.sleep(min(8.0, 0.5 * (2**attempt) + random.random()))
                        continue
                    resp.raise_for_status()

                if resp.status_code >= 400:
                    health.record(source_id, "error", f"HTTP {resp.status_code}")
                    resp.raise_for_status()

                health.mark_ok(source_id)
                return ScrapeResponse(
                    status_code=resp.status_code,
                    text=body,
                    headers=dict(resp.headers),
                    url=str(resp.url),
                )
            except (CaptchaBlockedError, RateLimitedError):
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                health.record(source_id, "error", str(exc))
                if attempt < max_retries:
                    time.sleep(min(8.0, 0.5 * (2**attempt) + random.random()))
                    continue
                raise
            finally:
                if cookie_held:
                    self._cookie_sema.release()
                self._sema.release()

        assert last_exc is not None
        raise last_exc

    def get_json(
        self,
        url: str,
        *,
        source_id: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float = 30.0,
        referer: str | None = None,
    ) -> Any:
        resp = self.get(
            url,
            source_id=source_id,
            params=params,
            headers=headers,
            timeout=timeout,
            accept="application/json,text/plain,*/*",
            referer=referer,
        )
        return resp.json()


_CLIENT: SafeScrapeClient | None = None
_CLIENT_LOCK = threading.Lock()


def get_scrape_client() -> SafeScrapeClient:
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = SafeScrapeClient()
        return _CLIENT


def playwright_user_agent() -> str:
    return _DEFAULT_UA


def assert_page_not_captcha(html: str, *, source_id: str, url: str = "") -> None:
    if looks_like_captcha(html):
        get_source_health_registry().record(
            source_id, "captcha_blocked", f"playwright challenge {urlparse(url).netloc}"
        )
        logger.warning(f"{source_id}: captcha_blocked via Playwright — aborting")
        raise CaptchaBlockedError(source_id, f"challenge page from {url or 'browser'}")
