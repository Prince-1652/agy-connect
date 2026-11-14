"""Type definitions for agy-connect."""

import os
from typing import Any, Callable, Coroutine, Dict, Optional
from dataclasses import dataclass, field

# Callback type for streaming responses
StreamCallback = Callable[[str], Coroutine[Any, Any, None]]

# Configuration dictionary type
ConfigDict = Dict[str, Any]

# History item structure
HistoryItem = Dict[str, str]

@dataclass
class StreamEvent:
    """Rich event delivered during stream-json generation."""
    event: str
    step_type: Optional[str] = None
    state: Optional[str] = None
    text_delta: Optional[str] = None
    thinking_delta: Optional[str] = None
    tool_name: Optional[str] = None
    tool_parameters: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    duration_seconds: Optional[float] = None
    usage: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    interaction_id: Optional[str] = None
    question_data: Optional[Dict[str, Any]] = None

    @property
    def is_tool(self) -> bool:
        """True if this event represents a tool execution."""
        return self.step_type == "tool"

    @property
    def is_thinking(self) -> bool:
        """True if this event represents reasoning / thinking."""
        if self.step_type in ("thought", "thinking") or bool(self.thinking_delta):
            return True
        if self.step_type == "agent_response" and not self.text_delta:
            usage = self.usage or {}
            if usage.get("thinking_tokens", 0) > 0:
                return True
        return False

    @property
    def is_text(self) -> bool:
        """True if this event contains assistant response text."""
        return bool(self.text_delta)

    @property
    def is_question(self) -> bool:
        """True if this event represents an interactive question / prompt."""
        return self.event in ("interaction", "ask_question", "question") or bool(self.question_data)

    def format_cli(self, color: bool = True) -> Optional[str]:
        """
        Formats event matching native Antigravity CLI terminal style.
        """
        dim = "\033[90m" if color else ""
        cyan = "\033[36m" if color else ""
        green = "\033[32m" if color else ""
        yellow = "\033[33m" if color else ""
        reset = "\033[0m" if color else ""

        if self.is_question:
            q_text = ""
            if self.question_data:
                q_text = self.question_data.get("question") or str(self.question_data)
            return f"{yellow}? Question:{reset} {q_text}"

        if self.is_tool:
            tool = self.tool_name or "tool"
            params = self.tool_parameters or {}

            # Resolve target parameter dynamically across known tool schemas
            target = ""
            if "CommandLine" in params:
                target = str(params["CommandLine"])
            elif "command" in params:
                target = str(params["command"])
            elif "cmd" in params:
                target = str(params["cmd"])
            elif "Path" in params:
                target = os.path.basename(str(params["Path"])) or str(params["Path"])
            elif "path" in params:
                target = os.path.basename(str(params["path"])) or str(params["path"])
            elif "file_path" in params:
                target = os.path.basename(str(params["file_path"])) or str(params["file_path"])
            elif "file" in params:
                target = os.path.basename(str(params["file"])) or str(params["file"])
            elif "query" in params:
                target = f'"{params["query"]}"'
            elif "prompt" in params:
                target = f'"{params["prompt"]}"'
            elif "url" in params:
                target = str(params["url"])

            if target:
                target = " ".join(target.split())
                if len(target) > 80:
                    target = target[:77] + "..."

            # Match exact CLI verbs
            if tool in ("run_command", "bash", "exec", "shell"):
                verb_active, verb_done = "Running", "Ran"
            elif tool in ("read_file", "view_file", "cat"):
                verb_active, verb_done = "Reading", "Read"
            elif tool in ("write_file", "edit_file", "replace_file_content", "save_file"):
                verb_active, verb_done = "Editing", "Edited"
            elif tool in ("list_dir", "dir", "ls"):
                verb_active, verb_done = "Listing", "Listed"
            elif tool in ("search_web", "google_search", "grep", "find"):
                verb_active, verb_done = "Searching", "Searched"
            elif tool in ("fetch_web_page", "browse"):
                verb_active, verb_done = "Browsing", "Browsed"
            else:
                verb_active, verb_done = "Calling", "Called"

            desc = f" {target}" if target else f" {tool}"

            if self.state == "ACTIVE":
                return f"{dim}* {verb_active}{reset}{cyan}{desc}{reset}"
            elif self.state == "DONE":
                dur = f" ({self.duration_seconds:.1f}s)" if self.duration_seconds is not None else ""
                return f"{green}+ {verb_done}{reset}{dim}{desc}{dur}{reset}"

        elif self.is_thinking:
            dur = f" ({self.duration_seconds:.1f}s)" if self.duration_seconds is not None else ""
            if self.state == "DONE":
                return f"{dim}* Thought{dur}{reset}"
            return f"{dim}* Thinking...{dur}{reset}"

        return None

    @property
    def status_message(self) -> Optional[str]:
        """Formatted status message matching CLI style."""
        return self.format_cli(color=True)
