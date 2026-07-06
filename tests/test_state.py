import pytest
import asyncio
from agy_connect.state import StateMachine
from agy_connect.constants import STATE_STOPPED, STATE_STARTING, STATE_READY, STATE_BUSY
from agy_connect.exceptions import InvalidState

@pytest.mark.asyncio
async def test_state_machine():
    sm = StateMachine()
    
    assert sm.current == STATE_STOPPED
    
    await sm.transition(STATE_STARTING)
    assert sm.current == STATE_STARTING
    
    await sm.transition(STATE_READY)
    assert sm.current == STATE_READY
    
    await sm.transition(STATE_BUSY)
    assert sm.current == STATE_BUSY
    
    with pytest.raises(InvalidState):
        await sm.transition("INVALID_STATE")
