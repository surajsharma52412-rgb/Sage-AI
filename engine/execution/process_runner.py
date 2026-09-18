"""
Process Runner for Sage Multi-Agentic AI Architecture.
Executes terminal commands, test runners, and deployment scripts with safety bounds.
"""
import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config import WORKSPACE_ROOT

logger = logging.getLogger(__name__)


class ProcessRunner:
    """Manages subprocess execution for dev tools, tests, and build commands."""

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout

    def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Runs a command string using system shell safely."""
        work_dir = cwd or WORKSPACE_ROOT
        timeout_val = timeout or self.default_timeout

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
                cwd=str(work_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout_val} seconds.",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }


_process_runner_instance: Optional[ProcessRunner] = None

def get_process_runner() -> ProcessRunner:
    global _process_runner_instance
    if _process_runner_instance is None:
        _process_runner_instance = ProcessRunner()
    return _process_runner_instance
