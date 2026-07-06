"""State machine for agy-connect."""

import asyncio
from typing import List, Callable, Coroutine, Any
from .constants import (
    STATE_STOPPED, STATE_STARTING, STATE_READY, STATE_BUSY,
    STATE_STREAMING, STATE_ERROR, STATE_RESTARTING, VALID_STATES
)
from .exceptions import InvalidState
from .logger import get_logger

logger = get_logger()

class StateMachine:
    """Manages the state of a single Antigravity session."""
    
    def __init__(self) -> None:
        self._current: str = STATE_STOPPED
        self._lock = asyncio.Lock()
        self._callbacks: List[Callable[[str, str], Coroutine[Any, Any, None]]] = []
        
    @property
    def current(self) -> str:
        return self._current
        
    def add_listener(self, callback: Callable[[str, str], Coroutine[Any, Any, None]]) -> None:
        """Add an async listener for state changes."""
        self._callbacks.append(callback)
        
    async def transition(self, new_state: str) -> None:
        """Safely transition to a new state."""
        if new_state not in VALID_STATES:
            raise InvalidState(f"Unknown state: {new_state}")
            
        async with self._lock:
            if self._current == new_state:
                return
                
            # Define valid transitions
            valid_transitions = {
                STATE_STOPPED: {STATE_STARTING},
                STATE_STARTING: {STATE_READY, STATE_ERROR},
                STATE_READY: {STATE_BUSY, STATE_ERROR, STATE_STOPPED, STATE_RESTARTING},
                STATE_BUSY: {STATE_STREAMING, STATE_READY, STATE_ERROR, STATE_STOPPED},
                STATE_STREAMING: {STATE_READY, STATE_ERROR, STATE_STOPPED},
                STATE_ERROR: {STATE_RESTARTING, STATE_STOPPED},
                STATE_RESTARTING: {STATE_READY, STATE_ERROR, STATE_STOPPED}
            }
            
            allowed = valid_transitions.get(self._current, set())
            if new_state not in allowed:
                logger.warning(f"Forced or illegal state transition from {self._current} to {new_state}")
                # We log a warning instead of raising to allow forced recovery, 
                # but in strict mode we could raise InvalidState.
            
            old_state = self._current
            self._current = new_state
            logger.debug(f"State transitioned: {old_state} -> {new_state}")
            
            for cb in self._callbacks:
                try:
                    await cb(old_state, new_state)
                except Exception as e:
                    logger.error(f"Error in state transition callback: {e}")
