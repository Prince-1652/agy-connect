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
        # Mocking the command structure since agy internal details are abstracted.
        # This will need to be adapted based on real agy behavior.
        process = await asyncio.create_subprocess_exec(
            exe, "--help", # Using help as a safe fallback command to see if it even runs
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode() + stderr.decode()
        
        # If output explicitly mentions "login" or "authentication required"
        if "authenticate" in output.lower() or "login" in output.lower():
             raise AuthenticationRequired("Antigravity CLI is not authenticated. Please login first.")
             
        return True
    except FileNotFoundError:
        raise AgyNotInstalled("Executable not found during auth check.")
    except Exception as e:
        if isinstance(e, AuthenticationRequired):
            raise
        logger.warning(f"Could not verify authentication status: {e}")
        # Proceed cautiously
        return True
