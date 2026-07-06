"""Constants for agy-connect."""

import os
import sys

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_SESSIONS = 10
DEFAULT_CHUNK_SIZE = 1024

# Executable name based on platform
if sys.platform == "win32":
    AGY_EXECUTABLE_NAME = "agy.exe"
else:
    AGY_EXECUTABLE_NAME = "agy"

# State machine states
STATE_STOPPED = "STOPPED"
STATE_STARTING = "STARTING"
STATE_READY = "READY"
STATE_BUSY = "BUSY"
STATE_STREAMING = "STREAMING"
STATE_ERROR = "ERROR"
STATE_RESTARTING = "RESTARTING"

VALID_STATES = {
    STATE_STOPPED,
    STATE_STARTING,
    STATE_READY,
    STATE_BUSY,
    STATE_STREAMING,
    STATE_ERROR,
    STATE_RESTARTING,
}

# Prompt marker or completion marker
# We use a standard shell-like prompt marker, but this can be customized
DEFAULT_PROMPT_MARKER = "agy> "
