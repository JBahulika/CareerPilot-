"""Optional board cookies for advanced users (Phase 6).

Load session cookies from a local secrets directory (default ``data/cookies/``,
gitignored). Supported per-board files (``{source_id}`` matches registry ids):

- ``{source}.txt`` — Netscape cookie file **or** a single ``Cookie`` header line
  (``name=value; name2=value2``)
- ``{source}.json`` — list of Playwright-style cookie dicts
  (``name``, ``value``, optional ``domain`` / ``path`` / ``expires`` / ``httpOnly`` / ``secure``)

Never log cookie values. Prefer APIs; cookie mode is high-risk for your account.
Does **not** bypass captchas or enable auto-apply.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.config import PROJECT_ROOT, settings
from core.logging import get_logger

logger = get_logger(__name__)


def cookies_dir() -> Path:
    custom = (getattr(settings, "scrape_cookies_dir", "") or "").strip()
    if custom:
        return Path(custom)
    return PROJECT_ROOT / "data" / "cookies"


def cookies_feature_enabled() -> bool:
    return bool(getattr(settings, "scrape_cookies_enabled", False))


def _candidate_files(source_id: str) -> list[Path]:
    root = cookies_dir()
    sid = (source_id or "").strip().lower()
    if not sid:
        return []
    return [root / f"{sid}.json", root / f"{sid}.txt", root / f"{sid}.cookies"]


def source_has_cookies(source_id: str) -> bool:
    if not cookies_feature_enabled():
        return False
    return any(p.is_file() and p.stat().st_size > 0 for p in _candidate_files(source_id))


def _parse_simple_header(text: str) -> list[dict[str, Any]]:
    """Parse ``a=b; c=d`` into cookie dicts (domain left empty for header use)."""
    out: list[dict[str, Any]] = []
    for part in text.split(";"):
        part = part.strip()
        if not part or part.startswith("#") or "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        if not name:
            continue
        out.append({"name": name, "value": value.strip(), "path": "/"})
    return out


def _parse_netscape(text: str) -> list[dict[str, Any]]:
    """Parse Netscape / curl cookie file lines."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        http_only = False
        if not line:
            continue
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_") :]
        elif line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, path, secure, expires, name, value = parts[:7]
        cookie: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain.lstrip("."),
            "path": path or "/",
            "secure": secure.upper() == "TRUE",
            "httpOnly": http_only,
        }
        try:
            exp = int(expires)
            if exp > 0:
                cookie["expires"] = exp
        except ValueError:
            pass
        out.append(cookie)
    return out


def _load_raw_cookies(source_id: str) -> list[dict[str, Any]]:
    """Load cookie dicts for a source; empty if disabled or missing."""
    if not cookies_feature_enabled():
        return []

    for path in _candidate_files(source_id):
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning(f"Could not read cookie file for {source_id}: {exc}")
            continue
        if not raw:
            continue

        if path.suffix.lower() == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.warning(f"Invalid cookie JSON for {source_id}: {exc}")
                continue
            if isinstance(data, dict) and "cookies" in data:
                data = data["cookies"]
            if not isinstance(data, list):
                logger.warning(f"Cookie JSON for {source_id} must be a list")
                continue
            cookies = [c for c in data if isinstance(c, dict) and c.get("name")]
            if cookies:
                logger.info(f"Loaded {len(cookies)} cookie(s) for {source_id} (json)")
                return cookies
            continue

        # .txt / .cookies — Netscape if tab-separated with 7+ fields, else header
        data_lines = [
            ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")
        ]
        if any(len(ln.split("\t")) >= 7 for ln in data_lines):
            cookies = _parse_netscape(raw)
        else:
            body = "\n".join(data_lines)
            cookies = _parse_simple_header(body.replace("\n", "; "))
        if cookies:
            logger.info(f"Loaded {len(cookies)} cookie(s) for {source_id} (file)")
            return cookies

    return []


def load_cookie_header(source_id: str) -> str | None:
    """Return a ``Cookie`` header value for HTTP clients, or None."""
    cookies = _load_raw_cookies(source_id)
    if not cookies:
        return None
    parts = []
    for c in cookies:
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        parts.append(f"{name}={c.get('value', '')}")
    return "; ".join(parts) if parts else None


def load_playwright_cookies(source_id: str) -> list[dict[str, Any]]:
    """Return cookies suitable for ``browser_context.add_cookies``."""
    cookies = _load_raw_cookies(source_id)
    out: list[dict[str, Any]] = []
    for c in cookies:
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        item: dict[str, Any] = {
            "name": name,
            "value": str(c.get("value", "")),
            "path": str(c.get("path") or "/"),
        }
        domain = str(c.get("domain") or "").strip()
        if domain:
            item["domain"] = domain.lstrip(".")
        else:
            item["url"] = _default_url_for_source(source_id)
        if "expires" in c and c["expires"] is not None:
            try:
                item["expires"] = float(c["expires"])
            except (TypeError, ValueError):
                pass
        if "httpOnly" in c:
            item["httpOnly"] = bool(c["httpOnly"])
        if "secure" in c:
            item["secure"] = bool(c["secure"])
        if "sameSite" in c and c["sameSite"] in ("Strict", "Lax", "None"):
            item["sameSite"] = c["sameSite"]
        out.append(item)
    return out


def _default_url_for_source(source_id: str) -> str:
    defaults = {
        "linkedin": "https://www.linkedin.com/",
        "indeed": "https://www.indeed.com/",
        "glassdoor": "https://www.glassdoor.com/",
        "naukri": "https://www.naukri.com/",
        "wellfound": "https://wellfound.com/",
        "remotive": "https://remotive.com/",
        "remoteok": "https://remoteok.com/",
    }
    return defaults.get((source_id or "").lower(), "https://example.com/")


def listed_cookie_sources() -> list[str]:
    """Source ids that have a non-empty cookie file (feature may still be off)."""
    root = cookies_dir()
    if not root.is_dir():
        return []
    found: set[str] = set()
    for path in root.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".json", ".cookies"}:
            continue
        if path.stat().st_size <= 0:
            continue
        found.add(path.stem.lower())
    return sorted(found)


def cookie_status() -> dict[str, Any]:
    """Safe status for Setup UI — never includes cookie values."""
    sources = listed_cookie_sources()
    enabled = cookies_feature_enabled()
    active = [s for s in sources if enabled]
    return {
        "enabled": enabled,
        "configured": bool(active) if enabled else bool(sources),
        "dir": str(cookies_dir()),
        "boards_with_files": sources,
        "boards_active": active,
        "count": len(active) if enabled else 0,
        "strict_rate_limits": bool(getattr(settings, "scrape_cookies_strict", True)),
        "never_bypass_captcha": True,
        "auto_apply": False,
    }
