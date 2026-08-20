"""Optional HTTP(S) proxy helpers for polite scrapers (Phase 5).

Load order:
1. ``SCRAPE_PROXY_URL`` (single proxy)
2. ``data/proxies/list.txt`` or ``SCRAPE_PROXY_FILE`` (one URL per line)

Never logs credentials. Rotation is optional round-robin when multiple URLs exist.
"""

from __future__ import annotations

import threading
from pathlib import Path

from core.config import PROJECT_ROOT, settings
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_INDEX = 0


def _default_proxy_file() -> Path:
    custom = (getattr(settings, "scrape_proxy_file", "") or "").strip()
    if custom:
        return Path(custom)
    return PROJECT_ROOT / "data" / "proxies" / "list.txt"


def _redact(url: str) -> str:
    """Hide userinfo in proxy URLs for logs."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" in rest:
        rest = rest.split("@", 1)[-1]
        return f"{scheme}://***@{rest}"
    return url


def load_proxy_urls() -> list[str]:
    """Return configured proxy URLs (may be empty)."""
    urls: list[str] = []
    single = (getattr(settings, "scrape_proxy_url", "") or "").strip()
    if single:
        urls.append(single)

    path = _default_proxy_file()
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls.append(line)
        except OSError as exc:
            logger.warning(f"Could not read proxy file {path}: {exc}")

    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def proxies_enabled() -> bool:
    if not bool(getattr(settings, "scrape_proxy_enabled", False)):
        return False
    return bool(load_proxy_urls())


def next_proxy_url() -> str | None:
    """Pick next proxy URL, or None when proxies are off / empty."""
    if not bool(getattr(settings, "scrape_proxy_enabled", False)):
        return None
    urls = load_proxy_urls()
    if not urls:
        return None
    rotate = bool(getattr(settings, "scrape_proxy_rotate", True))
    global _INDEX
    with _LOCK:
        if not rotate:
            return urls[0]
        url = urls[_INDEX % len(urls)]
        _INDEX += 1
        return url


def proxy_status() -> dict:
    urls = load_proxy_urls()
    return {
        "enabled": bool(getattr(settings, "scrape_proxy_enabled", False)),
        "configured": bool(urls),
        "count": len(urls),
        "rotate": bool(getattr(settings, "scrape_proxy_rotate", True)),
        "file": str(_default_proxy_file()),
        "samples": [_redact(u) for u in urls[:3]],
    }
