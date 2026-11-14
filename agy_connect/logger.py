"""Structured logging for agy-connect."""

import logging
from typing import Optional

_logger = logging.getLogger("agy_connect")
_initialized = False


def setup_logger(log_level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Setup and configure the logger. Safe to call multiple times (idempotent after first)."""
    global _initialized
    if _initialized:
        return _logger

    _initialized = True
    _logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in _logger.handlers[:]:
        _logger.removeHandler(handler)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Stream handler
    sh = logging.StreamHandler()
    sh.setLevel(log_level)
    sh.setFormatter(formatter)
    _logger.addHandler(sh)

    # Optional file handler
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        _logger.addHandler(fh)

    return _logger


def get_logger() -> logging.Logger:
    """Get the library logger."""
    return _logger
