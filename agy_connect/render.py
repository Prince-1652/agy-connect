"""Terminal renderer matching native Antigravity CLI appearance and speed."""

import sys
import os
import time
from typing import Optional, TextIO
from .types import StreamEvent

def enable_ansi() -> None:
    """Enables ANSI escape sequence support on Windows consoles."""
    if os.name == "nt":
        os.system("")

class CliLiveRenderer:
    """
    Renders live streaming events with native Antigravity CLI visual states:
    - Ephemeral thinking states: `* Thinking...`
    - Live tool execution: `* Running <cmd>` -> `+ Ran <cmd> (<duration>s)`
    - Instant token-by-token streaming with customizable prefix (e.g. `Agy> `)
    """

    def __init__(
        self,
        prefix: str = "Agy> ",
        stream: Optional[TextIO] = None,
        color: bool = True,
        show_thinking: bool = True,
    ) -> None:
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self.color = color
        self.show_thinking = show_thinking

        self._active_status: Optional[str] = None
        self._prefix_printed: bool = False
        self._collected_text: list[str] = []
        self._start_time: float = time.time()
        self._current_line_dirty: bool = False
        self._finished: bool = False

        enable_ansi()

    def start(self) -> None:
        """Call immediately when user prompt is submitted for instant feedback."""
        self._start_time = time.time()
        self._active_status = None
        self._prefix_printed = False
        self._collected_text.clear()
        self._current_line_dirty = False
        self._finished = False
        if self.show_thinking:
            dim = "\033[90m" if self.color else ""
            reset = "\033[0m" if self.color else ""
            self._render_status(f"{dim}* Thinking...{reset}")

    def _ensure_newline(self) -> None:
        """Ensures the terminal is on a fresh line before status/tool output."""
        if self._current_line_dirty:
            self.stream.write("\n")
            self.stream.flush()
            self._current_line_dirty = False

    def _render_status(self, text: str) -> None:
        """Renders an ephemeral status line without trailing newline."""
        self.clear_status()
        self.stream.write(text)
        self.stream.flush()
        self._active_status = text

    def clear_status(self) -> None:
        """Clears the active ephemeral status line from the terminal."""
        if self._active_status:
            self.stream.write("\r\033[2K\r")
            self.stream.flush()
            self._active_status = None

    def handle_event(self, event: StreamEvent) -> None:
        """Processes a StreamEvent and updates the terminal display live."""
        dim = "\033[90m" if self.color else ""
        reset = "\033[0m" if self.color else ""

        if event.is_question:
            self.clear_status()
            self._ensure_newline()
            cli_line = event.format_cli(color=self.color)
            if cli_line:
                self.stream.write(f"{cli_line}\n")
                self.stream.flush()
            self._current_line_dirty = False

        elif event.is_tool:
            cli_line = event.format_cli(color=self.color)
            if not cli_line:
                return

            if event.state == "ACTIVE":
                self.clear_status()
                self._ensure_newline()
                self._render_status(cli_line)
            elif event.state == "DONE":
                self.clear_status()
                self._ensure_newline()
                self.stream.write(f"{cli_line}\n")
                self.stream.flush()
                self._current_line_dirty = False
                # If still working after tool completion, show thinking
                if self.show_thinking:
                    self._render_status(f"{dim}* Thinking...{reset}")

        elif event.is_thinking:
            if not self.show_thinking:
                return
            cli_line = event.format_cli(color=self.color)
            if cli_line:
                if event.state == "DONE":
                    self.clear_status()
                    self._ensure_newline()
                    self.stream.write(f"{cli_line}\n")
                    self.stream.flush()
                    self._current_line_dirty = False
                else:
                    self.clear_status()
                    self._ensure_newline()
                    self._render_status(cli_line)

        elif event.text_delta:
            self.clear_status()
            # First text token: clear thinking line and print prompt prefix once
            if not self._prefix_printed:
                self._ensure_newline()
                if self.prefix:
                    self.stream.write(self.prefix)
                self._prefix_printed = True

            self.stream.write(event.text_delta)
            self.stream.flush()
            self._collected_text.append(event.text_delta)
            self._current_line_dirty = not event.text_delta.endswith("\n")

        elif event.event == "result":
            self.finish()

    def finish(self) -> str:
        """Finalizes rendering, clears status, and ensures newline after streamed text. Idempotent."""
        if self._finished:
            return "".join(self._collected_text)
        self._finished = True
        self.clear_status()
        if self._current_line_dirty:
            self.stream.write("\n")
            self.stream.flush()
            self._current_line_dirty = False
        return "".join(self._collected_text)

    def get_text(self) -> str:
        """Returns the full accumulated response text."""
        return "".join(self._collected_text)

