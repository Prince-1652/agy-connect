import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agy_connect.session import Session
from agy_connect.config import Config
from agy_connect.exceptions import StreamError

@pytest.mark.asyncio
@patch('agy_connect.process.find_executable', return_value="C:\\agy.exe")
async def test_session_history_rollback_on_failure(mock_find_exe):
    """Verify failed turns rollback user prompt and don't record empty assistant messages."""
    config = Config(executable_path="C:\\agy.exe")
    with patch('agy_connect.session.Session.initialize', new_callable=AsyncMock):
        session = Session("test_sess", config)

        # Mock adapter.send to fail
        session.adapter.send = AsyncMock(side_effect=StreamError("Process died"))

        with pytest.raises(StreamError):
            await session.send("Explain quantum computing")

        # History should be empty — user prompt rolled back
        assert len(session.history.get_all()) == 0

@pytest.mark.asyncio
@patch('agy_connect.process.find_executable', return_value="C:\\agy.exe")
async def test_session_stream_history_rollback_on_failure(mock_find_exe):
    """Verify streaming failures before any token rollback user prompt."""
    config = Config(executable_path="C:\\agy.exe")
    with patch('agy_connect.session.Session.initialize', new_callable=AsyncMock):
        session = Session("test_sess", config)

        async def failing_stream(prompt, **kwargs):
            if False:
                yield "never"
            raise StreamError("Network drop")

        session.adapter.stream = failing_stream

        with pytest.raises(StreamError):
            async for _ in session.stream("Hello"):
                pass

        # History should be empty
        assert len(session.history.get_all()) == 0

@pytest.mark.asyncio
@patch('agy_connect.process.find_executable', return_value="C:\\agy.exe")
async def test_session_convenience_methods(mock_find_exe, tmp_path):
    """Verify session convenience methods status, reset, save, load."""
    config = Config(executable_path="C:\\agy.exe")
    with patch('agy_connect.session.Session.initialize', new_callable=AsyncMock):
        session = Session("test_sess", config)
        assert session.status() == "STOPPED"

        session.history.add("user", "test 1")
        session.history.add("assistant", "resp 1")

        save_path = str(tmp_path / "sess.json")
        session.save(save_path)

        session.reset()
        assert len(session.history.get_all()) == 0

        session.load(save_path)
        assert len(session.history.get_all()) == 2
        assert session.history.get_all()[0]["content"] == "test 1"
