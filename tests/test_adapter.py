import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from agy_connect.adapter import AntigravityAdapter
from agy_connect.config import Config
from agy_connect.constants import STATE_READY, STATE_STOPPED

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_adapter_start_stop(mock_find_executable, mock_spawn, mock_readline):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"test-conv"}'
    
    config = Config(executable_path="/usr/bin/agy")
    adapter = AntigravityAdapter("test_session", config)
    
    await adapter.start()
    assert adapter.state.current == STATE_READY
    assert adapter.conversation_id == "test-conv"
    
    await adapter.stop()
    assert adapter.state.current == STATE_STOPPED

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.write_line', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_adapter_stream_and_send(mock_find_executable, mock_spawn, mock_readline, mock_write_line):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    
    # sequence of stdout lines: init, step_update, step_update, result
    mock_readline.side_effect = [
        '{"event":"init","conversation_id":"c1"}',
        '{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"hello "}}',
        '{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"world"}}',
        '{"event":"result","result":{"status":"SUCCESS"}}'
    ]
    config = Config(executable_path="/usr/bin/agy")
    adapter = AntigravityAdapter("test_session", config)
    await adapter.start()

    chunks = []
    async for chunk in adapter.stream("test"):
        chunks.append(chunk)

    assert "".join(chunks) == "hello world"
    assert adapter.state.current == STATE_READY
    await adapter.stop()

@pytest.mark.asyncio
@patch('agy_connect.process.ProcessManager.write_line', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.find_executable')
async def test_adapter_tool_and_status_events(mock_find_executable, mock_spawn, mock_readline, mock_write_line):
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    
    mock_readline.side_effect = [
        '{"event":"init","conversation_id":"c1"}',
        '{"event":"step_update","step_update":{"step_type":"thought","thinking_delta":"checking files"}}',
        '{"event":"step_update","step_update":{"step_type":"tool","state":"ACTIVE","tool_name":"run_command","tool_info":{"name":"run_command","parameters":{"CommandLine":"git status"}}}}',
        '{"event":"step_update","step_update":{"step_type":"tool","state":"DONE","tool_name":"run_command","duration_seconds":0.5}}',
        '{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"Git clean"}}',
        '{"event":"result","result":{"status":"SUCCESS"}}'
    ]
    config = Config(executable_path="/usr/bin/agy")
    adapter = AntigravityAdapter("test_session", config)
    await adapter.start()

    statuses = []
    chunks = []
    async for chunk in adapter.stream("status", on_status=lambda msg: statuses.append(msg)):
        chunks.append(chunk)

    assert "".join(chunks) == "Git clean"
    assert any("Thinking..." in s for s in statuses)
    assert any("Running" in s and "git status" in s for s in statuses)
    assert any("Ran" in s and "0.5s" in s for s in statuses)
    await adapter.stop()
