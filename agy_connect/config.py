"""Configuration classes for agy-connect."""

from dataclasses import dataclass, field
from typing import Optional
import os
import logging
from .constants import DEFAULT_TIMEOUT, DEFAULT_MAX_SESSIONS, DEFAULT_CHUNK_SIZE, AGY_EXECUTABLE_NAME
from .exceptions import ConfigurationError

@dataclass
class Config:
    """Configuration for the agy-connect runtime."""
    
    # Path to the agy executable. If None, it will be searched in PATH
    executable_path: Optional[str] = None
    
    # Maximum idle time for a session before it is cleaned up (in seconds)
    idle_timeout: float = DEFAULT_TIMEOUT
    
    # Maximum number of concurrent sessions
    max_sessions: int = DEFAULT_MAX_SESSIONS
    
    # Chunk size for reading streams (in bytes)
    stream_chunk_size: int = DEFAULT_CHUNK_SIZE
    
    # Logging level
    log_level: int = logging.INFO
    
    # Optional file to log to
    log_file: Optional[str] = None
    
    # Debug mode flag
    debug_mode: bool = False
    
    # Auto-recovery after crash
    auto_recover: bool = True
    
    # Working directory for the agy process
    working_directory: str = field(default_factory=os.getcwd)

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.idle_timeout <= 0:
            raise ConfigurationError("idle_timeout must be greater than 0.")
        if self.max_sessions <= 0:
            raise ConfigurationError("max_sessions must be greater than 0.")
        if self.stream_chunk_size <= 0:
            raise ConfigurationError("stream_chunk_size must be greater than 0.")
        if not os.path.isdir(self.working_directory):
            raise ConfigurationError(f"working_directory {self.working_directory} does not exist.")
        
        if self.debug_mode:
            self.log_level = logging.DEBUG
