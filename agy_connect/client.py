"""Synchronous client interface for agy-connect."""

import asyncio
import threading
import uuid
from typing import Iterator, Optional, Dict, Any, List
from .config import Config
from .session import Session
from .manager import SessionManager

# A global thread to run the asyncio loop for synchronous API
_loop_thread: Optional[threading.Thread] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()

def _start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()

def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(target=_start_background_loop, args=(_loop,), daemon=True)
            _loop_thread.start()
        return _loop
        
def _run_coroutine(coro: Any) -> Any:
    """Run a coroutine thread-safely in the background loop."""
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

class Chat:
    """
    Synchronous Chat interface representing one independent conversation.
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.session_id = str(uuid.uuid4())
        self._session = Session(self.session_id, self.config)
        _run_coroutine(self._session.initialize())
        
    def send(self, prompt: str) -> str:
        """Send a prompt and wait for the full response."""
        return _run_coroutine(self._session.send(prompt))
        
    def stream(self, prompt: str) -> Iterator[str]:
        """Stream the response chunks synchronously."""
        loop = _get_loop()
        
        # We use a thread-safe queue to pass chunks from async generator to sync iterator
        q: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
        
        async def _consume_stream() -> None:
            try:
                async for chunk in self._session.stream(prompt):
                    await q.put(chunk)
                await q.put(None) # EOF
            except Exception as e:
                # We could put the exception in the queue, but for simplicity
                await q.put(None)
                
        asyncio.run_coroutine_threadsafe(_consume_stream(), loop)
        
        while True:
            # We must wait for items in the queue thread-safely
            future = asyncio.run_coroutine_threadsafe(q.get(), loop)
            chunk = future.result()
            if chunk is None:
                break
            yield chunk
            
    def history(self) -> List[Dict[str, str]]:
        """Retrieve the conversation history."""
        return self._session.history.get_all()
        
    def save(self, filepath: Optional[str] = None) -> None:
        """Save history to a file. Defaults to sessions/<session_id>.json if no path provided."""
        if filepath is None:
            filepath = os.path.join(self.config.working_directory, "sessions", f"{self.session_id}.json")
            
        # Ensure parent directories exist
        import os
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        self._session.history.save(filepath)
        
    def load(self, filepath: str) -> None:
        """Load history from a file."""
        self._session.history.load(filepath)
        
    def reset(self) -> None:
        """Reset the conversation history."""
        self._session.history.clear()
        
    def restart(self) -> None:
        """Restart the underlying process."""
        _run_coroutine(self._session.adapter.restart())
        
    def interrupt(self) -> None:
        """Interrupt the current generation (restarts the process)."""
        self.restart()
        
    def status(self) -> str:
        """Get the current state of the adapter."""
        return self._session.adapter.state.current
        
    def health(self) -> Dict[str, Any]:
        """Get health metrics."""
        h = self._session.health.get_status(
            process_alive=self._session.adapter.process.is_running,
            pid=self._session.adapter.process.pid,
            queue_length=self._session.queue.qsize() if hasattr(self._session, 'queue') else 0, # Since we removed RequestQueue for Lock, queue length is N/A
            current_state=self._session.adapter.state.current
        )
        return {
            "process_alive": h.process_alive,
            "pid": h.pid,
            "uptime": h.uptime,
            "current_state": h.current_state,
            "last_error": h.last_error
        }
        
    def close(self) -> None:
        """Close the session and terminate the process."""
        _run_coroutine(self._session.cleanup())
