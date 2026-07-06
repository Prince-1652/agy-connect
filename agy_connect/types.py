"""Type definitions for agy-connect."""

from typing import Any, Callable, Coroutine, Dict, Optional, Union

# Callback type for streaming responses
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]

# Configuration dictionary type
ConfigDict = Dict[str, Any]

# History item structure
HistoryItem = Dict[str, str]
