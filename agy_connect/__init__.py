"""
agy-connect

A production-grade Python runtime for Antigravity CLI.
"""

from .client import Chat
from .manager import SessionManager
from .config import Config
from .types import StreamEvent
from .render import CliLiveRenderer
from .process import list_available_models as list_models
from .pool import warmup, async_warmup, get_pool, set_pool, WorkerPool, ProcessPool
from . import exceptions

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "Chat",
    "SessionManager",
    "Config",
    "StreamEvent",
    "CliLiveRenderer",
    "list_models",
    "warmup",
    "async_warmup",
    "get_pool",
    "set_pool",
    "WorkerPool",
    "ProcessPool",
    "exceptions"
]
