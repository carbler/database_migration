"""Logging configuration with structlog + file handler."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """Configure structlog with console and optional file output."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Standard library logging setup
    handlers: list[logging.Handler] = []

    # Console handler (minimal - Rich handles pretty output)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    handlers.append(console)

    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    # structlog configuration
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if not log_file
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structlog logger."""
    return structlog.get_logger(name)
