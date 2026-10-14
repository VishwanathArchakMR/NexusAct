"""Structured logging setup for NexusAct."""

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures structured stdout/stderr logging."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Convert level string to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        stream=sys.stdout,
        force=True,
    )

    logger = logging.getLogger("nexusact")
    logger.setLevel(numeric_level)
    return logger


logger = setup_logging()
