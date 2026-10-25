"""Logging configuration of the attestation service.

Same files as the other engines, plus a filter that masks anything looking like a
password, in case a library ever logs a request body or an exception with one.
"""

import logging
import re
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Optional, Union


SECRET_PATTERN = re.compile(
    r"(?i)(\"?(?:ritm_)?password\"?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s&,;}]+)"
)


def redact(text: str) -> str:
    return SECRET_PATTERN.sub(r"\1***", text)


class RedactSecretsFilter(logging.Filter):
    """Replace password values in the formatted message before it reaches any handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        return True


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
    for handler in application.handlers:
        handler.close()
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

    secrets_filter = RedactSecretsFilter()
    for handler in (console, events, errors):
        handler.addFilter(secrets_filter)
        application.addHandler(handler)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        library = logging.getLogger(name)
        if not any(isinstance(item, RedactSecretsFilter) for item in library.filters):
            library.addFilter(secrets_filter)
    application.info("Logging initialized in %s", target.resolve())
    return target
