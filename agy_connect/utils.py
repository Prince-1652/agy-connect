"""Utility functions for agy-connect."""

import shutil
import threading
import asyncio
from typing import Optional, Any, Union
import json
try:
    import orjson
    def fast_json_loads(data: Union[str, bytes]) -> Any:
        return orjson.loads(data)
    def fast_json_dumps(data: Any) -> str:
        return orjson.dumps(data).decode("utf-8")
except ImportError:
    def fast_json_loads(data: Union[str, bytes]) -> Any:
        return json.loads(data)
    def fast_json_dumps(data: Any) -> str:
        return json.dumps(data)
from .constants import AGY_EXECUTABLE_NAME
from .exceptions import AgyNotInstalled

_loop_thread: Optional[threading.Thread] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()

def _start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()

def get_background_loop() -> asyncio.AbstractEventLoop:
    """Get or start the shared background event loop for synchronous callers."""
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(target=_start_background_loop, args=(_loop,), daemon=True)
            _loop_thread.start()
        return _loop

def run_coroutine(coro: Any) -> Any:
    """Run a coroutine thread-safely in the background loop."""
    loop = get_background_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

def find_executable(configured_path: Optional[str] = None) -> str:
    """
    Locates the agy executable.
    Raises AgyNotInstalled if not found.
    """
    if configured_path:
        path = shutil.which(configured_path)
        if not path:
            raise AgyNotInstalled(f"Executable not found at configured path: {configured_path}")
        return path
        
    path = shutil.which(AGY_EXECUTABLE_NAME)
    if not path:
        raise AgyNotInstalled(
            f"'{AGY_EXECUTABLE_NAME}' could not be found in your system PATH.\n\n"
            "To fix this:\n"
            "1. Download the CLI from the official Google Antigravity website: "
            "https://antigravity.google/product/antigravity-cli\n"
            "2. Open your terminal and run `agy` for the first time.\n"
            "3. Complete the initial sign-in process.\n\n"
            "Once installed and signed in, restart your Python application."
        )
    return path
