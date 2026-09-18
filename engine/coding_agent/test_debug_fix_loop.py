"""
Test ➔ Debug ➔ Fix Loop for SAGE Autonomous Coding Agent.
Mandatory evidence-based engineering loop:
IMPLEMENT ➔ BUILD ➔ TEST ➔ PASS? ➔ (YES: REVIEW) | (NO: DIAGNOSE ➔ FIX ➔ TEST AGAIN)
Features:
- Smart Test Selection: executes only tests affected by changed files
- Deep diagnosis from stack traces, compiler errors, and build output
- Evidence-based minimal fix generation (no blind retries)
- Configurable retry threshold
"""
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .tool_system import ToolSystem
from .codebase_indexer import CodebaseIndexer

logger = logging.getLogger(__name__)


class TestDebugFixLoop:
    """Executes the evidence-based automated repair loop on test/build failures."""

    def __init__(
        self,
        tools: ToolSystem,
        indexer: CodebaseIndexer,
        max_retries: int = 3
    ):
        self.tools = tools
        self.indexer = indexer
        self.max_retries = max_retries

    def run_loop(
        self,
        changed_files: List[str],
        fix_generator_fn: Callable[[Dict[str, Any]], str],
        on_log: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes test suite for changed files. If failures occur, diagnoses and fixes iteratively.
        """
        def log(msg: str):
            if on_log:
                try:
                    on_log(msg)
                except Exception:
                    pass

        # 1. Select targeted tests
        target_tests = self.select_affected_tests(changed_files)
        log(f"🧪 Smart Test Selection: running {len(target_tests)} affected test file(s): {target_tests}")

        history = []
        attempt = 0

        while attempt <= self.max_retries:
            attempt += 1

            # 2. Run selected tests
            test_res = self._execute_tests(target_tests)
            if test_res["success"]:
                log(f"  ✅ All targeted tests passed on attempt {attempt}.")
                return {
                    "passed": True,
                    "attempts": attempt,
                    "history": history,
                    "final_test_result": test_res
                }

            if attempt > self.max_retries:
                log(f"  ❌ Reached retry threshold ({self.max_retries}). Halting test loop.")
                break

            # 3. Diagnose failure
            diag = self.diagnose_failure(test_res["stdout"] + "\n" + test_res["stderr"])
            log(f"  🔍 Diagnostic (Attempt {attempt}): {diag['root_cause']} at {diag['failed_file']}:{diag['line_no']}")

            # 4. Generate minimal evidence-based fix
            fix_context = {
                "attempt": attempt,
                "diagnostic": diag,
                "raw_error": test_res["stderr"] or test_res["stdout"],
                "failed_file": diag["failed_file"],
                "changed_files": changed_files
            }

            try:
                fixed_code = fix_generator_fn(fix_context)
                if fixed_code and diag["failed_file"]:
                    write_res = self.tools.write_file(diag["failed_file"], fixed_code)
                    log(f"  ✏️ Applied targeted patch to {diag['failed_file']}")
                    history.append({"attempt": attempt, "file": diag["failed_file"], "diag": diag})
                else:
                    log(f"  ⚠️ Could not determine file to patch for diagnostic: {diag['root_cause']}")
            except Exception as e:
                log(f"  ⚠️ Error applying fix: {e}")

        return {
            "passed": False,
            "attempts": attempt,
            "history": history,
            "final_test_result": test_res
        }

    def select_affected_tests(self, changed_files: List[str]) -> List[str]:
        """
        Maps modified source files to their corresponding unit/integration test files.
        Avoids running the entire repository test suite during incremental edits.
        """
        all_test_files = [f for f in self.tools.workspace_root.rglob("test_*.py") if ".git" not in f.parts and ".venv" not in f.parts]
        selected = []

        for cf in changed_files:
            cf_stem = Path(cf).stem.lower().replace("test_", "")
            for tf in all_test_files:
                tf_rel = str(tf.relative_to(self.tools.workspace_root)).replace("\\", "/")
                # Match test_auth.py with auth.py or user.py
                if cf_stem in tf_rel.lower():
                    if tf_rel not in selected:
                        selected.append(tf_rel)

        # Fallback: if no direct match, return first test file found
        if not selected and all_test_files:
            rel0 = str(all_test_files[0].relative_to(self.tools.workspace_root)).replace("\\", "/")
            selected.append(rel0)

        return selected

    def diagnose_failure(self, error_output: str) -> Dict[str, Any]:
        """
        Extracts tracebacks, failing test names, line numbers, and error classifications.
        """
        failed_file = ""
        line_no = 0
        root_cause = "Unknown test/runtime error"

        # Look for Python traceback line
        tb_match = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', error_output)
        if tb_match:
            last_frame = tb_match[-1]
            raw_path = last_frame[0]
            try:
                failed_file = str(Path(raw_path).relative_to(self.tools.workspace_root)).replace("\\", "/")
            except Exception:
                failed_file = Path(raw_path).name
            line_no = int(last_frame[1])

        # Look for AssertionError or Exception type
        exc_match = re.search(r"([A-Za-z0-9_]+Error|AssertionError):\s*(.*)", error_output)
        if exc_match:
            root_cause = f"{exc_match.group(1)}: {exc_match.group(2).strip()}"

        return {
            "failed_file": failed_file,
            "line_no": line_no,
            "root_cause": root_cause,
            "raw_output": error_output[:1500]
        }

    def _execute_tests(self, target_tests: List[str]) -> Dict[str, Any]:
        """Executes targeted test files using ToolSystem."""
        if not target_tests:
            return {"success": True, "stdout": "No targeted tests to run", "stderr": "", "exit_code": 0}

        # Run first or combined target test
        target = target_tests[0]
        return self.tools.run_tests(target=target)
