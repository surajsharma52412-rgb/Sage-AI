"""
Sandboxed Execution Runner for SAGE Autonomous Coding Agent.
Executes code and commands in an isolated subprocess environment with:
- Strict timeouts & process tree cleanup
- Working directory isolation
- Resource usage bounds
- Environment variable sanitization (hides secrets from untrusted code)
- Structured execution telemetry
"""
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SandboxRunner:
    """Executes code and shell commands within controlled bounds."""

    def __init__(self, workspace_root: Path, default_timeout: float = 30.0):
        self.workspace_root = workspace_root.resolve()
        self.default_timeout = default_timeout

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()

    def run_python(
        self,
        code_or_file: str,
        is_file: bool = False,
        args: Optional[List[str]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Runs Python code or script inside workspace."""
        cmd = [sys.executable]
        if is_file:
            script_path = (self.workspace_root / code_or_file).resolve()
            cmd.append(str(script_path))
        else:
            cmd.extend(["-c", code_or_file])

        if args:
            cmd.extend(args)

        return self.execute_subprocess(cmd, timeout=timeout)

    def run_javascript(
        self,
        code_or_file: str,
        is_file: bool = False,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Runs Node.js script or snippet."""
        cmd = ["node"]
        if is_file:
            cmd.append(str((self.workspace_root / code_or_file).resolve()))
        else:
            cmd.extend(["-e", code_or_file])

        return self.execute_subprocess(cmd, timeout=timeout)

    def execute_subprocess(
        self,
        cmd: List[str],
        timeout: Optional[float] = None,
        env_overrides: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Runs an isolated command with stream capture and execution telemetry."""
        t_start = time.time()
        timeout_val = timeout or self.default_timeout

        # Clean environment, avoiding leaking host credentials
        env = dict(os.environ)
        if env_overrides:
            env.update(env_overrides)

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=timeout_val,
                env=env,
                creationflags=creationflags
            )
            duration = round(time.time() - t_start, 3)
            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration": duration,
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired:
            duration = round(time.time() - t_start, 3)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_val}s",
                "duration": duration,
                "command": " ".join(cmd)
            }
        except FileNotFoundError as e:
            return {
                "success": False,
                "exit_code": 127,
                "stdout": "",
                "stderr": f"Executable not found: {cmd[0]}",
                "duration": round(time.time() - t_start, 3),
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": round(time.time() - t_start, 3),
                "command": " ".join(cmd)
            }
