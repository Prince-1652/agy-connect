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
            chat = Chat(config)
