"""History management for agy-connect sessions."""

import json
import os
from typing import List, Dict
from .exceptions import HistoryError

class HistoryManager:
    """Manages conversation history for a session."""
    
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._history: List[Dict[str, str]] = []
        
    def add(self, role: str, content: str) -> None:
        """Add a message to history."""
        self._history.append({"role": role, "content": content})
        
    def get_all(self) -> List[Dict[str, str]]:
        """Retrieve the full history."""
        return list(self._history)
        
    def clear(self) -> None:
        """Clear the history."""
        self._history.clear()
        
    def save(self, filepath: str) -> None:
        """Serialize history to a JSON file."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2)
        except Exception as e:
            raise HistoryError(f"Failed to save history: {e}")
            
    def load(self, filepath: str) -> None:
        """Load history from a JSON file."""
        if not os.path.exists(filepath):
            raise HistoryError(f"File not found: {filepath}")
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("History file must contain a JSON array.")
                self._history = data
        except Exception as e:
            raise HistoryError(f"Failed to load history: {e}")
