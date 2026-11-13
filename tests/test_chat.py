import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from agy_connect import Chat, Config
from agy_connect.exceptions import AgyNotInstalled

@patch('agy_connect.process.find_executable')
def test_chat_initialization(mock_find_executable):
    mock_find_executable.return_value = "/usr/bin/agy"
    config = Config(executable_path="/usr/bin/agy")
    
    # Mock initialize since it starts subprocess
    with patch('agy_connect.session.Session.initialize', new_callable=AsyncMock) as mock_init:
        chat = Chat(config)
        assert chat.session_id is not None
        mock_init.assert_called_once()
        chat.close()

def test_missing_executable():
    config = Config(executable_path="/nonexistent/agy")
    with patch('agy_connect.process.find_executable', side_effect=AgyNotInstalled):
        with pytest.raises(AgyNotInstalled):
            Chat(config)

@patch('agy_connect.process.find_executable')
def test_switch_model(mock_find_executable):
    mock_find_executable.return_value = "/usr/bin/agy"
    config = Config(executable_path="/usr/bin/agy", model="gemini-3.8-flash-low")
    with patch('agy_connect.session.Session.initialize', new_callable=AsyncMock):
        chat = Chat(config)
        with patch('agy_connect.adapter.AntigravityAdapter.restart', new_callable=AsyncMock) as mock_restart:
            chat.switch_model("claude-sonnet-4-6", effort="high")
            assert chat.config.model == "claude-sonnet-4-6"
            assert chat.config.effort == "high"
            mock_restart.assert_called_once()
        chat.close()

def test_list_models():
    from agy_connect import list_models
    with patch('agy_connect.process.find_executable', return_value="/usr/bin/agy"):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = "gemini-3.8-flash-low\tGemini 3.8 Flash (Low)\nclaude-sonnet-4-6\tClaude Sonnet 4.6\n"
            models = list_models("/usr/bin/agy")
            assert len(models) == 2
            assert models[0]["id"] == "gemini-3.8-flash-low"
            assert models[1]["name"] == "Claude Sonnet 4.6"

@patch('agy_connect.process.find_executable')
@patch('agy_connect.process.ProcessManager.spawn', new_callable=AsyncMock)
@patch('agy_connect.process.ProcessManager.readline', new_callable=AsyncMock)
def test_chat_with_warm_pool(mock_readline, mock_spawn, mock_find_executable):
    from agy_connect import warmup, get_pool, set_pool
    mock_find_executable.return_value = "/usr/bin/agy"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(return_value=0)
    mock_spawn.return_value = mock_proc
    mock_readline.return_value = '{"event":"init","conversation_id":"c-warm-chat"}'

    config = Config(executable_path="/usr/bin/agy")
    pool = get_pool()
    pool.auto_replenish = False

    # Synchronous warmup call with wait=True
    warmup(count=1, config=config, wait=True)
    assert pool.warm_count(config) == 1
    assert mock_spawn.call_count == 1

    # Creating Chat should acquire the warm worker from pool without spawning again
    chat = Chat(config)
    assert chat._session.adapter.conversation_id == "c-warm-chat"
    assert chat._session.adapter._from_pool is True
    assert mock_spawn.call_count == 1
    assert pool.warm_count(config) == 0

    chat.close()
    mock_proc.terminate.assert_called_once()
    set_pool(None)
