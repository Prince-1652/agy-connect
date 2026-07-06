"""Async request queue for agy-connect."""

import asyncio
from typing import Any, Callable, Coroutine, Dict, Tuple
from .exceptions import QueueError
from .logger import get_logger

logger = get_logger()

class RequestQueue:
    """
    Ensures only one prompt is processed at a time per session.
    Additional prompts are queued.
    """
    
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Tuple[Callable[..., Coroutine[Any, Any, Any]], tuple, dict]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        
    def start(self) -> None:
        """Start the background worker if not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            
    async def stop(self) -> None:
        """Stop the background worker."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._worker_task = None
        
    async def _worker(self) -> None:
        """Background loop processing queued requests sequentially."""
        while True:
            try:
                func, args, kwargs = await self._queue.get()
                try:
                    await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error processing queued request: {e}")
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker encountered unexpected error: {e}")
                
    async def enqueue(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> None:
        """
        Add an async function to the queue.
        Will start the worker if it's not running.
        """
        self.start()
        await self._queue.put((func, args, kwargs))
        
    def qsize(self) -> int:
        """Return the current size of the queue."""
        return self._queue.qsize()
