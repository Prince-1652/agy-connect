import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from agy_connect.adapter import AntigravityAdapter
from agy_connect.config import Config
from agy_connect.constants import STATE_READY, STATE_ERROR, STATE_STOPPED

@pytest.mark.asyncio
@patch('agy_connect.process.find_executable')
async def test_adapter_start_stop(mock_find_executable):
    mock_find_executable.return_value = "/usr/bin/agy"
    config = Config(executable_path="/usr/bin/agy")
    adapter = AntigravityAdapter("test_session", config)
    
    await adapter.start()
    assert adapter.state.current == STATE_READY
    
    await adapter.stop()
    assert adapter.state.current == STATE_STOPPED
