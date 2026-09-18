"""
Standardized Tool System for SAGE Autonomous Coding Agent.
Implements the full 24-tool specification from Section 11 with uniform structured return payloads:
{
    "success": bool,
    "tool": str,
    "exit_code": int,
    "stdout": str,
    "stderr": str,
    "duration": float
}
Categories:
- FILE TOOLS: read_file, write_file, edit_file, search_files, list_directory, create_directory, move_file, rename_file
- CODE TOOLS: run_python, run_javascript, run_tests, lint, format, build
- TERMINAL TOOLS: execute_command, install_dependency, run_script, inspect_process
- GIT TOOLS: git_status, git_diff, git_log, git_branch, git_checkout, git_commit, git_reset, git_push
- PROJECT TOOLS: inspect_project, detect_framework, detect_dependencies, search_codebase, find_symbol
"""
import os
import sys
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .safety_controller import SafetyController
from .sandbox_runner import SandboxRunner
from .project_analyzer import ProjectAnalyzer
from .codebase_indexer import CodebaseIndexer

logger = logging.getLogger(__name__)


class ToolSystem:
    """Consolidated, structured tool execution engine for coding sub-agents."""

    def __init__(
        self,
        workspace_root: Path,
        safety: SafetyController,
        sandbox: SandboxRunner,
        analyzer: ProjectAnalyzer,
        indexer: CodebaseIndexer
    ):
        self.workspace_root = workspace_root.resolve()
        self.safety = safety
        self.sandbox = sandbox
        self.analyzer = analyzer
        self.indexer = indexer

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.safety.set_workspace_root(self.workspace_root)
        self.sandbox.set_workspace_root(self.workspace_root)
        self.analyzer.set_workspace_root(self.workspace_root)
        self.indexer.set_workspace_root(self.workspace_root)

    # ── 1. FILE TOOLS ─────────────────────────────────────────────────

    def read_file(self, path: str, max_lines: Optional[int] = None) -> Dict[str, Any]:
        t0 = time.time()
        try:
            safe_p = self.safety.validate_safe_path(path)
            if not safe_p.exists():
                return self._result(False, "read_file", 1, "", f"File not found: {path}", t0)

            with open(safe_p, "r", encoding="utf-8", errors="replace") as f:
                if max_lines:
                    content = "".join(f.readline() for _ in range(max_lines))
                else:
                    content = f.read()
            return self._result(True, "read_file", 0, content, "", t0)
        except Exception as e:
            return self._result(False, "read_file", 1, "", str(e), t0)

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        t0 = time.time()
        try:
            safe_p = self.safety.validate_safe_path(path)
            safe_p.parent.mkdir(parents=True, exist_ok=True)
            self.safety.create_file_backup(safe_p)
            safe_p.write_text(content, encoding="utf-8")
            return self._result(True, "write_file", 0, f"Successfully wrote {len(content)} characters to {path}", "", t0)
        except Exception as e:
            return self._result(False, "write_file", 1, "", str(e), t0)

    def edit_file(self, path: str, old_snippet: str, new_snippet: str) -> Dict[str, Any]:
        t0 = time.time()
        try:
            safe_p = self.safety.validate_safe_path(path)
            if not safe_p.exists():
                return self._result(False, "edit_file", 1, "", f"File not found: {path}", t0)

            content = safe_p.read_text(encoding="utf-8", errors="replace")
            if old_snippet not in content:
                return self._result(False, "edit_file", 1, "", f"Target snippet not found in {path}", t0)

            self.safety.create_file_backup(safe_p)
            new_content = content.replace(old_snippet, new_snippet, 1)
            safe_p.write_text(new_content, encoding="utf-8")
            return self._result(True, "edit_file", 0, f"Successfully applied edit to {path}", "", t0)
        except Exception as e:
            return self._result(False, "edit_file", 1, "", str(e), t0)

    def search_files(self, pattern: str) -> Dict[str, Any]:
        t0 = time.time()
        try:
            matches = []
            for p in self.workspace_root.rglob(pattern):
                if not any(ig in p.parts for ig in (".git", ".venv", "node_modules", "__pycache__")):
                    rel = str(p.relative_to(self.workspace_root)).replace("\\", "/")
                    matches.append(rel)
            return self._result(True, "search_files", 0, "\n".join(matches), "", t0)
        except Exception as e:
            return self._result(False, "search_files", 1, "", str(e), t0)

    def list_directory(self, path: str = ".") -> Dict[str, Any]:
        t0 = time.time()
        try:
            safe_p = self.safety.validate_safe_path(path)
            items = []
            for entry in sorted(safe_p.iterdir()):
                if entry.name not in (".git", ".venv", "node_modules", "__pycache__") and not entry.name.startswith("."):
                    kind = "[DIR] " if entry.is_dir() else "[FILE]"
                    items.append(f"{kind} {entry.name}")
            return self._result(True, "list_directory", 0, "\n".join(items), "", t0)
        except Exception as e:
            return self._result(False, "list_directory", 1, "", str(e), t0)

    def create_directory(self, path: str) -> Dict[str, Any]:
        t0 = time.time()
        try:
            safe_p = self.safety.validate_safe_path(path)
            safe_p.mkdir(parents=True, exist_ok=True)
            return self._result(True, "create_directory", 0, f"Created directory: {path}", "", t0)
        except Exception as e:
            return self._result(False, "create_directory", 1, "", str(e), t0)

    def move_file(self, src: str, dst: str) -> Dict[str, Any]:
        t0 = time.time()
        try:
            safe_src = self.safety.validate_safe_path(src)
            safe_dst = self.safety.validate_safe_path(dst)
            safe_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(safe_src), str(safe_dst))
            return self._result(True, "move_file", 0, f"Moved {src} to {dst}", "", t0)
        except Exception as e:
            return self._result(False, "move_file", 1, "", str(e), t0)

    def rename_file(self, src: str, new_name: str) -> Dict[str, Any]:
        dst = str(Path(src).parent / new_name)
        return self.move_file(src, dst)

    # ── 2. CODE TOOLS ─────────────────────────────────────────────────

    def run_python(self, code_or_file: str, is_file: bool = False, timeout: float = 30.0) -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.run_python(code_or_file, is_file=is_file, timeout=timeout)
        return self._wrap_sandbox_res("run_python", res, t0)

    def run_javascript(self, code_or_file: str, is_file: bool = False, timeout: float = 30.0) -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.run_javascript(code_or_file, is_file=is_file, timeout=timeout)
        return self._wrap_sandbox_res("run_javascript", res, t0)

    def run_tests(self, target: Optional[str] = None, framework: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.time()
        cmd = [sys.executable, "-m", "unittest"]
        if target:
            cmd.append(target)
        else:
            cmd.extend(["discover", "-s", "tests"])
        res = self.sandbox.execute_subprocess(cmd, timeout=45.0)
        return self._wrap_sandbox_res("run_tests", res, t0)

    def lint(self, path: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.time()
        target = path or "."
        cmd = [sys.executable, "-m", "flake8", target, "--max-line-length=120"]
        res = self.sandbox.execute_subprocess(cmd, timeout=30.0)
        return self._wrap_sandbox_res("lint", res, t0)

    def format(self, path: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.time()
        target = path or "."
        cmd = [sys.executable, "-m", "black", target]
        res = self.sandbox.execute_subprocess(cmd, timeout=30.0)
        return self._wrap_sandbox_res("format", res, t0)

    def build(self, build_cmd: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.time()
        if build_cmd:
            cmd = build_cmd.split()
        elif (self.workspace_root / "package.json").exists():
            cmd = ["npm", "run", "build"]
        elif (self.workspace_root / "Cargo.toml").exists():
            cmd = ["cargo", "build"]
        else:
            return self._result(True, "build", 0, "No build step required for current project type", "", t0)

        res = self.sandbox.execute_subprocess(cmd, timeout=120.0)
        return self._wrap_sandbox_res("build", res, t0)

    # ── 3. TERMINAL TOOLS ─────────────────────────────────────────────

    def execute_command(self, command: str, timeout: float = 60.0) -> Dict[str, Any]:
        t0 = time.time()
        allowed, reason = self.safety.can_execute_command(command)
        if not allowed:
            return self._result(False, "execute_command", -1, "", reason, t0)

        # Split into list safely or run via shell
        res = self.sandbox.execute_subprocess(["powershell", "-Command", command] if os.name == "nt" else ["bash", "-c", command], timeout=timeout)
        return self._wrap_sandbox_res("execute_command", res, t0)

    def install_dependency(self, package: str, manager: str = "pip") -> Dict[str, Any]:
        t0 = time.time()
        if manager == "pip":
            cmd = [sys.executable, "-m", "pip", "install", package]
        elif manager == "npm":
            cmd = ["npm", "install", package]
        else:
            return self._result(False, "install_dependency", 1, "", f"Unsupported package manager: {manager}", t0)

        res = self.sandbox.execute_subprocess(cmd, timeout=120.0)
        return self._wrap_sandbox_res("install_dependency", res, t0)

    def run_script(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        t0 = time.time()
        ext = Path(script_path).suffix.lower()
        if ext == ".py":
            return self.run_python(script_path, is_file=True)
        elif ext in (".js", ".ts"):
            return self.run_javascript(script_path, is_file=True)
        else:
            cmd = [str((self.workspace_root / script_path).resolve())]
            if args:
                cmd.extend(args)
            res = self.sandbox.execute_subprocess(cmd)
            return self._wrap_sandbox_res("run_script", res, t0)

    def inspect_process(self, process_id_or_name: str) -> Dict[str, Any]:
        t0 = time.time()
        cmd = ["tasklist"] if os.name == "nt" else ["ps", "aux"]
        res = self.sandbox.execute_subprocess(cmd)
        return self._wrap_sandbox_res("inspect_process", res, t0)

    # ── 4. GIT TOOLS ──────────────────────────────────────────────────

    def git_status(self) -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.execute_subprocess(["git", "status", "--porcelain", "-b"])
        return self._wrap_sandbox_res("git_status", res, t0)

    def git_diff(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.time()
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        res = self.sandbox.execute_subprocess(cmd)
        return self._wrap_sandbox_res("git_diff", res, t0)

    def git_log(self, max_commits: int = 5) -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.execute_subprocess(["git", "log", f"-n{max_commits}", "--oneline"])
        return self._wrap_sandbox_res("git_log", res, t0)

    def git_branch(self) -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.execute_subprocess(["git", "branch", "-a"])
        return self._wrap_sandbox_res("git_branch", res, t0)

    def git_checkout(self, branch_or_file: str) -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.execute_subprocess(["git", "checkout", branch_or_file])
        return self._wrap_sandbox_res("git_checkout", res, t0)

    def git_commit(self, message: str) -> Dict[str, Any]:
        t0 = time.time()
        add_res = self.sandbox.execute_subprocess(["git", "add", "."])
        if not add_res["success"]:
            return self._wrap_sandbox_res("git_commit", add_res, t0)
        res = self.sandbox.execute_subprocess(["git", "commit", "-m", message])
        return self._wrap_sandbox_res("git_commit", res, t0)

    def git_reset(self, target: str = "HEAD") -> Dict[str, Any]:
        t0 = time.time()
        res = self.sandbox.execute_subprocess(["git", "reset", target])
        return self._wrap_sandbox_res("git_reset", res, t0)

    def git_push(self, remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        t0 = time.time()
        # Higher risk command check
        allowed, reason = self.safety.can_execute_command(f"git push {remote} {branch}")
        if not allowed:
            return self._result(False, "git_push", -1, "", reason, t0)
        res = self.sandbox.execute_subprocess(["git", "push", remote, branch])
        return self._wrap_sandbox_res("git_push", res, t0)

    # ── 5. PROJECT TOOLS ──────────────────────────────────────────────

    def inspect_project(self) -> Dict[str, Any]:
        t0 = time.time()
        proj_map = self.analyzer.analyze_project()
        return self._result(True, "inspect_project", 0, json.dumps(proj_map, indent=2), "", t0)

    def detect_framework(self) -> Dict[str, Any]:
        t0 = time.time()
        proj_map = self.analyzer.analyze_project()
        return self._result(True, "detect_framework", 0, ", ".join(proj_map.get("frameworks", [])) or "None", "", t0)

    def detect_dependencies(self) -> Dict[str, Any]:
        t0 = time.time()
        proj_map = self.analyzer.analyze_project()
        return self._result(True, "detect_dependencies", 0, ", ".join(proj_map.get("package_managers", [])) or "None", "", t0)

    def search_codebase(self, query: str) -> Dict[str, Any]:
        t0 = time.time()
        snippets = self.indexer.retrieve_relevant_snippets(query)
        return self._result(True, "search_codebase", 0, snippets, "", t0)

    def find_symbol(self, symbol_name: str) -> Dict[str, Any]:
        t0 = time.time()
        symbols = self.indexer.find_symbol(symbol_name)
        return self._result(True, "find_symbol", 0, json.dumps(symbols, indent=2), "", t0)

    # ── HELPERS ───────────────────────────────────────────────────────

    def _result(self, success: bool, tool: str, exit_code: int, stdout: str, stderr: str, t0: float) -> Dict[str, Any]:
        return {
            "success": success,
            "tool": tool,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration": round(time.time() - t0, 3)
        }

    def _wrap_sandbox_res(self, tool_name: str, res: Dict[str, Any], t0: float) -> Dict[str, Any]:
        return {
            "success": res.get("success", False),
            "tool": tool_name,
            "exit_code": res.get("exit_code", 0 if res.get("success") else 1),
            "stdout": res.get("stdout", ""),
            "stderr": res.get("stderr", ""),
            "duration": round(time.time() - t0, 3)
        }
