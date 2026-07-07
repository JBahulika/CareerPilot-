"""WhatsApp notification agent (stub + formatter).

Formats job digests per the PRD. Real WhatsApp Cloud API delivery activates when
``WHATSAPP_TOKEN`` and ``WHATSAPP_PHONE_ID`` are configured.
"""

from __future__ import annotations

from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def format_digest(matches: list[dict], profile_name: str = "") -> str:
    """Build a morning digest with fresh jobs and tailored resume paths."""
    from datetime import datetime

    stamp = datetime.now().strftime("%a %d %b, %I:%M %p")
    count = len(matches)
    header = f"CareerPilot — {count} new match{'es' if count != 1 else ''} ({stamp})"
    if profile_name:
        header = f"{header}\nFor {profile_name}"

    if count == 0:
        return f"{header}\n\nNo new matching jobs this morning. Check back after the next scan."

    lines = [header, ""]
    for idx, match in enumerate(matches, start=1):
        company = match.get("company", "Unknown")
        title = match.get("title", "Role")
        score = match.get("match_score", 0)
        lines.append(f"{idx}. {title} @ {company} — {score}% match")
        if match.get("posted_at"):
            lines.append(f"   Posted: {match['posted_at'][:10]}")
        if match.get("apply_url"):
            lines.append(f"   Apply: {match['apply_url']}")
        pdf = match.get("generated_pdf_path")
        if pdf:
            lines.append(f"   Resume: {pdf}")
        skills = match.get("matched_skills") or []
        if skills:
            lines.append(f"   Skills: {', '.join(skills[:5])}")
        lines.append("")
    lines.append("— Sent by CareerPilot AI")
    return "\n".join(lines).strip()


def send_message(phone: str, text: str) -> bool:
    """Send a WhatsApp message via Cloud API when configured."""
    if not settings.whatsapp_enabled:
        logger.info("WhatsApp disabled; message not sent.")
        return False

    token = settings.whatsapp_token
    phone_id = settings.whatsapp_phone_id
    if not token or not phone_id:
        logger.warning("WhatsApp not configured (missing token or phone_id).")
        return False

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone.lstrip("+"),
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
        logger.info(f"WhatsApp message sent to {phone}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"WhatsApp send failed: {exc}")
        return False
