"""
Iterate & Improve (Self-Healing Feedback Loop) for SAGE Coding Agent Architecture (v6).
Implements the feedback loop: "If tests fail -> Feedback to relevant agents"
- Analyzes test failures, syntax errors, and missing dependencies
- Routes the exact error traceback and offending file to the responsible subagent
- Executes repair prompt, writes patched file, and re-validates
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from ..context_manager import ContextFileManager
from ..tool_ecosystem import ToolEcosystem
from .automated_validator import AutomatedValidator

logger = logging.getLogger(__name__)


class SelfHealingLoop:
    """Orchestrates iterative repair when validation, builds, or tests report failures."""

    def __init__(
        self,
        context_mgr: ContextFileManager,
        tools: ToolEcosystem,
        validator: AutomatedValidator,
        subagents: Dict[str, Any],
        max_repairs: int = 2
    ):
        self.context_mgr = context_mgr
        self.tools = tools
        self.validator = validator
        self.subagents = subagents
        self.max_repairs = max_repairs

    def run_repair_cycle(
        self,
        initial_val_report: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None,
        on_log: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Loops up to max_repairs times, feeding error diagnostics to the responsible subagents.
        """
        def log(msg: str):
            if on_log:
                try:
                    on_log(msg)
                except Exception:
                    pass

        val_report = initial_val_report
        repair_history: List[Dict[str, Any]] = []

        for attempt in range(1, self.max_repairs + 1):
            if val_report.get("passed"):
                break

            log(f"🔄 Self-Healing Feedback Loop: Iteration {attempt}/{self.max_repairs}...")

            # 1. Identify failure target and error message
            target_file = ""
            error_msg = ""
            responsible_role = "backend"

            if val_report.get("syntax_errors"):
                err = val_report["syntax_errors"][0]
                target_file = err.get("file", "")
                error_msg = f"Syntax Error at line {err.get('line')}: {err.get('msg')}"
            elif val_report.get("test_results", {}).get("stderr"):
                error_msg = val_report["test_results"]["stderr"][:800]
                target_file = "tests/test_api.py"
                responsible_role = "qa"
            elif val_report.get("test_results", {}).get("stdout"):
                error_msg = val_report["test_results"]["stdout"][:800]
                responsible_role = "backend"

            # Assign responsible agent
            if "frontend" in target_file or target_file.endswith((".html", ".css", ".js")):
                responsible_role = "frontend"
            elif "test" in target_file:
                responsible_role = "qa"
            elif "docker" in target_file.lower():
                responsible_role = "devops"
            else:
                responsible_role = "backend"

            agent = self.subagents.get(responsible_role) or self.subagents.get("backend")
            log(f"  ⚡ Routing error feedback to [{responsible_role.upper()}] agent: {error_msg[:120]}...")

            file_content = ""
            if target_file:
                try:
                    file_content = self.context_mgr.read_file(target_file)
                except Exception:
                    pass

            repair_prompt = (
                f"Auto-Repair Request: Fix the following failure in `{target_file}`:\n\n"
                f"Error Details:\n{error_msg}\n\n"
                f"Offending File Content:\n{file_content}\n\n"
                "Return the corrected, complete working code block."
            )

            system_prompt = (
                f"You are Sage AI's {agent.name if agent else 'Repair Agent'}. "
                "Diagnose the bug or error, resolve root causes, and output clean, robust fixed code."
            )

            repair_res = agent.call_llm(
                prompt=repair_prompt,
                system_prompt=system_prompt,
                llm_caller_fn=llm_caller_fn
            ) if agent else {"text": ""}

            repaired_text = repair_res.get("text", "")
            fixed_blocks = agent.extract_code_blocks(repaired_text) if agent else []

            repaired_path = target_file
            if fixed_blocks:
                repaired_path = fixed_blocks[0].get("path") or target_file
                try:
                    self.context_mgr.write_file(repaired_path, fixed_blocks[0]["content"])
                    log(f"  ✏️ Applied auto-repair patch to: {repaired_path}")
                except Exception as e:
                    log(f"  ⚠️ Could not apply patch: {e}")

            # Re-validate
            val_report = self.validator.validate_codebase()
            repair_history.append({
                "attempt": attempt,
                "role": responsible_role,
                "file": repaired_path,
                "passed": val_report.get("passed", False)
            })

            if val_report.get("passed"):
                log("  ✅ Auto-repair successfully resolved all issues!")
                break
            else:
                log("  ⚠️ Verification still reported issues after patch.")

        return {
            "passed": val_report.get("passed", False),
            "final_validation": val_report,
            "repairs_executed": repair_history
        }
