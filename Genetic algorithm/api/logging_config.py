"""Logging configuration for the DSM GA API."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "api.log"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure application-wide logging with console + rotating file output."""
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger("dsm_ga")
    logger.setLevel(level)

    # Prevent duplicate handlers on re-init
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Rotating file handler — 5 MB per file, keep 3 backups
    file_handler = RotatingFileHandler(
        str(LOG_FILE), maxBytes=5_000_000, backupCount=3, encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # Also capture uvicorn access/error logs into our file
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.addHandler(file_handler)

    return logger
