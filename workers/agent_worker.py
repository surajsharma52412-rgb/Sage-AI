"""
Agent Worker QThread for Sage AI (Lunar Engine).
Runs autonomous project coding agent tasks asynchronously via SAGE Coding Agent Architecture (v6),
emitting logs, diffs, and completion signals.
"""
from typing import Optional, Dict, Any, List
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from engine.coding_agent import CodingAgentOrchestrator
from engine.router import FallbackRouter


class AgentWorker(QThread):
    """Asynchronous worker executing project agent tasks using v6 Coding Agent Architecture."""

    log_emitted = Signal(str)
    diff_emitted = Signal(str, str)  # (path, diff_content)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        workspace_path: Path,
        task_instruction: str,
        test_command: Optional[str] = None,
        selected_model: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.workspace_path = Path(workspace_path)
        self.task_instruction = task_instruction
        self.test_command = test_command
        self.selected_model = selected_model
        self.router = FallbackRouter()

    def run(self):
        try:
            def on_log(msg: str):
                self.log_emitted.emit(msg)

            def on_diff(path: str, diff_text: str):
                self.diff_emitted.emit(path, diff_text)

            orchestrator = CodingAgentOrchestrator(
                workspace_root=self.workspace_path,
                model_override=self.selected_model if self.selected_model and self.selected_model != "Auto Router" else None
            )

            def llm_caller(prompt: str, system_prompt: str, preferred_providers: Optional[List[str]] = None) -> Dict[str, Any]:
                res = self.router.route_and_call(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    preferred_providers=preferred_providers,
                    selected_model=self.selected_model if self.selected_model and self.selected_model != "Auto Router" else None
                )
                return res

            report = orchestrator.execute_project(
                goal=self.task_instruction,
                context={"test_command": self.test_command},
                llm_caller_fn=llm_caller,
                on_stage=on_log,
                on_log=on_log,
                on_diff=on_diff
            )

            # Map written files to operations format expected by UI components
            ops = []
            for wf in report.get("written_files", []):
                ops.append({
                    "op": "write" if wf.get("is_new") else "modify",
                    "path": wf.get("path"),
                    "status": "success"
                })

            unified_report = {
                "success": report.get("success", True),
                "summary": report.get("summary", "Coding Agent v6 executed successfully."),
                "operations": ops,
                "tree": report.get("tree", ""),
                "timeline": report.get("timeline", []),
                "validation": report.get("validation", {}),
                "deliverables": report.get("deliverables", []),
                "error": None if report.get("success") else "Task execution encountered issues."
            }

            self.finished.emit(unified_report)

        except Exception as e:
            self.failed.emit(f"Agent Execution Error: {str(e)}")
