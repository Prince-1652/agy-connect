"""Process management for agy-connect."""

import asyncio
import signal
import sys
import os
from typing import Optional, Tuple
from .config import Config
from .utils import find_executable
from .exceptions import ProcessCrash, AgyNotInstalled
from .logger import get_logger

logger = get_logger()

class ProcessManager:
    """Manages the Antigravity CLI subprocess."""
    
    def __init__(self, session_id: str, config: Config) -> None:
        self.session_id = session_id
        self.config = config
        self._process: Optional[asyncio.subprocess.Process] = None
        self._executable = find_executable(config.executable_path)
        
        # Create unique directory for this session so agy maintains context naturally
        self.session_dir = os.path.join(self.config.working_directory, "sessions", self.session_id)
        os.makedirs(self.session_dir, exist_ok=True)
        
    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None
        
    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None
        
    @property
    def stdout(self) -> Optional[asyncio.StreamReader]:
        return self._process.stdout if self._process else None
        
    @property
    def stdin(self) -> Optional[asyncio.StreamWriter]:
        return self._process.stdin if self._process else None
        
    @property
    def stderr(self) -> Optional[asyncio.StreamReader]:
        return self._process.stderr if self._process else None
        
    async def spawn(self) -> asyncio.subprocess.Process:
        """Spawns a new agy process."""
        logger.debug(f"Spawning new agy process: {self._executable}")
        try:
            process = await asyncio.create_subprocess_exec(
                self._executable,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.session_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            self._process = process
            logger.info(f"agy process spawned with PID {process.pid}")
            return process
        except FileNotFoundError:
            raise AgyNotInstalled("Executable not found.")
        except Exception as e:
            raise ProcessCrash(f"Failed to spawn agy process: {e}")
            
    async def terminate(self) -> None:
        """Gracefully terminates the agy process."""
        if not self.is_running or not self._process:
            return
            
        logger.debug(f"Terminating agy process {self.pid}")
        
        try:
            self._process.terminate()
            # Wait for it to close
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Process {self.pid} did not terminate gracefully, killing it.")
                self._process.kill()
                await self._process.wait()
        except ProcessLookupError:
            pass # Already dead
        finally:
            self._process = None
            logger.info("agy process terminated.")
            
    async def write_stdin_and_close(self, process: asyncio.subprocess.Process, text: str) -> None:
        """Writes text to the process stdin and sends EOF."""
        if not process.stdin:
            raise ProcessCrash("Cannot write to stdin. Pipe not available.")
            
        try:
            if not text.endswith("\n"):
                text += "\n"
            process.stdin.write(text.encode('utf-8'))
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise ProcessCrash(f"Process stdin pipe broken: {e}")
