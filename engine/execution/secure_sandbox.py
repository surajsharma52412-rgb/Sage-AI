"""
Secure Sandbox for Sage Multi-Agentic AI Architecture.
Safely executes Python scripts and code snippets with timeout guards,
syntax pre-verification, and output stream capture.
"""
import os
import sys
import io
import ast
import time
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config import WORKSPACE_ROOT

logger = logging.getLogger(__name__)


class SecureSandbox:
    """Provides isolated, guarded code execution for Agent Execution modules."""

    def __init__(self, timeout_sec: float = 30.0):
        self.timeout_sec = timeout_sec

    def validate_syntax(self, code: str) -> Dict[str, Any]:
        """Performs static syntax verification using Python AST."""
        try:
            ast.parse(code)
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"SyntaxError on line {e.lineno}: {e.msg}",
                "lineno": e.lineno
            }

    def is_safe_to_execute(self, code: str) -> tuple[bool, str]:
        """
        Performs static analysis to reject overtly destructive operations.
        (e.g., formatting drives, fork bombs).
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax Error: {e.msg} at line {e.lineno}"

        # Disallow raw ctypes memory overrides or extreme destructive OS calls
        dangerous_patterns = [
            "ctypes.windll", "ctypes.cdll",
            "shutil.rmtree('/')", "os.system('rm -rf /')",
            "os.system('rmdir /s /q c:\\')", "os.system('format ')"
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                return False, f"Execution denied: pattern '{pattern}' flagged as high-risk."

        return True, "Safe"

    def execute_code(
        self,
        code: str,
        cwd: Optional[Path] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes code in an isolated subprocess to prevent main GUI/process crashes.
        Returns: {success: bool, stdout: str, stderr: str, exit_code: int, duration_ms: float}
        """
        safe, reason = self.is_safe_to_execute(code)
        if not safe:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Security Guard: {reason}",
                "exit_code": -1,
                "duration_ms": 0.0
            }

        work_dir = cwd or WORKSPACE_ROOT
        timeout_val = timeout or self.timeout_sec
        start_t = time.time()

        # Execute using the active virtual environment Python if available
        py_exe = sys.executable

        try:
            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            res = subprocess.run(
                [py_exe, "-c", code],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout_val,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            duration_ms = round((time.time() - start_t) * 1000.0, 2)
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "duration_ms": duration_ms
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_val} seconds.",
                "exit_code": -1,
                "duration_ms": round((time.time() - start_t) * 1000.0, 2)
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration_ms": round((time.time() - start_t) * 1000.0, 2)
            }


_secure_sandbox_instance: Optional[SecureSandbox] = None

def get_secure_sandbox() -> SecureSandbox:
    global _secure_sandbox_instance
    if _secure_sandbox_instance is None:
        _secure_sandbox_instance = SecureSandbox()
    return _secure_sandbox_instance
