"""Daily job monitoring scheduler (PRD future scope, stub).

Wires APScheduler to run the pipeline every morning for the latest profile.
Not started by the API automatically; call ``start_daily_scan`` from a
long-running process when you want autonomous daily runs.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from agents.orchestrator import run_pipeline
from core.config import settings
from core.logging import get_logger
from database.repositories import create_run, get_latest_profile

logger = get_logger(__name__)


def _daily_job() -> None:
    result = get_latest_profile()
    if result is None:
        logger.warning("Daily scan skipped: no profile found.")
        return
    profile_id, profile = result
    run_id = create_run(profile_id)
    logger.info(f"Daily scan starting pipeline run {run_id}")
    run_pipeline(run_id, profile, top_n=settings.top_n_jobs)


def start_daily_scan(hour: int = 8, minute: int = 0) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(_daily_job, "cron", hour=hour, minute=minute, id="daily_scan")
    scheduler.start()
    logger.info(f"Daily job scan scheduled at {hour:02d}:{minute:02d}")
    return scheduler
