"""Phase 11 — bearer-token auth for the phone remote API.

Set ``REMOTE_API_TOKEN`` in ``.env`` to enable. Empty token = remote API disabled
(503). Never expose the API without a token on the public internet.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Query

from core.config import settings


def remote_api_enabled() -> bool:
    return bool((settings.remote_api_token or "").strip())


def _extract_token(
    authorization: Optional[str],
    x_remote_token: Optional[str],
    token_query: Optional[str],
) -> str:
    if x_remote_token and x_remote_token.strip():
        return x_remote_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if token_query and token_query.strip():
        # Optional for PWA fetch from same-origin forms; prefer headers.
        return token_query.strip()
    return ""


def require_remote_token(
    authorization: Annotated[Optional[str], Header()] = None,
    x_remote_token: Annotated[Optional[str], Header(alias="X-Remote-Token")] = None,
    token: Annotated[Optional[str], Query()] = None,
) -> str:
    """FastAPI dependency — validates phone remote token."""
    expected = (settings.remote_api_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "Remote API disabled. Set REMOTE_API_TOKEN in .env on the host PC/VPS, "
                "then restart uvicorn. See docs/REMOTE_ACCESS.md."
            ),
        )
    provided = _extract_token(authorization, x_remote_token, token)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing remote token. Use Authorization: Bearer <token>.",
        )
    return provided


def generate_remote_token() -> str:
    """Helper for docs / setup — url-safe secret."""
    return secrets.token_urlsafe(32)


RemoteAuth = Annotated[str, Depends(require_remote_token)]
