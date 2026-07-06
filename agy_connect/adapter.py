"""AntigravityAdapter orchestrating process and communication."""

import asyncio
from typing import AsyncGenerator, Optional, Callable, Coroutine, Any, List
from .config import Config
from .process import ProcessManager
from .state import StateMachine
from .events import EventDispatcher, EVENT_PROCESS_CRASHED, EVENT_PROMPT_COMPLETED
from .stream import SafeStreamer
from .completion import CompletionDetector
from .constants import (
    STATE_STOPPED, STATE_STARTING, STATE_READY, STATE_BUSY,
    STATE_STREAMING, STATE_ERROR, STATE_RESTARTING, DEFAULT_PROMPT_MARKER
)
from .exceptions import ProcessCrash, StreamError, InvalidState
from .logger import get_logger

logger = get_logger()

class AntigravityAdapter:
    """
    The heart of the runtime. Manages state, process, and streaming.
    Hides all subprocess implementation details from the rest of the library.
    """
    
    def __init__(self, session_id: str, config: Config) -> None:
        self.session_id = session_id
        self.config = config
        self.state = StateMachine()
        self.events = EventDispatcher()
        self.process = ProcessManager(session_id, config)
        self.detector = CompletionDetector(marker=DEFAULT_PROMPT_MARKER)
        self._background_tasks: List[asyncio.Task[Any]] = []
        
    async def start(self) -> None:
        """Initialize the adapter."""
        await self.state.transition(STATE_STARTING)
        await self.state.transition(STATE_READY)
            
    async def stop(self) -> None:
        """Stop the adapter."""
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        await self.process.terminate()
        await self.state.transition(STATE_STOPPED)
        
    async def restart(self) -> None:
        """Restart the adapter."""
        await self.state.transition(STATE_RESTARTING)
        await self.stop()
        await self.start()
        
    async def _ensure_ready(self) -> None:
        """Ensures the adapter is ready to process a prompt."""
        if self.state.current != STATE_READY:
            if self.state.current in (STATE_BUSY, STATE_STREAMING):
                raise InvalidState("Adapter is currently busy with another prompt.")
            if self.state.current == STATE_ERROR and self.config.auto_recover:
                await self.restart()
            else:
                raise InvalidState(f"Adapter is in state: {self.state.current}")
                
    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Sends a prompt and yields the response tokens.
        """
        await self._ensure_ready()
        
        await self.state.transition(STATE_BUSY)
        
        try:
            # Spawn a new batch process
            process = await self.process.spawn()
            await self.state.transition(STATE_STREAMING)
            
            # Write prompt and close stdin so agy executes
            await self.process.write_stdin_and_close(process, prompt)
            
            if not process.stdout:
                raise ProcessCrash("No stdout available.")
                
            streamer = SafeStreamer(marker="", chunk_size=self.config.stream_chunk_size)
            
            async for chunk in streamer.stream(process.stdout):
                yield chunk
                
            await process.wait()
            
            await self.events.emit(EVENT_PROMPT_COMPLETED)
            await self.state.transition(STATE_READY)
            
        except Exception as e:
            logger.error(f"Error during stream: {e}")
            await self.state.transition(STATE_ERROR)
            await self.events.emit(EVENT_PROCESS_CRASHED, error=str(e))
            raise
            
    async def send(self, prompt: str) -> str:
        """
        Sends a prompt and returns the full response string.
        """
        response_parts = []
        async for chunk in self.stream(prompt):
            response_parts.append(chunk)
        return "".join(response_parts)
