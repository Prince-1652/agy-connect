"""Session wrapper for agy-connect."""

import asyncio
from typing import AsyncGenerator
from .config import Config
from .adapter import AntigravityAdapter
from .history import HistoryManager
from .health import HealthMonitor

class Session:
    """
    Represents a single conversation session.
    Combines the adapter, history, and synchronizes access.
    """
    
    def __init__(self, session_id: str, config: Config) -> None:
        self.session_id = session_id
        self.config = config
        self.adapter = AntigravityAdapter(session_id, config)
        self.history = HistoryManager(session_id)
        self.health = HealthMonitor()
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize the session and start the adapter."""
        self.health.record_start()
        await self.adapter.start()
        
    async def cleanup(self) -> None:
        """Clean up resources when session ends."""
        await self.adapter.stop()
        self.health.record_stop()
        
    async def send(self, prompt: str) -> str:
        """Send a prompt to this session sequentially."""
        async with self._lock:
            self.history.add("user", prompt)
            
            # agy is stateless in batch mode, we MUST prepend history manually
            full_prompt = "\\n".join([f"{msg['role']}: {msg['content']}" for msg in self.history.get_all()])
            
            response = await self.adapter.send(full_prompt)
            
            self.history.add("assistant", response)
            return response
            
    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream a prompt's response sequentially."""
        async with self._lock:
            self.history.add("user", prompt)
            
            # agy is stateless in batch mode, we MUST prepend history manually
            full_prompt = "\\n".join([f"{msg['role']}: {msg['content']}" for msg in self.history.get_all()])
            
            full_response = ""
            async for chunk in self.adapter.stream(full_prompt):
                full_response += chunk
                yield chunk
                
            self.history.add("assistant", full_response)
