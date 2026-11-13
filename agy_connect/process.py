"""Process management for agy-connect."""

import asyncio
import os
from typing import Optional, List, Dict
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
        self.conversation_id: Optional[str] = None
        
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
        
    async def spawn(self, conversation_id: Optional[str] = None) -> asyncio.subprocess.Process:
        """Spawns a new persistent agy process in stream-json mode."""
        args = [
            self._executable,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
        ]
        if self.config.dangerously_skip_permissions:
            args.append("--dangerously-skip-permissions")
        if self.config.model:
            args.extend(["--model", self.config.model])
        if self.config.effort:
            args.extend(["--effort", self.config.effort])
        if conversation_id:
            args.extend(["--conversation", conversation_id])

        logger.debug(f"Spawning new persistent agy process: {' '.join(args)}")
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_directory,
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
            if self._process.stdin and not self._process.stdin.is_closing():
                try:
                    self._process.stdin.close()
                except Exception:
                    pass
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

    async def write_line(self, line: str) -> None:
        """Writes text line to the process stdin without closing the pipe."""
        if not self._process or not self._process.stdin:
            raise ProcessCrash("Cannot write to stdin. Pipe not available.")
        try:
            if not line.endswith("\n"):
                line += "\n"
            self._process.stdin.write(line.encode("utf-8"))
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise ProcessCrash(f"Process stdin pipe broken: {e}")

    async def readline(self) -> str:
        """Reads a line from stdout."""
        if not self._process or not self._process.stdout:
            raise ProcessCrash("Cannot read from stdout. Pipe not available.")
        line_bytes = await self._process.stdout.readline()
        if not line_bytes:
            return ""
        return line_bytes.decode("utf-8", errors="replace")
            
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

def list_available_models(executable_path: Optional[str] = None) -> List[Dict[str, str]]:
    """Runs `agy models` and returns a list of available models."""
    executable = find_executable(executable_path)
    import subprocess
    try:
        res = subprocess.run([executable, "models"], capture_output=True, text=True, timeout=10)
        models: List[Dict[str, str]] = []
        for line in res.stdout.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("Fetching"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                models.append({"id": parts[0].strip(), "name": parts[1].strip()})
            elif len(parts) == 1:
                models.append({"id": parts[0].strip(), "name": parts[0].strip()})
        return models
    except Exception as e:
        logger.warning(f"Failed to list models via CLI: {e}")
        return []
