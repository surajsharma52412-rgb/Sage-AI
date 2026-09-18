"""
Project Workspace for Sage Multi-Agentic AI Architecture.
Manages repository navigation, file inspection, and secure file operations
with strict path-traversal sandboxing.
"""
import os
import fnmatch
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import WORKSPACE_ROOT, BASE_DIR

logger = logging.getLogger(__name__)


class ProjectWorkspace:
    """Safely inspects and modifies project files within an authorized root."""

    def __init__(self, root_path: Optional[Path] = None):
        self.root_path = Path(root_path or WORKSPACE_ROOT).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def resolve_safe_path(self, relative_path: str) -> Path:
        """
        Resolves a path relative to workspace root and blocks directory traversal.
        Raises PermissionError if path attempts to escape the root.
        """
        # Strip leading slashes to keep it relative
        clean_rel = relative_path.lstrip("/\\")
        target = (self.root_path / clean_rel).resolve()
        try:
            target.relative_to(self.root_path)
        except ValueError:
            raise PermissionError(f"Access denied: path '{relative_path}' is outside workspace root.")
        return target

    def read_file(self, relative_path: str, max_bytes: int = 1_000_000) -> str:
        """Safely reads content of a workspace file."""
        target = self.resolve_safe_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if not target.is_file():
            raise IsADirectoryError(f"Target is a directory: {relative_path}")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)

    def write_file(self, relative_path: str, content: str) -> Dict[str, Any]:
        """Safely writes or overwrites a file in the workspace."""
        target = self.resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        is_new = not target.exists()
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "path": str(relative_path),
            "absolute_path": str(target),
            "bytes_written": len(content.encode("utf-8")),
            "is_new": is_new
        }

    def delete_file(self, relative_path: str) -> bool:
        """Safely removes a file."""
        target = self.resolve_safe_path(relative_path)
        if target.exists() and target.is_file():
            target.unlink()
            return True
        return False

    def list_tree(self, max_depth: int = 3, exclude_patterns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Scans workspace directory hierarchy up to max_depth."""
        excludes = exclude_patterns or [
            ".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode"
        ]
        items = []

        for root, dirs, files in os.walk(self.root_path):
            rel_dir = Path(root).relative_to(self.root_path)
            depth = len(rel_dir.parts)
            if depth > max_depth:
                dirs.clear()
                continue

            # Filter out ignored directories in-place
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pat) for pat in excludes)]

            for f in files:
                if any(fnmatch.fnmatch(f, pat) for pat in excludes):
                    continue
                file_rel = (rel_dir / f).as_posix()
                if file_rel.startswith("./"):
                    file_rel = file_rel[2:]
                full_path = Path(root) / f
                try:
                    size = full_path.stat().st_size
                except Exception:
                    size = 0
                items.append({
                    "path": file_rel,
                    "size": size,
                    "is_dir": False
                })

        return items

    def find_files(self, pattern: str) -> List[str]:
        """Finds files matching wildcard pattern."""
        matches = []
        for item in self.list_tree(max_depth=5):
            if fnmatch.fnmatch(item["path"], pattern) or fnmatch.fnmatch(Path(item["path"]).name, pattern):
                matches.append(item["path"])
        return matches

    def git_status(self) -> Dict[str, Any]:
        """Returns Git repository status if workspace is a git repository."""
        git_dir = self.root_path / ".git"
        if not git_dir.exists():
            return {"is_git": False, "status": "Not a git repository"}

        try:
            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.root_path),
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            return {
                "is_git": True,
                "clean": len(res.stdout.strip()) == 0,
                "status": res.stdout.strip()
            }
        except Exception as e:
            return {"is_git": True, "error": str(e)}


_project_workspace_instance: Optional[ProjectWorkspace] = None

def get_project_workspace() -> ProjectWorkspace:
    global _project_workspace_instance
    if _project_workspace_instance is None:
        _project_workspace_instance = ProjectWorkspace()
    return _project_workspace_instance
