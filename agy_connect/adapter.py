"""AntigravityAdapter orchestrating process and communication."""

import asyncio
import json
from typing import AsyncGenerator, Optional, Callable, Any, List, Dict
from .config import Config
from .process import ProcessManager
from .state import StateMachine
from .events import EventDispatcher, EVENT_PROCESS_CRASHED, EVENT_PROMPT_COMPLETED
from .completion import CompletionDetector
from .constants import (
    STATE_STOPPED, STATE_STARTING, STATE_READY, STATE_BUSY,
    STATE_STREAMING, STATE_ERROR, STATE_RESTARTING, DEFAULT_PROMPT_MARKER
)
from .exceptions import ProcessCrash, StreamError, InvalidState
from .types import StreamEvent
from .logger import get_logger
from .utils import fast_json_loads, fast_json_dumps

logger = get_logger()

QUOTA_PATTERNS = (
    "resource_exhausted",
    "429",
    "quota",
    "rate limit",
    "rate_limit",
    "limit reached",
    "exceeded your current quota",
    "exhausted",
)

def _is_quota_error(err_msg: str) -> bool:
    if not err_msg:
        return False
    lower = err_msg.lower()
    return any(p in lower for p in QUOTA_PATTERNS)

class AntigravityAdapter:
    """
    The heart of the runtime. Manages state, process, and streaming.
    Hides all subprocess implementation details from the rest of the library.
    """
    
    def __init__(self, session_id: str, config: Config) -> None:
        self.session_id = session_id
        self.config = config
        self.state = StateMachine()
        self.events = EventDispatcher()
        self.process = ProcessManager(session_id, config)
        self.detector = CompletionDetector(marker=DEFAULT_PROMPT_MARKER)
        self._background_tasks: List[asyncio.Task[Any]] = []
        self.conversation_id: Optional[str] = None
        self._from_pool: bool = False
        self._fallback_chain: List[str] = list(config.fallback_models)
        
    async def start(self, conversation_id: Optional[str] = None) -> None:
        """Initialize the adapter and warm up persistent agy process."""
        await self.state.transition(STATE_STARTING)
        try:
            await self._ensure_process(conversation_id=conversation_id)
            await self.state.transition(STATE_READY)
        except Exception as e:
            logger.error(f"Failed to start adapter: {e}")
            await self.state.transition(STATE_ERROR)
            raise

    async def _ensure_process(self, conversation_id: Optional[str] = None) -> None:
        """Ensures the persistent stream-json process is running and initialized."""
        if not self.process.is_running:
            if conversation_id is None and getattr(self.config, "use_pool", True):
                from .pool import get_pool
                warm_worker = await get_pool().acquire_warm(self.config)
                if warm_worker is not None:
                    self.process = warm_worker
                    self.conversation_id = getattr(warm_worker, "conversation_id", None) or self.session_id
                    self._from_pool = True
                    return

            proc = await self.process.spawn(conversation_id=conversation_id)
            if self.process._process is None and proc is not None:
                self.process._process = proc
            init_line = await self.process.readline()
            if init_line:
                try:
                    data = fast_json_loads(init_line.strip())
                    if data.get("event") == "init":
                        self.conversation_id = data.get("conversation_id", self.session_id)
                except Exception:
                    pass
            
    async def stop(self) -> None:
        """Stop the adapter and terminate process."""
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        # Transition state BEFORE terminating so in-flight stream_events()
        # generators observe STATE_STOPPED and exit cleanly.
        await self.state.transition(STATE_STOPPED)
        if self._from_pool:
            from .pool import get_pool
            await get_pool().release(self.process)
            self._from_pool = False
            self.process = ProcessManager(self.session_id, self.config)
        else:
            await self.process.terminate()
        
    async def restart(self, conversation_id: Optional[str] = None) -> None:
        """Restart the adapter, optionally resuming conversation."""
        await self.state.transition(STATE_RESTARTING)
        # Terminate process directly (without going through stop()'s state transition)
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        if self._from_pool:
            from .pool import get_pool
            await get_pool().release(self.process)
            self._from_pool = False
            self.process = ProcessManager(self.session_id, self.config)
        else:
            await self.process.terminate()
        # Re-initialize with the (optionally resumed) conversation
        resume_id = conversation_id or self.conversation_id
        try:
            await self._ensure_process(conversation_id=resume_id)
            await self.state.transition(STATE_READY)
        except Exception as e:
            logger.error(f"Failed to restart adapter: {e}")
            await self.state.transition(STATE_ERROR)
            raise
        
    async def _ensure_ready(self) -> None:
        """Ensures the adapter is ready to process a prompt."""
        if self.state.current != STATE_READY:
            if self.state.current in (STATE_BUSY, STATE_STREAMING):
                raise InvalidState("Adapter is currently busy with another prompt.")
            if self.state.current == STATE_ERROR and self.config.auto_recover:
                await self.restart()
            elif self.state.current == STATE_STOPPED:
                await self.start()
            else:
                raise InvalidState(f"Adapter is in state: {self.state.current}")
        
        # Ensure underlying process is alive
        if not self.process.is_running:
            await self._ensure_process()
                
    async def stream_events(
        self,
        prompt: str,
        on_question: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Sends a prompt to the persistent agy process and yields StreamEvent objects.
        Handles interactive questions and mid-session quota limit failovers without recursion.
        """
        while True:
            await self._ensure_ready()
            await self.state.transition(STATE_STREAMING)
            should_failover = False
            
            try:
                msg = fast_json_dumps({"event": "user", "message": {"content": prompt}})
                await self.process.write_line(msg)
                
                while True:
                    line = await self.process.readline()
                    if not line:
                        if self.state.current in (STATE_STOPPED, STATE_RESTARTING):
                            return
                        err = ""
                        if self.process._process and self.process._process.stderr:
                            try:
                                err_bytes = await self.process._process.stderr.read()
                                err = err_bytes.decode(errors="replace")
                            except Exception:
                                pass

                        # Mid-session limit recovery on process exit
                        if _is_quota_error(err) and self._fallback_chain:
                            next_model = self._fallback_chain.pop(0)
                            logger.warning(
                                f"Process exited on quota limit ({err.strip()}). Failing over to model: {next_model}"
                            )
                            self.config.model = next_model
                            self.process.config.model = next_model
                            should_failover = True
                            break

                        logger.error(f"agy process exited with code {self.process._process.returncode if self.process._process else 'None'}. stderr: {err}")
                        raise ProcessCrash(f"agy process terminated unexpectedly during stream. Code: {self.process._process.returncode if self.process._process else 'None'}. stderr: {err}")
                    
                    try:
                        data = fast_json_loads(line)
                    except Exception:
                        continue
                    
                    event_name = data.get("event")

                    # Handle interactive questions from agy CLI
                    if event_name in ("interaction", "ask_question"):
                        interaction_data = data.get("interaction") or data.get("ask_question") or data
                        interaction_id = (
                            interaction_data.get("id")
                            or data.get("interaction_id")
                            or data.get("id")
                            or "default"
                        )
                        evt = StreamEvent(
                            event="question",
                            interaction_id=interaction_id,
                            question_data=interaction_data,
                            raw=data,
                        )
                        yield evt

                        if on_question:
                            try:
                                if asyncio.iscoroutinefunction(on_question):
                                    answer = await on_question(interaction_data)
                                else:
                                    answer = on_question(interaction_data)
                                response_payload = {
                                    "event": "interaction_response",
                                    "interaction_id": interaction_id,
                                    "response": answer,
                                }
                                await self.process.write_line(fast_json_dumps(response_payload))
                            except Exception as q_err:
                                logger.error(f"Error handling question callback: {q_err}")
                        continue

                    if event_name == "step_update":
                        step = data.get("step_update", {})
                        tool_info = step.get("tool_info") or {}
                        tool_name = step.get("tool_name") or tool_info.get("name")
                        is_ask_q = tool_name == "ask_question" or step.get("step_type") == "ask_question"
                        q_data = tool_info.get("parameters") if is_ask_q else None

                        evt = StreamEvent(
                            event="step_update",
                            step_type=step.get("step_type"),
                            state=step.get("state"),
                            text_delta=step.get("text_delta"),
                            thinking_delta=step.get("thinking_delta") or step.get("thinking"),
                            tool_name=tool_name,
                            tool_parameters=tool_info.get("parameters"),
                            tool_output=tool_info.get("output"),
                            duration_seconds=step.get("duration_seconds"),
                            usage=step.get("usage"),
                            raw=data,
                            question_data=q_data,
                        )
                        yield evt

                        if is_ask_q and step.get("state") == "ACTIVE" and on_question:
                            try:
                                if asyncio.iscoroutinefunction(on_question):
                                    answer = await on_question(q_data or {})
                                else:
                                    answer = on_question(q_data or {})
                                response_payload = {
                                    "event": "interaction_response",
                                    "interaction_id": str(step.get("step_index", "default")),
                                    "response": answer,
                                }
                                await self.process.write_line(fast_json_dumps(response_payload))
                            except Exception as q_err:
                                logger.error(f"Error handling ask_question callback: {q_err}")

                    elif event_name == "result":
                        res = data.get("result", {})
                        status = res.get("status")
                        evt = StreamEvent(
                            event="result",
                            state=status,
                            usage=res.get("usage"),
                            raw=data,
                        )
                        if status == "ERROR":
                            err_msg = res.get("error", "Unknown error in agy result")
                            # Mid-session limit recovery in stream result
                            if _is_quota_error(err_msg) and self._fallback_chain:
                                next_model = self._fallback_chain.pop(0)
                                logger.warning(
                                    f"Mid-session limit reached ({err_msg}). Failing over to model: {next_model}"
                                )
                                self.config.model = next_model
                                self.process.config.model = next_model
                                should_failover = True
                                break
                            raise StreamError(err_msg)
                        yield evt
                        break

                if should_failover:
                    await self.restart(conversation_id=self.conversation_id)
                    await self.state.transition(STATE_READY)
                    continue

                await self.events.emit(EVENT_PROMPT_COMPLETED)
                await self.state.transition(STATE_READY)
                return
                
            except Exception as e:
                logger.error(f"Error during stream: {e}")
                await self.state.transition(STATE_ERROR)
                await self.events.emit(EVENT_PROCESS_CRASHED, error=str(e))
                raise

    async def stream(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
        on_question: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Sends a prompt and yields response text tokens incrementally.
        Calls on_status(msg), on_event(evt), or on_question(q) during generation.
        """
        last_status = None
        async for evt in self.stream_events(prompt, on_question=on_question):
            if on_event:
                if asyncio.iscoroutinefunction(on_event):
                    await on_event(evt)
                else:
                    on_event(evt)

            if on_status and evt.status_message and evt.status_message != last_status:
                last_status = evt.status_message
                if asyncio.iscoroutinefunction(on_status):
                    await on_status(evt.status_message)
                else:
                    on_status(evt.status_message)

            if evt.text_delta:
                yield evt.text_delta
                
    async def send(
        self,
        prompt: str,
        on_status: Optional[Callable[[str], Any]] = None,
        on_event: Optional[Callable[[StreamEvent], Any]] = None,
        on_question: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> str:
        """
        Sends a prompt and returns the full response string.
        """
        response_parts = []
        async for chunk in self.stream(prompt, on_status=on_status, on_event=on_event, on_question=on_question):
            response_parts.append(chunk)
        return "".join(response_parts)
