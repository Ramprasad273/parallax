"""Modular structured logging system for Parallax."""

import logging
from typing import ClassVar


class ParallaxLogFormatter(logging.Formatter):
    """Clean, human-readable console formatter with color-ready markers."""

    FORMATS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "[DEBUG] %(message)s",
        logging.INFO: "%(message)s",
        logging.WARNING: "[WARNING] %(message)s",
        logging.ERROR: "[ERROR] %(message)s",
        logging.CRITICAL: "[CRITICAL] %(message)s",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno, "%(message)s")
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging(verbose: bool = False, logger_name: str = "parallax") -> logging.Logger:
    """Configure and return a standard logger for Parallax."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ParallaxLogFormatter())
        logger.addHandler(handler)

    logger.propagate = True
    return logger


logger = logging.getLogger("parallax")
