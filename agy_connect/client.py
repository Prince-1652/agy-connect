"""Synchronous client interface for agy-connect."""

import os
import asyncio
import queue as _queue_mod
import uuid
from typing import Iterator, Optional, Dict, Any, List, Callable, Union
from .config import Config
from .session import Session
from .types import StreamEvent
from .render import CliLiveRenderer
from .process import list_available_models
from .utils import get_background_loop as _get_loop, run_coroutine as _run_coroutine

class Chat:
    """
    Synchronous Chat interface representing one independent conversation.
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.session_id = str(uuid.uuid4())
        self._session = Session(self.session_id, self.config)
        _run_coroutine(self._session.initialize())
        
    def send(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """Send a prompt and wait for the full response, optionally receiving status updates."""
        return _run_coroutine(
            self._session.send(
                prompt,
                on_status=on_status,
                on_event=on_event,
                on_question=on_question,
            )
        )
        
    def stream(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> Iterator[str]:
        """Stream the response chunks synchronously with optional real-time status feedback."""
        loop = _get_loop()

        # Use stdlib queue.Queue for true cross-thread safety (works on all Python 3.9+)
        q: _queue_mod.Queue[Union[Optional[str], Exception]] = _queue_mod.Queue()

        async def _consume_stream() -> None:
            try:
                async for chunk in self._session.stream(
                    prompt,
                    on_status=on_status,
                    on_event=on_event,
                    on_question=on_question,
                ):
                    q.put(chunk)
                q.put(None) # EOF
            except Exception as e:
                q.put(e)

        asyncio.run_coroutine_threadsafe(_consume_stream(), loop)

        while True:
            item = q.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def stream_cli(
        self,
        prompt: str,
        prefix: str = "Agy> ",
        show_thinking: bool = True,
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Stream a prompt with live Antigravity CLI states (thinking, tools, streaming tokens)
        rendered directly to stdout in real time. Returns the complete response text.
        """
        renderer = CliLiveRenderer(prefix=prefix, show_thinking=show_thinking)
        renderer.start()
        try:
            for event in self.stream_events(prompt, on_question=on_question):
                renderer.handle_event(event)
        finally:
            renderer.finish()
        return renderer.get_text()

    def stream_events(
        self,
        prompt: str,
        on_question: Optional[Callable[[dict], Any]] = None,
    ) -> Iterator[StreamEvent]:
        """Stream response events (thoughts, tool calls, text deltas) synchronously."""
        loop = _get_loop()
        q: _queue_mod.Queue[Union[Optional[StreamEvent], Exception]] = _queue_mod.Queue()

        async def _consume_events() -> None:
            try:
                async for event in self._session.stream_events(prompt, on_question=on_question):
                    q.put(event)
                q.put(None)
            except Exception as e:
                q.put(e)

        asyncio.run_coroutine_threadsafe(_consume_events(), loop)

        while True:
            event = q.get()
            if event is None:
                break
            if isinstance(event, Exception):
                raise event
            yield event
            
    def history(self) -> List[Dict[str, str]]:
        """Retrieve the conversation history."""
        return self._session.history.get_all()
        
    def save(self, filepath: Optional[str] = None) -> None:
        """Save history to a file. Defaults to sessions/<session_id>.json if no path provided."""
        if filepath is None:
            filepath = os.path.join(self.config.working_directory, "sessions", f"{self.session_id}.json")
            
        # Ensure parent directories exist
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

    def switch_model(self, model: Optional[str], effort: Optional[str] = None) -> None:
        """
        Dynamically switch the active AI model while seamlessly preserving conversation context.
        Set model=None to inherit the user's currently selected CLI model.
        """
        _run_coroutine(self._session.switch_model(model, effort))

    def models(self) -> List[Dict[str, str]]:
        """List all available models discovered by Antigravity CLI."""
        return list_available_models(self.config.executable_path)
        
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

    def __enter__(self) -> "Chat":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
