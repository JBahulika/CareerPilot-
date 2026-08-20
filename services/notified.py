"""Dedupe jobs already sent in digests (Phase 8).

Skip re-notifying the same listing across runs unless:
- match score jumps by ``NOTIFY_RESEND_SCORE_DELTA`` or more, or
- the listing clearly refreshed (newer ``posted_at`` or different fingerprint).

Identity: ``content_hash`` first, else normalized ``apply_url``.
Human-in-the-loop only — never auto-apply.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import urlparse, urlunparse

from core.config import settings
from core.logging import get_logger
from database.models import NotifiedJobRow
from database.session import get_session
from sqlmodel import select

logger = get_logger(__name__)


@dataclass
class PriorNotify:
    match_score: int = 0
    posted_at: datetime | None = None
    listing_fingerprint: str = ""


def normalize_apply_url(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    # Ignore synthetic search fallbacks
    if "google.com/search" in raw.lower():
        return ""
    try:
        parsed = urlparse(raw)
        # Drop fragment + common tracking query noise lightly
        path = parsed.path.rstrip("/") or ""
        netloc = (parsed.netloc or "").lower()
        if not netloc:
            return raw.lower()
        return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", "", ""))
    except Exception:  # noqa: BLE001
        return raw.lower()


def listing_fingerprint(match: Mapping[str, Any]) -> str:
    """Stable short fingerprint of listing text for refresh detection."""
    parts = [
        str(match.get("title") or ""),
        str(match.get("company") or ""),
        str(match.get("description") or "")[:800],
        str(match.get("posted_at") or ""),
    ]
    blob = "|".join(parts).lower()
    blob = re.sub(r"\s+", " ", blob).strip()
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _parse_posted_at(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    try:
        # fromisoformat handles "2026-08-20T12:00:00"
        return datetime.fromisoformat(text.replace("Z", ""))
    except ValueError:
        return None


def _find_prior(
    *,
    profile_id: int | None,
    content_hash: str,
    apply_url: str,
) -> PriorNotify | None:
    try:
        with get_session() as session:
            q = select(NotifiedJobRow)
            if profile_id is not None:
                q = q.where(NotifiedJobRow.profile_id == profile_id)
            rows = list(session.exec(q).all())
            row = None
            if content_hash:
                row = next((r for r in rows if r.content_hash == content_hash), None)
            if row is None and apply_url:
                row = next((r for r in rows if r.apply_url and r.apply_url == apply_url), None)
            if row is None:
                return None
            return PriorNotify(
                match_score=int(row.match_score or 0),
                posted_at=row.posted_at,
                listing_fingerprint=row.listing_fingerprint or "",
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"notified_jobs lookup failed (treating as new): {exc}")
        return None


def should_notify_again(
    match: Mapping[str, Any],
    prior: PriorNotify | None,
    *,
    score_delta: int | None = None,
) -> tuple[bool, str]:
    """Return (notify?, reason)."""
    if prior is None:
        return True, "new"

    delta = (
        score_delta
        if score_delta is not None
        else int(getattr(settings, "notify_resend_score_delta", 10))
    )
    delta = max(1, int(delta))
    score = int(match.get("match_score", 0) or 0)
    if score - int(prior.match_score or 0) >= delta:
        return True, "score_jump"

    posted = _parse_posted_at(match.get("posted_at"))
    if posted and prior.posted_at:
        prior_posted = prior.posted_at
        if prior_posted.tzinfo:
            prior_posted = prior_posted.replace(tzinfo=None)
        if posted > prior_posted:
            return True, "listing_refreshed"

    fp = listing_fingerprint(match)
    if fp and prior.listing_fingerprint and fp != prior.listing_fingerprint:
        if match.get("description") or match.get("posted_at"):
            return True, "listing_changed"

    return False, "already_notified"


def filter_already_notified(
    matches: Sequence[Mapping[str, Any]],
    *,
    profile_id: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Drop matches already digested unless refresh/score-jump. Returns (kept, dropped)."""
    if not bool(getattr(settings, "notify_dedupe_enabled", True)):
        return [dict(m) for m in matches], 0

    kept: list[dict[str, Any]] = []
    dropped = 0
    for m in matches:
        content_hash = str(m.get("content_hash") or "").strip()
        apply_url = normalize_apply_url(m.get("apply_url"))
        prior = _find_prior(
            profile_id=profile_id,
            content_hash=content_hash,
            apply_url=apply_url,
        )
        ok, reason = should_notify_again(m, prior)
        if ok:
            row = dict(m)
            row["_notify_reason"] = reason
            kept.append(row)
        else:
            dropped += 1
            logger.debug(
                f"Digest skip already-notified: "
                f"{m.get('title')} @ {m.get('company')} ({reason})"
            )
    return kept, dropped


def record_notified_matches(
    matches: Sequence[Mapping[str, Any]],
    *,
    run_id: int,
    profile_id: int | None = None,
) -> int:
    """Persist digest recipients so future runs can dedupe. Returns rows upserted."""
    if not matches:
        return 0
    count = 0
    with get_session() as session:
        for m in matches:
            content_hash = str(m.get("content_hash") or "").strip()
            apply_url = normalize_apply_url(m.get("apply_url"))
            if not content_hash and not apply_url:
                # Fall back identity so we still dedupe by company+title
                content_hash = hashlib.sha256(
                    f"{m.get('company')}|{m.get('title')}".lower().encode()
                ).hexdigest()[:32]

            prior = None
            q = select(NotifiedJobRow)
            if profile_id is not None:
                q = q.where(NotifiedJobRow.profile_id == profile_id)
            rows = list(session.exec(q).all())
            if content_hash:
                prior = next((r for r in rows if r.content_hash == content_hash), None)
            if prior is None and apply_url:
                prior = next((r for r in rows if r.apply_url == apply_url), None)

            posted = _parse_posted_at(m.get("posted_at"))
            score = int(m.get("match_score", 0) or 0)
            fp = listing_fingerprint(m)
            if prior is None:
                prior = NotifiedJobRow(profile_id=profile_id)
                session.add(prior)
            prior.content_hash = content_hash or prior.content_hash
            prior.apply_url = apply_url or prior.apply_url
            prior.company = str(m.get("company") or "")
            prior.title = str(m.get("title") or "")
            prior.match_score = score
            prior.posted_at = posted or prior.posted_at
            prior.listing_fingerprint = fp or prior.listing_fingerprint
            prior.last_run_id = run_id
            prior.notified_at = datetime.utcnow()
            session.add(prior)
            count += 1
    logger.info(f"Recorded {count} notified job(s) for run {run_id}")
    return count
