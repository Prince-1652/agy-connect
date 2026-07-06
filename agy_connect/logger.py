"""Structured logging for agy-connect."""

import logging
from typing import Optional
from .config import Config

_logger = logging.getLogger("agy_connect")

def setup_logger(config: Config) -> logging.Logger:
    """Setup and configure the logger based on Config."""
    _logger.setLevel(config.log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in _logger.handlers[:]:
        _logger.removeHandler(handler)
        
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Stream handler
    sh = logging.StreamHandler()
    sh.setLevel(config.log_level)
    sh.setFormatter(formatter)
    _logger.addHandler(sh)
    
    # Optional file handler
    if config.log_file:
        fh = logging.FileHandler(config.log_file)
        fh.setLevel(config.log_level)
        fh.setFormatter(formatter)
        _logger.addHandler(fh)
        
    return _logger

def get_logger() -> logging.Logger:
    """Get the library logger."""
    return _logger
