"""WhatsApp notification agent (formatter + Cloud API send).

Formats job digests for human-in-the-loop review. Real WhatsApp Cloud API
delivery activates when ``WHATSAPP_TOKEN`` and ``WHATSAPP_PHONE_ID`` are set.
CareerPilot never auto-applies — digests are links-only.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.logging import get_logger
from services.digest import short_reason

logger = get_logger(__name__)

_FOOTER = (
    "— CareerPilot discovers & notifies only. "
    "You choose applications and apply manually (no auto-apply)."
)


def format_digest(
    matches: list[dict],
    profile_name: str = "",
    *,
    min_match_score: int | None = None,
    max_digest_jobs: int | None = None,
) -> str:
    """Build a digest: title, company, location, score, reason, apply link."""
    from datetime import datetime

    stamp = datetime.now().strftime("%a %d %b, %I:%M %p")
    count = len(matches)
    header = f"CareerPilot — {count} match{'es' if count != 1 else ''} ({stamp})"
    if profile_name:
        header = f"{header}\nFor {profile_name}"
    if min_match_score is not None:
        header = f"{header}\nMin match score: {min_match_score}%"
    if max_digest_jobs is not None:
        header = f"{header}\nDigest cap: {max_digest_jobs}"

    if count == 0:
        return (
            f"{header}\n\nNo matching jobs at or above your threshold "
            f"this scan.\n\n{_FOOTER}"
        )

    lines = [header, ""]
    for idx, match in enumerate(matches, start=1):
        company = match.get("company", "Unknown")
        title = match.get("title", "Role")
        score = match.get("match_score", 0)
        lines.append(f"{idx}. {title} @ {company} — {score}% match")
        if match.get("location"):
            lines.append(f"   Location: {match['location']}")
        reason = short_reason(match)
        if reason:
            lines.append(f"   Why: {reason}")
        apply_url = (match.get("apply_url") or "").strip()
        if apply_url:
            lines.append(f"   Apply: {apply_url}")
        else:
            lines.append("   Apply: (link unavailable — search the role manually)")
        lines.append("")
    lines.append(_FOOTER)
    return "\n".join(lines).strip()


def send_message(phone: str, text: str, *, cfg=None) -> bool:
    """Send a WhatsApp message via Cloud API when configured."""
    from services.notify_config import resolve_notify_config, whatsapp_ready

    config = cfg or resolve_notify_config()
    if not config.whatsapp_enabled:
        logger.info("WhatsApp disabled; message not sent.")
        return False

    token = config.whatsapp_token
    phone_id = config.whatsapp_phone_id
    if not token or not phone_id:
        logger.warning("WhatsApp not configured (missing token or phone_id).")
        return False

    recipient = (phone or config.whatsapp_recipient or "").strip()
    if not recipient:
        logger.warning("WhatsApp not configured (missing recipient).")
        return False

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient.lstrip("+"),
        "type": "text",
        "text": {"body": text[:4096]},
    }
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        logger.info(f"WhatsApp message sent to {recipient}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"WhatsApp send failed: {exc}")
        return False


def whatsapp_configured(profile=None) -> bool:
    from services.notify_config import resolve_notify_config, whatsapp_ready

    return whatsapp_ready(resolve_notify_config(profile))
