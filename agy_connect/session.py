"""Session wrapper for agy-connect."""

import asyncio
from typing import AsyncGenerator, Optional, Callable, Any
from .config import Config
from .adapter import AntigravityAdapter
from .history import HistoryManager
from .health import HealthMonitor
from .types import StreamEvent

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

    async def switch_model(self, model: Optional[str], effort: Optional[str] = None) -> None:
        """Switch model on active session while preserving conversation context."""
        async with self._lock:
            self.config.model = model
            self.config.effort = effort
            self.adapter.process.config.model = model
            self.adapter.process.config.effort = effort
            await self.adapter.restart(conversation_id=self.adapter.conversation_id)
        
    async def send(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
    ) -> str:
        """Send a prompt to this session sequentially."""
        async with self._lock:
            self.history.add("user", prompt)
            response = await self.adapter.send(prompt, on_status=on_status, on_event=on_event)
            self.history.add("assistant", response)
            return response
            
    async def stream(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a prompt's response sequentially."""
        async with self._lock:
            self.history.add("user", prompt)
            full_response = ""
            async for chunk in self.adapter.stream(prompt, on_status=on_status, on_event=on_event):
                full_response += chunk
                yield chunk
            self.history.add("assistant", full_response)

    async def stream_events(self, prompt: str) -> AsyncGenerator[StreamEvent, None]:
        """Stream response events sequentially."""
        async with self._lock:
            self.history.add("user", prompt)
            full_response = ""
            async for event in self.adapter.stream_events(prompt):
                if event.text_delta:
                    full_response += event.text_delta
                yield event
            self.history.add("assistant", full_response)
