"""Event system for agy-connect."""

import asyncio
from typing import Callable, Coroutine, Any, Dict, List
from .logger import get_logger

logger = get_logger()

# Common event names
EVENT_PROCESS_STARTED = "process_started"
EVENT_PROCESS_CRASHED = "process_crashed"
EVENT_PROCESS_STOPPED = "process_stopped"
EVENT_OUTPUT_RECEIVED = "output_received"
EVENT_ERROR_RECEIVED = "error_received"
EVENT_PROMPT_COMPLETED = "prompt_completed"

class EventDispatcher:
    """Internal event bus for session components."""
    
    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[..., Coroutine[Any, Any, None]]]] = {}
        
    def on(self, event_name: str, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        """Subscribe to an event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        
    def off(self, event_name: str, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        """Unsubscribe from an event."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
            except ValueError:
                pass
                
    async def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event asynchronously."""
        if event_name not in self._listeners:
            return
            
        for cb in self._listeners[event_name]:
            try:
                await cb(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in event listener for {event_name}: {e}")
