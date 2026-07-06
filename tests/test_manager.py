import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from agy_connect import SessionManager, Config

@pytest.mark.asyncio
@patch('agy_connect.process.find_executable')
@patch('agy_connect.session.Session.initialize', new_callable=AsyncMock)
async def test_session_manager(mock_init, mock_find_executable):
    mock_find_executable.return_value = "/usr/bin/agy"
    config = Config(max_sessions=2, executable_path="/usr/bin/agy")
    manager = SessionManager(config)
    
    sess1 = await manager.get("session_1")
    sess2 = await manager.get("session_2")
    
    assert len(manager.list_sessions()) == 2
    
    # Getting a third session should evict the oldest (session_1)
    sess3 = await manager.get("session_3")
    
    assert len(manager.list_sessions()) == 2
    assert "session_3" in manager.list_sessions()
    assert "session_2" in manager.list_sessions()
    assert "session_1" not in manager.list_sessions()
    
    await manager.shutdown()
