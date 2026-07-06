import pytest
import os
import json
from agy_connect.history import HistoryManager
from agy_connect.exceptions import HistoryError

def test_history_manager(tmp_path):
    manager = HistoryManager("test_session")
    
    manager.add("user", "hello")
    manager.add("assistant", "world")
    
    history = manager.get_all()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "world"
    
    file_path = tmp_path / "history.json"
    manager.save(str(file_path))
    
    assert file_path.exists()
    
    manager2 = HistoryManager("test_session")
    manager2.load(str(file_path))
    
    assert len(manager2.get_all()) == 2
    assert manager2.get_all()[0]["content"] == "hello"
    
    with pytest.raises(HistoryError):
        manager2.load(str(tmp_path / "nonexistent.json"))
