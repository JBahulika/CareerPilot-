"""Daily job monitoring scheduler.

Runs the full pipeline every morning for the latest profile and sends a job
digest via the configured notifier (local file now, WhatsApp when ready).
"""

from __future__ import annotations

from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from agents.orchestrator import run_pipeline
from core.config import settings
from core.logging import get_logger
from database.repositories import create_run, get_latest_profile, get_matches_for_run
from services.notifier import get_notifier

logger = get_logger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _daily_job() -> None:
    result = get_latest_profile()
    if result is None:
        logger.warning("Daily scan skipped: no profile found.")
        return

    profile_id, profile = result
    run_id = create_run(profile_id)
    logger.info(f"Daily scan starting pipeline run {run_id}")

    run_pipeline(
        run_id,
        profile,
        top_n=settings.top_n_jobs,
        source=settings.job_source,
        strict_experience=True,
        allow_stretch=False,
    )

    matches, _ = get_matches_for_run(run_id, offset=0, limit=settings.top_n_jobs)
    sent = get_notifier().send_job_digest(profile, matches, run_id)
    logger.info(f"Daily scan run {run_id} complete; notified={sent}")


def start_daily_scan(hour: int = 8, minute: int = 0) -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _daily_job,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_scan",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"Daily job scan scheduled at {hour:02d}:{minute:02d}")
    return _scheduler


def stop_daily_scan() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Daily job scan scheduler stopped.")


def get_scheduler_status() -> dict:
    if _scheduler is None or not _scheduler.running:
        return {
            "enabled": settings.daily_scan_enabled,
            "running": False,
            "next_run": None,
        }

    job = _scheduler.get_job("daily_scan")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "enabled": settings.daily_scan_enabled,
        "running": True,
        "next_run": next_run,
        "hour": settings.daily_scan_hour,
        "minute": settings.daily_scan_minute,
    }
