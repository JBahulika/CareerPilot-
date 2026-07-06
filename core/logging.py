"""Loguru-based logging setup.

``setup_logging`` is called once at startup; modules obtain a bound logger via
``get_logger(__name__)``. Scraping activity and LLM responses are logged to
rotating files under ``logs/`` per the PRD logging requirements (FR-8).
"""

from __future__ import annotations

import sys

from loguru import logger

from core.config import settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{extra[name]}</cyan> - <level>{message}</level>"
        ),
    )
    logger.add(
        settings.logs_dir / "app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    )
    _configured = True


def get_logger(name: str):
    setup_logging()
    return logger.bind(name=name)
