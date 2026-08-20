"""Daily scan windows and quiet hours (Phase 5).

- Quiet hours: skip the daily job if local time falls in [start, end)
  (supports overnight wrap, e.g. 22:00–07:00).
- Random scan window: arm a one-shot job at a random time between
  window start and end each day (instead of a fixed clock time).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings


def _minutes_since_midnight(hour: int, minute: int = 0) -> int:
    return max(0, min(23, int(hour))) * 60 + max(0, min(59, int(minute)))


def in_quiet_hours(when: Optional[datetime] = None) -> bool:
    """True when ``when`` (local) falls inside configured quiet hours."""
    if not bool(getattr(settings, "quiet_hours_enabled", False)):
        return False
    now = when or datetime.now()
    cur = now.hour * 60 + now.minute
    start = _minutes_since_midnight(
        getattr(settings, "quiet_hours_start_hour", 22),
        getattr(settings, "quiet_hours_start_minute", 0),
    )
    end = _minutes_since_midnight(
        getattr(settings, "quiet_hours_end_hour", 7),
        getattr(settings, "quiet_hours_end_minute", 0),
    )
    if start == end:
        return False
    if start < end:
        return start <= cur < end
    # Overnight wrap (e.g. 22:00 → 07:00)
    return cur >= start or cur < end


def scan_window_enabled() -> bool:
    return bool(getattr(settings, "daily_scan_window_enabled", False))


def scan_window_bounds() -> tuple[int, int]:
    """Return (start_minute_of_day, end_minute_of_day) for the random window."""
    start = _minutes_since_midnight(
        getattr(settings, "daily_scan_window_start_hour", 8),
        getattr(settings, "daily_scan_window_start_minute", 0),
    )
    end = _minutes_since_midnight(
        getattr(settings, "daily_scan_window_end_hour", 11),
        getattr(settings, "daily_scan_window_end_minute", 0),
    )
    if end <= start:
        # Degenerate window — fall back to a 60-minute span after start
        end = min(start + 60, 24 * 60 - 1)
    return start, end


def pick_random_scan_datetime(day: Optional[datetime] = None) -> datetime:
    """Pick a random local datetime within today's scan window."""
    base = day or datetime.now()
    start_m, end_m = scan_window_bounds()
    # If we're already past the window today, schedule for tomorrow's window
    today_start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    chosen_offset = random.randint(start_m, max(start_m, end_m - 1))
    candidate = today_start + timedelta(minutes=chosen_offset)
    if candidate <= base:
        tomorrow = today_start + timedelta(days=1)
        candidate = tomorrow + timedelta(minutes=chosen_offset)
    return candidate


def window_status() -> dict:
    start_m, end_m = scan_window_bounds()
    return {
        "window_enabled": scan_window_enabled(),
        "window_start": f"{start_m // 60:02d}:{start_m % 60:02d}",
        "window_end": f"{end_m // 60:02d}:{end_m % 60:02d}",
        "quiet_hours_enabled": bool(getattr(settings, "quiet_hours_enabled", False)),
        "quiet_hours_start": (
            f"{int(getattr(settings, 'quiet_hours_start_hour', 22)):02d}:"
            f"{int(getattr(settings, 'quiet_hours_start_minute', 0)):02d}"
        ),
        "quiet_hours_end": (
            f"{int(getattr(settings, 'quiet_hours_end_hour', 7)):02d}:"
            f"{int(getattr(settings, 'quiet_hours_end_minute', 0)):02d}"
        ),
        "currently_quiet": in_quiet_hours(),
    }
