"""Session wrapper for agy-connect."""

import asyncio
from typing import AsyncGenerator, Optional, Callable, Any
from .config import Config
from .adapter import AntigravityAdapter
from .history import HistoryManager
from .health import HealthMonitor
from .logger import get_logger, setup_logger
from .types import StreamEvent

logger = get_logger()

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

        # BUG-17: Ensure logging is configured on first session creation.
        setup_logger(config.log_level, config.log_file)
        
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
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """Send a prompt to this session sequentially."""
        async with self._lock:
            self.history.add("user", prompt)
            try:
                response = await self.adapter.send(
                    prompt,
                    on_status=on_status,
                    on_event=on_event,
                    on_question=on_question,
                )
                self.history.add("assistant", response)
                return response
            except Exception:
                if self.history._history and self.history._history[-1].get("content") == prompt:
                    self.history._history.pop()
                raise
            
    async def stream(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a prompt's response sequentially, protected by session lock."""
        async with self._lock:
            self.history.add("user", prompt)
            full_response = ""
            success = False
            try:
                async for chunk in self.adapter.stream(
                    prompt,
                    on_status=on_status,
                    on_event=on_event,
                    on_question=on_question,
                ):
                    full_response += chunk
                    yield chunk
                success = True
            finally:
                if success or full_response:
                    self.history.add("assistant", full_response)
                else:
                    if self.history._history and self.history._history[-1].get("content") == prompt:
                        self.history._history.pop()

    async def stream_events(
        self,
        prompt: str,
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream response events sequentially, protected by session lock."""
        async with self._lock:
            self.history.add("user", prompt)
            full_response = ""
            success = False
            try:
                async for event in self.adapter.stream_events(prompt, on_question=on_question):
                    if event.text_delta:
                        full_response += event.text_delta
                    yield event
                success = True
            finally:
                if success or full_response:
                    self.history.add("assistant", full_response)
                else:
                    if self.history._history and self.history._history[-1].get("content") == prompt:
                        self.history._history.pop()

    def status(self) -> str:
        """Get the current state of the adapter."""
        return self.adapter.state.current

    async def restart(self, conversation_id: Optional[str] = None) -> None:
        """Restart session adapter."""
        async with self._lock:
            await self.adapter.restart(conversation_id=conversation_id)

    def reset(self) -> None:
        """Reset conversation history."""
        self.history.clear()

    def save(self, filepath: str) -> None:
        """Save conversation history to JSON."""
        self.history.save(filepath)

    def load(self, filepath: str) -> None:
        """Load conversation history from JSON."""
        self.history.load(filepath)

    async def list_models(self) -> list:
        """List available models asynchronously."""
        from .process import list_available_models
        return await asyncio.to_thread(list_available_models, self.config.executable_path)
