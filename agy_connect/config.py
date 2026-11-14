"""Configuration classes for agy-connect."""

from dataclasses import dataclass, field
from typing import Optional, List
import os
import logging
from .constants import DEFAULT_TIMEOUT, DEFAULT_MAX_SESSIONS, DEFAULT_CHUNK_SIZE
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
    
    # Model alias/name (e.g. "gemini-3.8-flash-low", "gemini-3.8-flash-medium").
    # If None, inherits user settings.json.
    model: Optional[str] = "gemini-3.8-flash-low"

    # Fallback models chain for quota/rate limit failover
    fallback_models: List[str] = field(default_factory=list)

    # Reasoning effort ("low", "medium", "high", "xhigh", "max").
    # If None, inherits model default or user settings.json.
    effort: Optional[str] = None

    # Auto-approve tool permissions without blocking
    dangerously_skip_permissions: bool = True

    # Use worker pool for pre-warmed processes
    use_pool: bool = True

    # Automatically trigger pre-warming in background
    auto_warmup: bool = False

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
