"""Utility functions for agy-connect."""

import shutil
from typing import Optional
from .constants import AGY_EXECUTABLE_NAME
from .exceptions import AgyNotInstalled

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
            f"'{AGY_EXECUTABLE_NAME}' could not be found in your system PATH.\\n\\n"
            "To fix this:\\n"
            "1. Download the CLI from the official Google Antigravity website: https://antigravity.google/product/antigravity-cli\\n"
            "2. Open your terminal and run `agy` for the first time.\\n"
            "3. Complete the initial sign-in process.\\n\\n"
            "Once installed and signed in, restart your Python application."
        )
    return path
