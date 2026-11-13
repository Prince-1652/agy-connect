import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from agy_connect.config import Config
from agy_connect.pool import WorkerPool, _config_key, set_pool
from agy_connect.adapter import AntigravityAdapter
from agy_connect.constants import STATE_READY, STATE_STOPPED

@pytest.fixture(autouse=True)
def reset_global_pool():
    """Ensure a clean pool before and after each test."""
    set_pool(None)
    yield
    set_pool(None)

def test_config_key_generation():
    cfg1 = Config(model="gemini-3.8-flash-low", effort="low")
    cfg2 = Config(model="claude-sonnet-4-6", effort="high")
    cfg3 = Config(model="gemini-3.8-flash-low", effort="low")

    k1 = _config_key(cfg1)
    k2 = _config_key(cfg2)
    k3 = _config_key(cfg3)

    assert k1 == k3
    assert k1 != k2

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_pool_warmup_and_acquire_warm(mock_find_executable, mock_spawn, mock_readline):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"conv-pool-1"}'

    config = Config(executable_path="/usr/bin/agy", model="gemini-3.8-flash-low")
    pool = WorkerPool(target_size=1, auto_replenish=False)

    assert not pool.is_warm(config)
    assert pool.warm_count(config) == 0

    # Warm up 1 worker
    await pool.warmup(count=1, config=config)

    assert pool.is_warm(config)
    assert pool.warm_count(config) == 1
    mock_spawn.assert_called_once()

    # acquire_warm should return the pre-warmed worker instantly without spawning again
    worker = await pool.acquire_warm(config)
    assert worker is not None
    assert worker.conversation_id == "conv-pool-1"
    assert pool.warm_count(config) == 0
    # mock_spawn count should still be 1 (zero new spawns)
    assert mock_spawn.call_count == 1

    await pool.release(worker)
    mock_proc.terminate.assert_called_once()
    await pool.shutdown()

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_pool_acquire_on_demand_when_empty(mock_find_executable, mock_spawn, mock_readline):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"conv-demand"}'

    config = Config(executable_path="/usr/bin/agy")
    pool = WorkerPool(target_size=0, auto_replenish=False)

    # Empty pool -> acquire spawns on demand
    worker = await pool.acquire(config)
    assert worker is not None
    assert worker.conversation_id == "conv-demand"
    assert mock_spawn.call_count == 1

    await pool.release(worker)
    await pool.shutdown()

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_adapter_uses_prewarmed_worker(mock_find_executable, mock_spawn, mock_readline):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"conv-warmed"}'

    config = Config(executable_path="/usr/bin/agy")
    pool = WorkerPool(target_size=1, auto_replenish=False)
    set_pool(pool)

    # Pre-warm pool
    await pool.warmup(count=1, config=config)
    assert pool.warm_count(config) == 1
    assert mock_spawn.call_count == 1

    # Adapter start should take the warm worker and NOT spawn again
    adapter = AntigravityAdapter("session-test", config)
    await adapter.start()

    assert adapter.state.current == STATE_READY
    assert adapter.conversation_id == "conv-warmed"
    assert adapter._from_pool is True
    # mock_spawn should still be 1
    assert mock_spawn.call_count == 1

    await adapter.stop()
    assert adapter.state.current == STATE_STOPPED
    mock_proc.terminate.assert_called_once()
    await pool.shutdown()

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_pool_background_replenishment(mock_find_executable, mock_spawn, mock_readline):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"conv-replenish"}'

    config = Config(executable_path="/usr/bin/agy")
    pool = WorkerPool(target_size=1, auto_replenish=True)

    # Pre-warm 1 worker
    await pool.warmup(count=1, config=config)
    assert pool.warm_count(config) == 1

    # Acquire worker -> drops pool below target -> triggers replenishment
    worker = await pool.acquire(config)
    assert worker is not None

    # Wait briefly for replenishment background task to complete
    await asyncio.sleep(0.1)

    # Pool should be replenished back to 1
    assert pool.warm_count(config) == 1
    assert mock_spawn.call_count == 2

    await pool.release(worker)
    await pool.shutdown()

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_pool_shutdown(mock_find_executable, mock_spawn, mock_readline):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"conv-shutdown"}'

    config = Config(executable_path="/usr/bin/agy")
    pool = WorkerPool(target_size=2, auto_replenish=False)
    await pool.warmup(count=2, config=config)
    assert pool.warm_count(config) == 2

    await pool.shutdown()
    assert pool.warm_count(config) == 0
    assert mock_proc.terminate.call_count == 2
