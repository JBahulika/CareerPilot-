"""Daily job monitoring scheduler.

Runs the full pipeline on a schedule for the latest profile and sends a
human-in-the-loop job digest (local / WhatsApp / email). No auto-apply.

Phase 5: optional random scan window + quiet hours (skip during quiet range).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from agents.orchestrator import run_pipeline
from core.config import settings
from core.logging import get_logger
from database.repositories import create_run, get_latest_profile, get_matches_for_run
from services.notifier import get_notifier
from services.scan_windows import (
    in_quiet_hours,
    pick_random_scan_datetime,
    scan_window_enabled,
    window_status,
)
from services.threshold import effective_min_match_score

logger = get_logger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _daily_job() -> None:
    if in_quiet_hours():
        logger.info("Daily scan skipped: quiet hours active.")
        return

    result = get_latest_profile()
    if result is None:
        logger.warning("Daily scan skipped: no profile found.")
        return

    profile_id, profile = result
    run_id = create_run(profile_id)
    logger.info(f"Daily scan starting pipeline run {run_id}")

    flex = profile.flex_years if profile.flex_years is not None else settings.experience_flex_years
    threshold = effective_min_match_score(profile)

    run_pipeline(
        run_id,
        profile,
        top_n=settings.top_n_jobs,
        source=settings.job_source,
        strict_experience=profile.strict_experience,
        allow_stretch=profile.allow_stretch,
        flex_years=flex,
        exclude_internships=profile.exclude_internships,
        include_remote=profile.include_remote,
        recent_days=settings.daily_recent_jobs_days,
        min_match_score=threshold,
        send_digest=False,  # digest sent below (avoids double-send)
    )

    # Fetch strong matches only; notifier caps via MAX_DIGEST_JOBS after filters.
    fetch_limit = max(settings.top_n_jobs, settings.max_digest_jobs * 3, 30)
    matches, _ = get_matches_for_run(
        run_id, offset=0, limit=fetch_limit, min_score=threshold
    )
    sent = get_notifier(profile=profile).send_job_digest(
        profile, matches, run_id, profile_id=profile_id
    )
    logger.info(f"Daily scan run {run_id} complete; notified={sent}")


def _arm_randomized_scan() -> None:
    """Schedule today's (or tomorrow's) scan at a random time inside the window."""
    from datetime import timedelta

    if _scheduler is None:
        return
    when = pick_random_scan_datetime()
    attempts = 0
    while in_quiet_hours(when) and attempts < 8:
        when = pick_random_scan_datetime(when + timedelta(hours=1))
        attempts += 1
    if in_quiet_hours(when):
        logger.warning(
            f"Random scan time {when.isoformat()} still in quiet hours; "
            "running guard will skip if quiet at fire time."
        )
    _scheduler.add_job(
        _daily_job,
        "date",
        run_date=when,
        id="daily_scan_once",
        replace_existing=True,
    )
    logger.info(f"Randomized daily scan armed for {when.isoformat()}")


def start_daily_scan(hour: int | None = None, minute: int | None = None) -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scan_hour = hour if hour is not None else settings.daily_scan_hour
    scan_minute = minute if minute is not None else settings.daily_scan_minute

    _scheduler = BackgroundScheduler()

    if scan_window_enabled():
        start_h = int(settings.daily_scan_window_start_hour)
        start_m = int(settings.daily_scan_window_start_minute)
        # Each day at window start, arm a one-shot random time within the window
        _scheduler.add_job(
            _arm_randomized_scan,
            "cron",
            hour=start_h,
            minute=start_m,
            id="daily_scan_arm",
            replace_existing=True,
        )
        # Also arm immediately so we don't wait until tomorrow if window is ahead today
        try:
            _arm_randomized_scan()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not arm initial randomized scan: {exc}")
        logger.info(
            f"Daily job scan using random window "
            f"{start_h:02d}:{start_m:02d}–"
            f"{int(settings.daily_scan_window_end_hour):02d}:"
            f"{int(settings.daily_scan_window_end_minute):02d}"
        )
    else:
        _scheduler.add_job(
            _daily_job,
            "cron",
            hour=scan_hour,
            minute=scan_minute,
            id="daily_scan",
            replace_existing=True,
        )
        logger.info(f"Daily job scan scheduled at {scan_hour:02d}:{scan_minute:02d}")

    _scheduler.start()
    return _scheduler


def stop_daily_scan() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Daily job scan scheduler stopped.")


def get_scheduler_status() -> dict:
    win = window_status()
    base = {
        "enabled": settings.daily_scan_enabled,
        "max_digest_jobs": settings.max_digest_jobs,
        "recent_days": settings.daily_recent_jobs_days,
        "hour": settings.daily_scan_hour,
        "minute": settings.daily_scan_minute,
        **win,
    }
    if _scheduler is None or not _scheduler.running:
        return {**base, "running": False, "next_run": None}

    next_run = None
    for job_id in ("daily_scan_once", "daily_scan", "daily_scan_arm"):
        job = _scheduler.get_job(job_id)
        if job and job.next_run_time:
            iso = job.next_run_time.isoformat()
            if next_run is None or iso < next_run:
                next_run = iso

    return {
        **base,
        "running": True,
        "next_run": next_run,
    }
