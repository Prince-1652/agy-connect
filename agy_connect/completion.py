"""Completion detection for agy responses."""

import re
import json
from typing import Optional, Tuple
from .constants import DEFAULT_PROMPT_MARKER
from .logger import get_logger

logger = get_logger()

class CompletionDetector:
    """
    Detects when a response from agy is complete.
    Supports marker strings, JSON validation, and regex.
    """
    
    def __init__(self, marker: str = DEFAULT_PROMPT_MARKER, use_json: bool = False) -> None:
        self.marker = marker
        self.use_json = use_json
        
    def detect(self, buffer: str) -> Tuple[bool, str]:
        """
        Checks if the buffer contains the completion marker.
        Returns a tuple: (is_complete, cleaned_content)
        """
        if not buffer:
            return False, ""
            
        if self.use_json:
            return self._detect_json(buffer)
            
        return self._detect_marker(buffer)
        
    def _detect_marker(self, buffer: str) -> Tuple[bool, str]:
        """Detect completion by a specific text marker."""
        if self.marker in buffer:
            parts = buffer.split(self.marker)
            # The actual response is everything before the last marker.
            # Usually the marker is at the very end.
            cleaned = parts[0].strip()
            return True, cleaned
        return False, buffer
        
    def _detect_json(self, buffer: str) -> Tuple[bool, str]:
        """
        Detect completion by verifying if buffer is valid JSON.
        Useful if agy is instructed to output strictly structured JSON.
        """
        try:
            # We attempt to parse. If it parses cleanly, it's complete.
            parsed = json.loads(buffer.strip())
            return True, buffer.strip()
        except json.JSONDecodeError:
            # Not complete JSON yet (or completely invalid)
            return False, buffer
