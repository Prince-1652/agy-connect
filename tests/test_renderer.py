"""Unit tests for CliLiveRenderer."""

import io
from agy_connect.render import CliLiveRenderer
from agy_connect.types import StreamEvent

def test_renderer_lifecycle():
    buf = io.StringIO()
    renderer = CliLiveRenderer(prefix="Agy> ", stream=buf, color=False)

    # 1. Start displays thinking
    renderer.start()
    assert "* Thinking..." in buf.getvalue()

    # 2. Tool active updates ephemeral line
    tool_active = StreamEvent(
        event="step_update",
        step_type="tool",
        state="ACTIVE",
        tool_name="run_command",
        tool_parameters={"CommandLine": "git status"},
    )
    renderer.handle_event(tool_active)
    assert "* Running git status" in buf.getvalue()

    # 3. Tool done finishes tool line
    tool_done = StreamEvent(
        event="step_update",
        step_type="tool",
        state="DONE",
        tool_name="run_command",
        tool_parameters={"CommandLine": "git status"},
        duration_seconds=0.45,
    )
    renderer.handle_event(tool_done)
    val = buf.getvalue()
    assert "+ Ran git status (0.5s)\n" in val

    # 4. Text chunk clears thinking and outputs prefix
    text_chunk1 = StreamEvent(
        event="step_update",
        step_type="agent_response",
        state="ACTIVE",
        text_delta="Hello ",
    )
    renderer.handle_event(text_chunk1)
    val = buf.getvalue()
    assert "Agy> Hello " in val

    # 5. Second text chunk appends directly
    text_chunk2 = StreamEvent(
        event="step_update",
        step_type="agent_response",
        state="ACTIVE",
        text_delta="world!",
    )
    renderer.handle_event(text_chunk2)
    val = buf.getvalue()
    assert "Agy> Hello world!" in val

    # 6. Finish finalizes text and newline
    full_text = renderer.finish()
    assert full_text == "Hello world!"
    assert buf.getvalue().endswith("\n")

def test_renderer_thinking_event():
    buf = io.StringIO()
    renderer = CliLiveRenderer(prefix="Agy> ", stream=buf, color=False, show_thinking=True)
    renderer.start()

    think_done = StreamEvent(
        event="step_update",
        step_type="thought",
        state="DONE",
        duration_seconds=1.2,
    )
    renderer.handle_event(think_done)
    assert "* Thought (1.2s)\n" in buf.getvalue()

