"""Logging configuration."""

import logging

from pythonjsonlogger.json import JsonFormatter


def setup_logging() -> None:
    """Send structured JSON logs to stderr."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
