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

def test_renderer_interleaved_text_and_tools():
    buf = io.StringIO()
    renderer = CliLiveRenderer(prefix="Agy> ", stream=buf, color=False)
    renderer.start()

    # Step 1: Text without trailing newline
    renderer.handle_event(StreamEvent(
        event="step_update",
        step_type="agent_response",
        state="ACTIVE",
        text_delta="Analyzing repository...",
    ))

    # Step 2: Tool execution triggered immediately after
    renderer.handle_event(StreamEvent(
        event="step_update",
        step_type="tool",
        state="ACTIVE",
        tool_name="run_command",
        tool_parameters={"CommandLine": "dir"},
    ))
    renderer.handle_event(StreamEvent(
        event="step_update",
        step_type="tool",
        state="DONE",
        tool_name="run_command",
        tool_parameters={"CommandLine": "dir"},
        duration_seconds=0.2,
    ))

    # Step 3: Subsequent text response continues
    renderer.handle_event(StreamEvent(
        event="step_update",
        step_type="agent_response",
        state="ACTIVE",
        text_delta="Found 5 files.",
    ))
    full = renderer.finish()

    output = buf.getvalue()
    # Ensure previous text was not erased and newline was inserted before tool output
    assert "Analyzing repository...\n" in output
    assert "+ Ran dir (0.2s)\n" in output
    assert "Found 5 files." in output
    assert full == "Analyzing repository...Found 5 files."

def test_renderer_question_event():
    buf = io.StringIO()
    renderer = CliLiveRenderer(prefix="Agy> ", stream=buf, color=False)
    renderer.start()

    renderer.handle_event(StreamEvent(
        event="question",
        question_data={"question": "Select target branch"},
    ))
    assert "? Question: Select target branch\n" in buf.getvalue()

def test_renderer_thinking_tokens_from_agent_response():
    """Verify that real agy agent_response steps with thinking_tokens are recognized as thinking."""
    event = StreamEvent(
        event="step_update",
        step_type="agent_response",
        state="DONE",
        duration_seconds=3.4,
        usage={"thinking_tokens": 250, "total_tokens": 500},
    )
    assert event.is_thinking is True
    assert event.format_cli(color=False) == "* Thought (3.4s)"

def test_renderer_multiline_tool_command_sanitization():
    """Verify that multiline tool commands are collapsed and truncated to prevent line wrapping."""
    event = StreamEvent(
        event="step_update",
        step_type="tool",
        state="ACTIVE",
        tool_name="run_command",
        tool_parameters={"CommandLine": "echo 'line 1'\n  echo 'line 2'\n  echo 'line 3' and very long command string repeated over multiple segments to exceed eighty chars"},
    )
    line = event.format_cli(color=False)
    assert "\n" not in line
    assert line.endswith("...")
    assert len(line) <= 100


