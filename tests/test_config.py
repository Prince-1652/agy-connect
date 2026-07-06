import pytest
from agy_connect.config import Config
from agy_connect.exceptions import ConfigurationError
import os

def test_valid_config():
    config = Config(idle_timeout=10, max_sessions=5, stream_chunk_size=1024)
    assert config.idle_timeout == 10
    
def test_invalid_config():
    with pytest.raises(ConfigurationError):
        Config(idle_timeout=-1)
        
    with pytest.raises(ConfigurationError):
        Config(max_sessions=0)
        
    with pytest.raises(ConfigurationError):
        Config(stream_chunk_size=0)
        
    with pytest.raises(ConfigurationError):
        Config(working_directory="/path/that/does/not/exist/ever")
