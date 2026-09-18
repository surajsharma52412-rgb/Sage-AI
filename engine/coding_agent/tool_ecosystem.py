"""
Tool Ecosystem (Coding Only) for SAGE Coding Agent Architecture (v6).
Provides tools strictly specialized for coding workflows:
- File Operations (read, write, patch, delete, list)
- Terminal / Shell Runner (safe subprocess with timeout and isolation)
- Package Management (pip, npm, yarn, pnpm, cargo, poetry)
- Git Operations (status, diff, commit, checkout)
- Database Tools (schema extraction, SQLite query, migrations)
- Web Search & Documentation retrieval
- Code Execution Runner (python, node, bash)
- Testing Runner (pytest, unittest, jest, vitest)
- Build Tools (vite, tsc, cargo, webpack)
- Cloud Deployment generator (Docker, CI/CD pipelines)
- API Testing (curl / HTTP requests with JSON response validation)
"""
import os
import sys
import json
import shutil
import sqlite3
import urllib.request
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .safety_controller import SafetyController
from .context_manager import ContextFileManager

logger = logging.getLogger(__name__)


class ToolEcosystem:
    """Consolidated tool dispatcher for coding sub-agents."""

    def __init__(self, workspace_root: Optional[Path] = None, context_mgr: Optional[ContextFileManager] = None, safety: Optional[SafetyController] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.safety = safety or SafetyController(self.workspace_root)
        self.context_mgr = context_mgr or ContextFileManager(self.workspace_root, self.safety)

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.safety.set_workspace_root(self.workspace_root)
        self.context_mgr.set_workspace_root(self.workspace_root)

    # --- 1. Terminal / Shell Execution ---

    def run_shell(self, command: str, timeout: int = 45, cwd: Optional[str] = None) -> Dict[str, Any]:
        """Runs a command inside workspace with safety checks and timeout."""
        allowed, reason = self.safety.can_execute_command(command)
        if not allowed:
            return {"success": False, "returncode": -1, "stdout": "", "stderr": reason, "command": command}

        exec_dir = self.safety.validate_safe_path(cwd) if cwd else self.workspace_root

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=str(exec_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": res.returncode == 0,
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "command": command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "returncode": -1, "stdout": "", "stderr": f"Command timed out after {timeout}s", "command": command}
        except Exception as e:
            return {"success": False, "returncode": -1, "stdout": "", "stderr": str(e), "command": command}

    # --- 2. Package Management ---

    def detect_package_managers(self) -> List[str]:
        """Detects package managers relevant to current workspace."""
        detected = []
        if (self.workspace_root / "package.json").exists():
            detected.append("npm")
            if (self.workspace_root / "pnpm-lock.yaml").exists():
                detected.append("pnpm")
            elif (self.workspace_root / "yarn.lock").exists():
                detected.append("yarn")
        if (self.workspace_root / "requirements.txt").exists() or (self.workspace_root / "pyproject.toml").exists():
            detected.append("pip")
        if (self.workspace_root / "Cargo.toml").exists():
            detected.append("cargo")
        if (self.workspace_root / "go.mod").exists():
            detected.append("go")
        return detected

    def install_packages(self, manager: str, packages: List[str]) -> Dict[str, Any]:
        """Installs dependencies via detected package manager."""
        pkg_str = " ".join(packages)
        if manager == "pip":
            cmd = f"pip install {pkg_str}"
        elif manager == "npm":
            cmd = f"npm install {pkg_str}"
        elif manager == "yarn":
            cmd = f"yarn add {pkg_str}"
        elif manager == "cargo":
            cmd = f"cargo add {pkg_str}"
        else:
            return {"success": False, "stderr": f"Unsupported package manager: {manager}"}

        return self.run_shell(cmd, timeout=120)

    # --- 3. Testing Tools ---

    def run_tests(self, test_framework: Optional[str] = None, path_or_pattern: Optional[str] = None) -> Dict[str, Any]:
        """Runs test suites (pytest, unittest, jest, vitest, etc.)."""
        # Auto-detect if framework not specified
        if not test_framework:
            if (self.workspace_root / "package.json").exists() and not (self.workspace_root / "tests").exists():
                test_framework = "npm test"
            else:
                test_framework = "unittest"

        if test_framework == "pytest":
            target = path_or_pattern or ""
            cmd = f'"{sys.executable}" -m pytest {target} --tb=short'
        elif test_framework == "unittest":
            target = path_or_pattern or "discover -s tests"
            cmd = f'"{sys.executable}" -m unittest {target}'
        elif test_framework in ("jest", "npm test"):
            cmd = "npm test -- --watchAll=false"
        elif test_framework == "vitest":
            cmd = "npx vitest run"
        else:
            cmd = test_framework

        return self.run_shell(cmd, timeout=30)

    # --- 4. Build Tools ---

    def run_build(self, build_cmd: Optional[str] = None) -> Dict[str, Any]:
        """Executes build command (e.g. npm run build, vite build, tsc)."""
        if not build_cmd:
            if (self.workspace_root / "package.json").exists():
                build_cmd = "npm run build"
            elif (self.workspace_root / "Cargo.toml").exists():
                build_cmd = "cargo build"
            elif (self.workspace_root / "Makefile").exists():
                build_cmd = "make"
            else:
                return {"success": True, "stdout": "No build step required", "stderr": ""}

        return self.run_shell(build_cmd, timeout=120)

    # --- 5. Database Tools ---

    def inspect_sqlite_schema(self, db_rel_path: str) -> Dict[str, Any]:
        """Extracts table schema and indexes from an SQLite database."""
        db_path = self.safety.validate_safe_path(db_rel_path)
        if not db_path.exists():
            return {"success": False, "error": f"Database file not found: {db_rel_path}"}

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [{"name": row[0], "sql": row[1]} for row in cur.fetchall()]
            return {"success": True, "tables": tables}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()

    def execute_sqlite_query(self, db_rel_path: str, query: str, max_rows: int = 50) -> Dict[str, Any]:
        """Executes a read-only or safe query against a local SQLite database."""
        allowed, reason = self.safety.can_execute_command(query)
        if not allowed:
            return {"success": False, "error": reason}

        db_path = self.safety.validate_safe_path(db_rel_path)
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query)
            if query.strip().lower().startswith("select") or query.strip().lower().startswith("pragma"):
                rows = [dict(r) for r in cur.fetchmany(max_rows)]
                return {"success": True, "rows": rows, "count": len(rows)}
            else:
                conn.commit()
                return {"success": True, "rows_affected": cur.rowcount}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()

    # --- 6. API Testing ---

    def test_http_endpoint(self, url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
        """Tests an HTTP endpoint and returns status, headers, and parsed body."""
        try:
            req_headers = headers or {}
            data = None
            if body:
                data = json.dumps(body).encode("utf-8")
                req_headers["Content-Type"] = "application/json"

            req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_bytes = resp.read()
                resp_text = resp_bytes.decode("utf-8", errors="replace")
                try:
                    parsed_json = json.loads(resp_text)
                except Exception:
                    parsed_json = None

                return {
                    "success": 200 <= resp.status < 300,
                    "status_code": resp.status,
                    "body_raw": resp_text[:2000],
                    "json": parsed_json
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
