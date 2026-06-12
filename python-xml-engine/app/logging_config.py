"""Logging configuration shared by the XML service modules."""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Optional, Union


class BelowErrorFilter(logging.Filter):
    """Allow event records while keeping errors in their own file."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR


def configure_logging(
    service: str,
    directory: Optional[Union[str, Path]] = None,
) -> Path:
    """Configure console, event, and error handlers for a service."""
    default = Path(__file__).resolve().parents[2] / "logs"
    target = Path(directory or os.getenv("LOG_DIR", str(default)))
    target.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(process)d] %(name)s - %(message)s"
    )
    application = logging.getLogger("app")
    application.handlers.clear()
    application.setLevel(level)
    application.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    events = RotatingFileHandler(
        target / f"{service}-events.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=14,
        encoding="utf-8",
    )
    events.setLevel(level)
    events.addFilter(BelowErrorFilter())
    events.setFormatter(formatter)

    errors = RotatingFileHandler(
        target / f"{service}-errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=30,
        encoding="utf-8",
    )
    errors.setLevel(logging.ERROR)
    errors.setFormatter(formatter)

    application.addHandler(console)
    application.addHandler(events)
    application.addHandler(errors)
    return target
