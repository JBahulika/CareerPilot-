"""Source health registry for job boards (Phase 2).

Statuses: ok | rate_limited | captcha_blocked | disabled | error

In-memory only (process lifetime). Never solves captchas — captcha_blocked means
that source aborted and should be treated as unavailable until cleared/cooldown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

_VALID = frozenset({"ok", "rate_limited", "captcha_blocked", "disabled", "error"})


@dataclass
class SourceHealth:
    source_id: str
    status: str = "ok"
    detail: str = ""
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class SourceHealthRegistry:
    def __init__(self, *, cooldown_seconds: int = 1800) -> None:
        self._lock = Lock()
        self._rows: dict[str, SourceHealth] = {}
        self._cooldown = timedelta(seconds=cooldown_seconds)

    def record(
        self,
        source_id: str,
        status: str,
        detail: str = "",
    ) -> SourceHealth:
        if status not in _VALID:
            status = "error"
        row = SourceHealth(
            source_id=source_id,
            status=status,
            detail=(detail or "")[:240],
            updated_at=datetime.utcnow().isoformat() + "Z",
        )
        with self._lock:
            self._rows[source_id] = row
        return row

    def mark_ok(self, source_id: str, detail: str = "") -> SourceHealth:
        return self.record(source_id, "ok", detail)

    def get(self, source_id: str) -> SourceHealth:
        with self._lock:
            row = self._rows.get(source_id)
            if row is None:
                return SourceHealth(source_id=source_id, status="ok", detail="not yet used")
            return row

    def list_all(self, source_ids: list[str] | None = None) -> list[dict]:
        ids = source_ids or sorted(self._rows.keys())
        return [self.get(sid).to_dict() for sid in ids]

    def is_temporarily_blocked(self, source_id: str) -> bool:
        """True if captcha/rate-limit should skip this source for now."""
        row = self.get(source_id)
        if row.status not in {"captcha_blocked", "rate_limited", "disabled"}:
            return False
        if not row.updated_at:
            return True
        try:
            stamp = datetime.fromisoformat(row.updated_at.replace("Z", ""))
        except ValueError:
            return True
        return datetime.utcnow() - stamp < self._cooldown


_REGISTRY: SourceHealthRegistry | None = None


def get_source_health_registry() -> SourceHealthRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        from core.config import settings

        _REGISTRY = SourceHealthRegistry(
            cooldown_seconds=settings.scrape_health_cooldown_seconds
        )
    return _REGISTRY
