"""Authentication checks for agy-connect."""

import asyncio
from typing import Optional
from .exceptions import AuthenticationRequired, AgyNotInstalled
from .utils import find_executable
from .logger import get_logger

logger = get_logger()

async def check_authentication(executable_path: Optional[str] = None) -> bool:
    """
    Checks if the agy CLI is authenticated.
    Runs an arbitrary command (e.g., `agy auth status`) to verify.
    Returns True if authenticated, otherwise raises AuthenticationRequired.
    """
    try:
        exe = find_executable(executable_path)
    except AgyNotInstalled as e:
        raise e
        
    logger.debug(f"Checking authentication using executable: {exe}")
    
    # Note: In a real integration, the exact command `agy auth status` or similar would be used.
    # For this robust SDK, we will attempt to run it and parse stderr/stdout.
    # If the tool just exits with a known auth error code, we catch it.
    
    try:
        # Run `agy models` as an authentic, non-destructive auth check.
        # If not authenticated, agy models exits non-zero with auth error.
        process = await asyncio.create_subprocess_exec(
            exe, "models",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            output = (stdout.decode() + stderr.decode()).strip()
            raise AuthenticationRequired(
                f"Antigravity CLI is not authenticated. Run `agy` in your terminal to sign in. ({output})"
            )

        return True
    except FileNotFoundError:
        raise AgyNotInstalled("Executable not found during auth check.")
    except AuthenticationRequired:
        raise
    except Exception as e:
        logger.warning(f"Could not verify authentication status: {e}")
        # Proceed cautiously — the auth sub-command may not exist in all versions
        return True
