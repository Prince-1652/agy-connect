"""Process pool and pre-warming for agy-connect."""

import asyncio
import json
import os
import threading
import time
import uuid
from typing import Dict, List, Optional, Set

from .config import Config
from .process import ProcessManager
from .exceptions import ProcessCrash
from .logger import get_logger
from .utils import get_background_loop, run_coroutine

logger = get_logger()

def _config_key(config: Config) -> tuple:
    """Derive cache key identifying configuration parameters affecting agy subprocesses."""
    try:
        from .utils import find_executable
        exe = find_executable(config.executable_path)
    except Exception:
        exe = config.executable_path or ""

    norm_exe = os.path.normcase(os.path.abspath(exe)) if exe else ""
    norm_cwd = os.path.normcase(os.path.abspath(config.working_directory)) if config.working_directory else ""
    return (
        norm_exe,
        config.model or "",
        config.effort or "",
        bool(config.dangerously_skip_permissions),
        norm_cwd,
    )

class WorkerPool:
    """
    Maintains a pool of pre-warmed, authenticated Antigravity CLI worker processes.
    Enables instant (0ms) session initialization by eliminating subprocess spawn
    and auth/language server boot latencies.
    """

    def __init__(self, target_size: int = 1, auto_replenish: bool = True) -> None:
        self.target_size = target_size
        self.auto_replenish = auto_replenish
        self._pool: Dict[tuple, List[ProcessManager]] = {}
        self._replenishing: Dict[tuple, int] = {}
        self._background_tasks: Set[asyncio.Task] = set()
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _create_warm_worker(self, config: Config) -> ProcessManager:
        """Spawn a worker and wait until the {"event":"init"} event is read."""
        session_id = f"pool-{uuid.uuid4().hex[:8]}"
        manager = ProcessManager(session_id, config)
        proc = await manager.spawn(conversation_id=None)
        if manager._process is None and proc is not None:
            manager._process = proc

        # Read until init event is detected
        while True:
            line = await manager.readline()
            if not line:
                err = ""
                if manager.stderr:
                    try:
                        err_bytes = await manager.stderr.read()
                        err = err_bytes.decode(errors="replace")
                    except Exception:
                        pass
                await manager.terminate()
                raise ProcessCrash(f"agy process exited before emitting init event. stderr: {err}")

            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                if data.get("event") == "init":
                    manager.conversation_id = data.get("conversation_id", session_id)
                    break
            except json.JSONDecodeError:
                continue

        logger.debug(f"Pre-warmed worker ready (PID={manager.pid}, conversation_id={manager.conversation_id})")
        return manager

    async def _replenish_worker(self, config: Config, key: tuple) -> None:
        """Task to warm up a single worker and insert it into the pool."""
        try:
            worker = await self._create_warm_worker(config)
            async with self.lock:
                if len(self._pool.get(key, [])) < self.target_size:
                    if key not in self._pool:
                        self._pool[key] = []
                    self._pool[key].append(worker)
                    logger.debug(f"Worker {worker.pid} added to pool. Pool size: {len(self._pool[key])}")
                else:
                    logger.debug(f"Pool size limit reached; terminating surplus worker {worker.pid}")
                    await worker.terminate()
        except Exception as e:
            logger.warning(f"Background replenishment worker error: {e}")
        finally:
            async with self.lock:
                self._replenishing[key] = max(0, self._replenishing.get(key, 1) - 1)

    def _schedule_replenishment_locked(self, config: Config) -> None:
        """Schedule background replenishment. MUST be called while self.lock is held."""
        if not self.auto_replenish or self.target_size <= 0:
            return
        key = _config_key(config)
        current = len(self._pool.get(key, []))
        in_flight = self._replenishing.get(key, 0)
        needed = self.target_size - (current + in_flight)
        if needed <= 0:
            return

        for _ in range(needed):
            self._replenishing[key] = self._replenishing.get(key, 0) + 1
            task = asyncio.create_task(self._replenish_worker(config, key))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def acquire_warm(self, config: Optional[Config] = None) -> Optional[ProcessManager]:
        """Return an already-warm ProcessManager if available, or None."""
        cfg = config or Config()
        key = _config_key(cfg)
        async with self.lock:
            if key in self._pool:
                while self._pool[key]:
                    worker = self._pool[key].pop(0)
                    if worker.is_running:
                        logger.debug(f"Acquired pre-warmed worker {worker.pid} from pool")
                        self._schedule_replenishment_locked(cfg)
                        return worker
                    else:
                        logger.debug("Discarding dead worker from pool")
        return None

    async def acquire(self, config: Optional[Config] = None) -> ProcessManager:
        """
        Acquire a worker immediately if available matching config,
        or spawn and initialize a fresh one on demand.
        """
        cfg = config or Config()
        worker = await self.acquire_warm(cfg)
        if worker is not None:
            return worker

        logger.debug("No warm worker in pool; spawning on demand")
        worker = await self._create_warm_worker(cfg)
        async with self.lock:
            self._schedule_replenishment_locked(cfg)
        return worker

    async def release(self, worker: ProcessManager) -> None:
        """Terminate a used worker and replenish pool if below target."""
        try:
            await worker.terminate()
        except Exception as e:
            logger.warning(f"Error terminating released worker: {e}")

        if worker.config:
            async with self.lock:
                self._schedule_replenishment_locked(worker.config)

    async def warmup(self, count: int = 1, config: Optional[Config] = None) -> None:
        """Warm up count workers for config in the background."""
        cfg = config or Config()
        key = _config_key(cfg)
        self.target_size = max(self.target_size, count)
        tasks = []
        async with self.lock:
            current = len(self._pool.get(key, []))
            in_flight = self._replenishing.get(key, 0)
            needed = count - (current + in_flight)
            for _ in range(max(0, needed)):
                self._replenishing[key] = self._replenishing.get(key, 0) + 1
                t = asyncio.create_task(self._replenish_worker(cfg, key))
                self._background_tasks.add(t)
                t.add_done_callback(self._background_tasks.discard)
                tasks.append(t)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def wait_for_warmup(
        self,
        count: int = 1,
        config: Optional[Config] = None,
        timeout: float = 60.0,
    ) -> None:
        """Wait until at least count workers are warm and available in the pool."""
        cfg = config or Config()
        if self.warm_count(cfg) >= count:
            return

        _warmup_task = asyncio.create_task(self.warmup(count=count, config=cfg))
        self._background_tasks.add(_warmup_task)
        _warmup_task.add_done_callback(self._background_tasks.discard)
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            if self.warm_count(cfg) >= count:
                return
            await asyncio.sleep(0.05)
        raise TimeoutError(f"Worker pool did not reach {count} warm worker(s) within {timeout}s.")

    def warm_count(self, config: Optional[Config] = None) -> int:
        """Return number of alive warm workers ready in pool."""
        cfg = config or Config()
        key = _config_key(cfg)
        workers = self._pool.get(key, [])
        return sum(1 for w in workers if w.is_running)

    def is_warm(self, config: Optional[Config] = None) -> bool:
        """Check if at least one warm worker is available in pool."""
        return self.warm_count(config) > 0

    async def shutdown(self) -> None:
        """Terminate all idle workers and cancel background tasks."""
        for t in list(self._background_tasks):
            if not t.done():
                t.cancel()
        self._background_tasks.clear()

        async with self.lock:
            for key, workers in self._pool.items():
                for w in workers:
                    try:
                        await w.terminate()
                    except Exception:
                        pass
            self._pool.clear()
            self._replenishing.clear()


# Alias ProcessPool for flexibility
ProcessPool = WorkerPool

_default_pool: Optional[WorkerPool] = None
_pool_lock = threading.Lock()

def get_pool() -> WorkerPool:
    """Retrieve global default WorkerPool instance."""
    global _default_pool
    with _pool_lock:
        if _default_pool is None:
            _default_pool = WorkerPool()
        return _default_pool

def set_pool(pool: Optional[WorkerPool]) -> None:
    """Set or reset the global WorkerPool instance."""
    global _default_pool
    with _pool_lock:
        _default_pool = pool

def warmup(
    count: int = 1,
    config: Optional[Config] = None,
    wait: bool = False,
    timeout: float = 60.0,
) -> None:
    """
    Trigger pre-warming of agy worker process(es) in the background.
    If wait=True, blocks until count workers are ready.
    """
    cfg = config or Config()
    pool = get_pool()
    pool.target_size = max(pool.target_size, count)

    try:
        loop = asyncio.get_running_loop()
        is_running_loop = True
    except RuntimeError:
        loop = get_background_loop()
        is_running_loop = False

    if is_running_loop:
        if wait:
            raise RuntimeError("Cannot block running event loop with wait=True. Use async_warmup(...) instead.")
        asyncio.create_task(pool.warmup(count=count, config=cfg))
    else:
        if wait:
            run_coroutine(pool.wait_for_warmup(count=count, config=cfg, timeout=timeout))
        else:
            asyncio.run_coroutine_threadsafe(pool.warmup(count=count, config=cfg), loop)

async def async_warmup(
    count: int = 1,
    config: Optional[Config] = None,
    wait: bool = False,
    timeout: float = 60.0,
) -> None:
    """Async variant of warmup for coroutines."""
    cfg = config or Config()
    pool = get_pool()
    pool.target_size = max(pool.target_size, count)
    if wait:
        await pool.wait_for_warmup(count=count, config=cfg, timeout=timeout)
    else:
        asyncio.create_task(pool.warmup(count=count, config=cfg))
