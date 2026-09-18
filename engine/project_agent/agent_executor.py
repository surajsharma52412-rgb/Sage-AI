"""
Agent Executor for Autonomous Project Coding Agent.
Applies atomic file modifications, executes test suites, and runs self-repair loops.
"""
import os
import subprocess
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .workspace_inspector import WorkspaceInspector
from .agent_planner import AgentPlanner


class AgentExecutor:
    """Executes validated JSON plans with backups, test running, and self-repair."""

    def __init__(
        self,
        inspector: WorkspaceInspector,
        planner: Optional[AgentPlanner] = None,
        max_repairs: int = 2
    ):
        self.inspector = inspector
        self.planner = planner or AgentPlanner()
        self.max_repairs = max_repairs

    def execute_task(
        self,
        task_instruction: str,
        test_command: Optional[str] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_diff: Optional[Callable[[str, str], None]] = None,
        selected_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entrypoint: generates plan, executes operations, runs tests, and repairs if needed.
        """
        def log(msg: str):
            if on_log:
                try:
                    on_log(msg)
                except Exception:
                    pass

        log(f"🚀 Starting Autonomous Agent on workspace: {self.inspector.root.name}")
        log(f"📋 Task: {task_instruction}")

        repair_attempt = 0
        repair_context = None
        final_success = False
        all_diffs = []
        applied_ops = []

        while repair_attempt <= self.max_repairs:
            if repair_attempt > 0:
                log(f"🔄 Self-Repair Loop: Attempt {repair_attempt} of {self.max_repairs}...")

            log("🧠 Generating implementation plan...")
            plan = self.planner.generate_plan(
                inspector=self.inspector,
                task_instruction=task_instruction,
                repair_context=repair_context,
                selected_model=selected_model
            )

            log(f"📝 Plan summary: {plan.get('summary', 'Executing operations')}")
            operations = plan.get("operations", [])

            if not operations:
                log("⚠️ No valid operations returned by planner.")
                reason = "No operations executed"
                if plan.get("notes"):
                    for n in plan["notes"]:
                        log(f"ℹ️ Note: {n}")
                    reason = plan["notes"][0]
                elif plan.get("summary"):
                    reason = plan["summary"]
                return {
                    "success": False,
                    "summary": plan.get("summary", "Plan contained 0 operations"),
                    "operations": [],
                    "logs": "No operations executed",
                    "error": reason
                }

            # Apply operations
            log(f"⚙️ Applying {len(operations)} atomic file operations...")
            op_results, diffs = self._apply_operations(operations, on_diff=on_diff)
            applied_ops.extend(op_results)
            all_diffs.extend(diffs)

            for res in op_results:
                log(f"  • [{res['op'].upper()}] {res['path']} -> {res['status']}")

            # Run automated tests if command provided or tests detected
            cmd = test_command or self._detect_test_command()
            if cmd:
                log(f"🧪 Running automated test suite: `{cmd}`...")
                test_result = self._run_test_command(cmd)

                if test_result["success"]:
                    log(f"✅ Tests PASSED ({test_result['returncode']}):\n{test_result['output']}")
                    final_success = True
                    break
                else:
                    log(f"❌ Tests FAILED ({test_result['returncode']}):\n{test_result['output'][:500]}")
                    repair_context = (
                        f"Test command `{cmd}` failed with exit code {test_result['returncode']}.\n"
                        f"Output:\n{test_result['output']}"
                    )
                    repair_attempt += 1
            else:
                log("ℹ️ No test suite configured/detected. Operations applied directly.")
                final_success = True
                break

        status_msg = "Task completed successfully!" if final_success else "Task finished with remaining issues."
        log(f"🏁 {status_msg}")

        return {
            "success": final_success,
            "summary": plan.get("summary", "Complete"),
            "operations": applied_ops,
            "diffs": all_diffs,
            "repairs_performed": repair_attempt,
            "notes": plan.get("notes", [])
        }

    def _apply_operations(
        self,
        operations: List[Dict[str, Any]],
        on_diff: Optional[Callable[[str, str], None]] = None
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Applies write and delete operations with atomic safeguards."""
        results = []
        diff_texts = []

        for op in operations:
            op_type = op["op"]
            rel_path = op["path"]
            content = op.get("content", "")

            target_file = self.inspector.resolve_safe_path(rel_path)
            old_content = ""
            if target_file.is_file():
                try:
                    with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                        old_content = f.read()
                except Exception:
                    pass

            if op_type == "write":
                # Ensure parent directories exist
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Compute diff
                diff = list(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}"
                ))
                diff_str = "".join(diff) if diff else "(New file created)"
                diff_texts.append(diff_str)
                if on_diff:
                    on_diff(rel_path, diff_str)

                # Write content safely
                temp_file = target_file.with_suffix(f"{target_file.suffix}.tmp")
                try:
                    with open(temp_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    temp_file.replace(target_file)
                    results.append({"op": "write", "path": rel_path, "status": "written"})
                except Exception as e:
                    if temp_file.exists():
                        temp_file.unlink(missing_ok=True)
                    results.append({"op": "write", "path": rel_path, "status": f"error: {e}"})

            elif op_type == "delete":
                if target_file.exists() and target_file.is_file():
                    try:
                        target_file.unlink()
                        results.append({"op": "delete", "path": rel_path, "status": "deleted"})
                        diff_texts.append(f"Deleted file: {rel_path}")
                        if on_diff:
                            on_diff(rel_path, f"Deleted file: {rel_path}")
                    except Exception as e:
                        results.append({"op": "delete", "path": rel_path, "status": f"error: {e}"})
                else:
                    results.append({"op": "delete", "path": rel_path, "status": "file did not exist"})

        return results, diff_texts

    def _detect_test_command(self) -> Optional[str]:
        """Inspects workspace for common test runners."""
        root = self.inspector.root
        if (root / "pytest.ini").exists() or (root / "tests").is_dir():
            return "python -m unittest discover -s tests"
        elif (root / "package.json").exists():
            return "npm test"
        return None

    def _run_test_command(self, command: str) -> Dict[str, Any]:
        """Executes test command inside workspace root with timeout."""
        try:
            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            res = subprocess.run(
                command,
                shell=True,
                cwd=str(self.inspector.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=45,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            return {
                "success": res.returncode == 0,
                "returncode": res.returncode,
                "output": res.stdout
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "output": f"Test command `{command}` timed out after 45 seconds."
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "output": f"Error running test command: {str(e)}"
            }
