"""Manual-run digest flag resolution."""

from __future__ import annotations

from models.schemas import UserProfile
from services.notify_config import resolve_send_digest


def test_resolve_send_digest_profile_default():
    profile = UserProfile(notify_on_manual_run=True)
    assert resolve_send_digest(request_send_digest=None, profile=profile) is True
    profile2 = UserProfile(notify_on_manual_run=False)
    assert resolve_send_digest(request_send_digest=None, profile=profile2) is False


def test_resolve_send_digest_request_override():
    profile = UserProfile(notify_on_manual_run=False)
    assert resolve_send_digest(request_send_digest=True, profile=profile) is True
    profile2 = UserProfile(notify_on_manual_run=True)
    assert resolve_send_digest(request_send_digest=False, profile=profile2) is False
