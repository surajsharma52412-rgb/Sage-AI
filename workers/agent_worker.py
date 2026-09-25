"""
Agent Worker QThread for Sage AI.
Runs autonomous project coding agent tasks asynchronously via SAGE Coding Agent Architecture,
emitting structured live events, real-time file tracking, diffs, and model selection.
"""
import time
import re
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from engine.coding_agent import CodingAgentOrchestrator
from engine.coding_agent.events import CodingAgentEvent, EventType, AgentState
from engine.auto_router.coding_router import AutoCodingRouter
from engine.router import FallbackRouter


def extract_thinking(content: str) -> Tuple[Optional[str], str]:
    """Extracts <think>...</think> chain-of-thought and returns (thinking_text, clean_content)."""
    match = re.search(r'<think>(.*?)</think>', content, flags=re.DOTALL | re.IGNORECASE)
    if match:
        thinking_text = match.group(1).strip()
        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
        return thinking_text, clean_content
    unclosed = re.search(r'<think>(.*)', content, flags=re.DOTALL | re.IGNORECASE)
    if unclosed:
        thinking_text = unclosed.group(1).strip()
        clean_content = re.sub(r'<think>.*', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
        return thinking_text, clean_content
    return None, content


class AgentWorker(QThread):
    """Asynchronous worker executing project agent tasks with structured live event streaming."""

    # Structured Live Activity signals
    event_emitted = Signal(dict)
    status_changed = Signal(str)
    file_tracked = Signal(str, str, str)  # (file_path, action, status)
    model_selected_signal = Signal(dict)  # Model information dictionary
    diff_emitted = Signal(str, str)       # (file_path, diff_content)
    log_emitted = Signal(str)
    finished = Signal(dict)
    failed = Signal(str)

    # Live Thinking Cloud signals
    thinking_started = Signal()
    thinking_chunk = Signal(str)
    thinking_finished = Signal(float)

    def __init__(
        self,
        workspace_path: Path,
        task_instruction: str,
        test_command: Optional[str] = None,
        selected_model: Optional[str] = None,
        allow_fallback: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.workspace_path = Path(workspace_path)
        self.task_instruction = task_instruction
        self.test_command = test_command
        self.selected_model = selected_model
        self.allow_fallback = allow_fallback
        self.router = FallbackRouter()
        self.coding_router = AutoCodingRouter()
        self._is_cancelled = False

    def cancel(self):
        """Requests graceful cancellation."""
        self._is_cancelled = True

    def run(self):
        project_start_time = time.time()
        try:
            self.thinking_started.emit()
            self.status_changed.emit(AgentState.ANALYZING.value)
            self._emit_event(
                event_type=EventType.TASK_STARTED.value,
                state=AgentState.ANALYZING.value,
                message=f"Starting task: {self.task_instruction[:80]}..."
            )
            self.thinking_chunk.emit(f"✦ Ingesting goal: {self.task_instruction}\n")

            # 1. Resolve Model Selection via Auto Coding Router
            model_info = self.coding_router.select_model_for_execution(
                selected_model=self.selected_model,
                allow_fallback=self.allow_fallback,
                prompt=self.task_instruction,
                target_file=str(self.workspace_path)
            )
            self.model_selected_signal.emit(model_info)

            sel_disp = model_info.get("display_name", self.selected_model or "Auto")
            rank_txt = f"#{model_info.get('coding_rank', 1)}" if model_info.get("coding_rank") else ""
            self._emit_event(
                event_type=EventType.MODEL_SELECTED.value,
                state=AgentState.PLANNING.value,
                message=f"Model: {sel_disp} {rank_txt} ({model_info.get('provider_name')}) • Score: {model_info.get('coding_score')}",
                metadata=model_info
            )
            self.thinking_chunk.emit(f"✦ Selected engine: {sel_disp} (rank {rank_txt}, provider: {model_info.get('provider_name')})\n")

            # 2. Wire callbacks for Live Activity stream
            def on_log(msg: str):
                if self._is_cancelled:
                    return
                self.log_emitted.emit(msg)
                
                # Check for high-level operations to emit clean events
                msg_clean = msg.strip()
                # Stream cognitive steps into the thinking cloud
                if any(k in msg_clean.upper() for k in ("UNDERSTAND", "ANALYZ", "PLAN", "CHECKPOINT", "IMPLEMENT", "EXECUTE", "TEST", "DEBUG", "REVIEW", "VERIFY", "DELIVER")):
                    self.thinking_chunk.emit(f"✦ {msg_clean}\n")

                if "ANALYZ" in msg_clean.upper() or "SCANNING" in msg_clean.upper():
                    self.status_changed.emit(AgentState.ANALYZING.value)
                    self._emit_event(EventType.TASK_ANALYZING.value, AgentState.ANALYZING.value, message=msg_clean)
                elif "PLAN" in msg_clean.upper():
                    self.status_changed.emit(AgentState.PLANNING.value)
                    self._emit_event(EventType.TASK_STARTED.value, AgentState.PLANNING.value, message=msg_clean)
                elif "TEST" in msg_clean.upper() or "VALIDAT" in msg_clean.upper():
                    self.status_changed.emit(AgentState.TESTING.value)
                    self._emit_event(EventType.TEST_STARTED.value, AgentState.TESTING.value, message=msg_clean)

            def on_diff(path: str, diff_text: str):
                if self._is_cancelled:
                    return
                self.diff_emitted.emit(path, diff_text)
                self.status_changed.emit(AgentState.EDITING.value)
                self.file_tracked.emit(path, "Editing", "● Working")
                self._emit_event(
                    event_type=EventType.FILE_MODIFIED.value,
                    state=AgentState.EDITING.value,
                    file=path,
                    action="Editing",
                    diff=diff_text,
                    message=f"Applied code edits to {Path(path).name}"
                )

            # 3. Instantiate Orchestrator
            active_model_id = model_info.get("selected_model")
            orchestrator = CodingAgentOrchestrator(
                workspace_root=self.workspace_path,
                model_override=active_model_id
            )

            # 4. LLM execution with automatic coding fallback support & live thinking tokens
            current_model_id = active_model_id
            fallback_queue = list(model_info.get("fallback_queue", []))

            def llm_caller(prompt: str, system_prompt: str, preferred_providers: Optional[List[str]] = None) -> Dict[str, Any]:
                nonlocal current_model_id
                if self._is_cancelled:
                    raise InterruptedError("Coding Agent cancelled by user.")

                attempt_model = current_model_id if current_model_id and "auto" not in current_model_id.lower() else None
                in_think = False
                streamed_chunks = []
                call_start = time.time()
                self.thinking_started.emit()

                def on_chunk(token: str):
                    nonlocal in_think, streamed_chunks, call_start
                    if self._is_cancelled:
                        return
                    if "<think>" in token:
                        parts = token.split("<think>", 1)
                        in_think = True
                        call_start = time.time()
                        self.thinking_started.emit()
                        token = parts[1]
                    if in_think:
                        if "</think>" in token:
                            parts = token.split("</think>", 1)
                            if parts[0]:
                                self.thinking_chunk.emit(parts[0])
                                streamed_chunks.append(parts[0])
                            self.thinking_finished.emit(time.time() - call_start)
                            in_think = False
                        else:
                            self.thinking_chunk.emit(token)
                            streamed_chunks.append(token)

                try:
                    res = self.router.route_and_call(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        preferred_providers=preferred_providers,
                        selected_model=attempt_model,
                        on_chunk=on_chunk
                    )
                    if res and res.get("response"):
                        resp_text = res.get("response") or res.get("text") or ""
                        th_text, _ = extract_thinking(resp_text)
                        if th_text and not streamed_chunks:
                            self.thinking_chunk.emit(f"{th_text}\n")
                            self.thinking_finished.emit(time.time() - call_start)
                        return res
                    raise RuntimeError("Received empty or invalid response from model.")
                except Exception as ex:
                    # Check if fallback is enabled and we have queue candidates
                    if self.allow_fallback and fallback_queue:
                        next_model = fallback_queue.pop(0)
                        self._emit_event(
                            event_type=EventType.MODEL_FALLBACK.value,
                            state=AgentState.FALLBACK.value,
                            message=f"⚠ {current_model_id or 'Model'} errors: {str(ex)[:60]}. Fallback ➔ {next_model}"
                        )
                        self.thinking_chunk.emit(f"⚠️ Model fallback activated ➔ {next_model}\n")
                        current_model_id = next_model
                        return self.router.route_and_call(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            preferred_providers=preferred_providers,
                            selected_model=next_model,
                            on_chunk=on_chunk
                        )
                    raise ex

            # 5. Run real autonomous project execution pipeline
            self.status_changed.emit(AgentState.RUNNING.value)
            report = orchestrator.execute_project(
                goal=self.task_instruction,
                context={"test_command": self.test_command},
                llm_caller_fn=llm_caller,
                on_stage=on_log,
                on_log=on_log,
                on_diff=on_diff
            )

            # 6. Map written and verified files
            ops = []
            for wf in report.get("written_files", []):
                p = wf.get("path", "")
                is_new = wf.get("is_new", False)
                action_name = "Creating" if is_new else "Editing"
                self.file_tracked.emit(p, action_name, "✓ Completed")
                ops.append({
                    "op": "write" if is_new else "modify",
                    "path": p,
                    "status": "success"
                })

            # Check for test results if present
            if self.test_command:
                self._emit_event(
                    event_type=EventType.COMMAND_STARTED.value,
                    state=AgentState.TESTING.value,
                    command=self.test_command,
                    message=f"Ran test suite: {self.test_command}"
                )

            self.thinking_finished.emit(time.time() - project_start_time)
            self.status_changed.emit(AgentState.COMPLETED.value)
            self._emit_event(
                event_type=EventType.TASK_COMPLETED.value,
                state=AgentState.COMPLETED.value,
                message=f"Completed {len(ops)} file operations successfully."
            )

            unified_report = {
                "success": report.get("success", True),
                "summary": report.get("summary", "Sage Coding Agent executed successfully."),
                "operations": ops,
                "tree": report.get("tree", ""),
                "timeline": report.get("timeline", []),
                "validation": report.get("validation", {}),
                "deliverables": report.get("deliverables", []),
                "error": None if report.get("success") else "Task execution encountered issues."
            }

            self.finished.emit(unified_report)

        except InterruptedError:
            self.thinking_finished.emit(time.time() - project_start_time)
            self.status_changed.emit(AgentState.IDLE.value)
            self._emit_event(EventType.WARNING.value, AgentState.IDLE.value, message="Task stopped by user.")
            self.finished.emit({"success": False, "summary": "Task cancelled.", "operations": []})

        except Exception as e:
            self.thinking_finished.emit(time.time() - project_start_time)
            self.status_changed.emit(AgentState.ERROR.value)
            err_msg = f"Agent Execution Error: {str(e)}"
            self._emit_event(EventType.ERROR.value, AgentState.ERROR.value, message=err_msg)
            self.failed.emit(err_msg)

    def _emit_event(
        self,
        event_type: str,
        state: str,
        message: str = "",
        file: Optional[str] = None,
        action: Optional[str] = None,
        diff: Optional[str] = None,
        command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        event = CodingAgentEvent(
            event_type=event_type,
            state=state,
            message=message,
            file=file,
            action=action,
            diff=diff,
            command=command,
            metadata=metadata or {}
        )
        self.event_emitted.emit(event.to_dict())
