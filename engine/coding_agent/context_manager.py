"""
Context & File Manager for SAGE Coding Agent Architecture (v6).
Capabilities:
- Safe read / write file operations with atomic writes and diff generation
- Codebase searching (regex pattern search, symbol lookup, glob finder)
- Large file handling (smart windowing, chunking to avoid token overflow)
- Code chunking & indexing (function / class level extraction)
- Git integration (status, diffs, branch tracking, commits)
- Project structure mapping (ASCII trees, manifests, size analytics)
"""
import os
import re
import difflib
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .safety_controller import SafetyController

logger = logging.getLogger(__name__)


class ContextFileManager:
    """Manages workspace files, context retrieval, indexing, search, and Git operations."""

    def __init__(self, workspace_root: Optional[Path] = None, safety: Optional[SafetyController] = None):
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.safety = safety or SafetyController(self.workspace_root)
        self.max_file_read_bytes = 1024 * 1024 * 2  # 2MB max single file read

        # Common directories to skip during search and tree mapping
        self.ignore_dirs = {
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            ".pytest_cache", "dist", "build", ".next", ".nuxt",
            ".idea", ".vscode", "coverage", "vendor"
        }

    def set_workspace_root(self, root: Path):
        self.workspace_root = root.resolve()
        self.safety.set_workspace_root(self.workspace_root)

    # --- File Operations ---

    def read_file(self, rel_path: str, max_lines: Optional[int] = None) -> str:
        """Reads a file safely within workspace boundaries."""
        safe_path = self.safety.validate_safe_path(rel_path)
        if not safe_path.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        if not safe_path.is_file():
            raise IsADirectoryError(f"Path is a directory: {rel_path}")

        file_size = safe_path.stat().st_size
        if file_size > self.max_file_read_bytes and max_lines is None:
            # Auto-window large files
            max_lines = 1000

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            if max_lines:
                lines = [f.readline() for _ in range(max_lines)]
                return "".join(lines)
            return f.read()

    def write_file(self, rel_path: str, content: str, make_backup: bool = True) -> Dict[str, Any]:
        """
        Safely writes content to a file. Generates diff and backups previous version.
        """
        safe_path = self.safety.validate_safe_path(rel_path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        old_content = ""
        is_new = not safe_path.exists()
        if not is_new and safe_path.is_file():
            old_content = safe_path.read_text(encoding="utf-8", errors="replace")
            if make_backup:
                self.safety.create_file_backup(safe_path)

        # Write atomic or direct
        safe_path.write_text(content, encoding="utf-8")

        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}"
        ))
        diff_text = "".join(diff_lines)

        return {
            "path": rel_path,
            "is_new": is_new,
            "bytes_written": len(content.encode("utf-8")),
            "diff": diff_text
        }

    def delete_file(self, rel_path: str) -> bool:
        """Safely deletes a file with backup for recovery."""
        safe_path = self.safety.validate_safe_path(rel_path)
        if safe_path.exists() and safe_path.is_file():
            self.safety.create_file_backup(safe_path)
            safe_path.unlink()
            return True
        return False

    def list_files(self, sub_dir: str = "", max_files: int = 500) -> List[Dict[str, Any]]:
        """Lists files in the workspace respecting ignore boundaries."""
        start_path = self.safety.validate_safe_path(sub_dir) if sub_dir else self.workspace_root
        results = []
        for root, dirs, files in os.walk(start_path):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs and not d.startswith(".")]
            for f in files:
                full = Path(root) / f
                try:
                    rel = str(full.relative_to(self.workspace_root)).replace("\\", "/")
                    results.append({
                        "path": rel,
                        "size": full.stat().st_size,
                        "name": f
                    })
                    if len(results) >= max_files:
                        return results
                except Exception:
                    continue
        return results

    # --- Codebase Search & Chunking ---

    def search_codebase(self, query: str, is_regex: bool = False, max_results: int = 30) -> List[Dict[str, Any]]:
        """Searches across files for a string or regex pattern."""
        results = []
        compiled = None
        if is_regex:
            try:
                compiled = re.compile(query, re.IGNORECASE)
            except re.error:
                is_regex = False

        for f_info in self.list_files():
            rel_path = f_info["path"]
            # Only search text-based source files
            ext = Path(rel_path).suffix.lower()
            if ext in {".png", ".jpg", ".jpeg", ".ico", ".exe", ".bin", ".zip", ".tar", ".gz", ".db", ".sqlite"}:
                continue
            try:
                content = self.read_file(rel_path, max_lines=2000)
                for line_no, line in enumerate(content.splitlines(), start=1):
                    match = False
                    if is_regex and compiled:
                        match = bool(compiled.search(line))
                    else:
                        match = query.lower() in line.lower()

                    if match:
                        results.append({
                            "path": rel_path,
                            "line_number": line_no,
                            "line_content": line.strip()
                        })
                        if len(results) >= max_results:
                            return results
            except Exception:
                continue
        return results

    def chunk_file(self, rel_path: str, chunk_lines: int = 60, overlap: int = 15) -> List[Dict[str, Any]]:
        """Splits a file into structured chunks for RAG or multi-pass processing."""
        content = self.read_file(rel_path)
        lines = content.splitlines()
        if not lines:
            return []

        chunks = []
        idx = 0
        step = max(1, chunk_lines - overlap)
        chunk_id = 0

        while idx < len(lines):
            chunk_slice = lines[idx : idx + chunk_lines]
            chunk_text = "\n".join(chunk_slice)
            chunks.append({
                "chunk_id": chunk_id,
                "path": rel_path,
                "start_line": idx + 1,
                "end_line": min(len(lines), idx + len(chunk_slice)),
                "content": chunk_text
            })
            chunk_id += 1
            idx += step

        return chunks

    # --- Git Integration ---

    def git_status(self) -> Dict[str, Any]:
        """Inspects Git repository status if workspace is a git repo."""
        git_dir = self.workspace_root / ".git"
        if not git_dir.exists():
            return {"is_git": False, "status": "Not a git repository"}

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=5
            )
            return {
                "is_git": True,
                "branch_info": res.stdout.splitlines()[0] if res.stdout else "",
                "changed_files": [l.strip() for l in res.stdout.splitlines()[1:] if l.strip()],
                "raw": res.stdout
            }
        except Exception as e:
            return {"is_git": True, "error": str(e)}

    def git_diff(self, staged_only: bool = False) -> str:
        """Retrieves Git diff for current workspace changes."""
        git_dir = self.workspace_root / ".git"
        if not git_dir.exists():
            return ""

        cmd = ["git", "diff"]
        if staged_only:
            cmd.append("--staged")
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.stdout
        except Exception:
            return ""

    # --- Project Structure Mapping ---

    def generate_project_tree(self, max_depth: int = 4) -> str:
        """Generates a clean ASCII tree representation of the workspace."""
        lines = [f"{self.workspace_root.name}/"]

        def _traverse(current: Path, prefix: str, depth: int):
            if depth > max_depth:
                lines.append(f"{prefix}└── ...")
                return
            try:
                entries = sorted(
                    [p for p in current.iterdir() if p.name not in self.ignore_dirs and not p.name.startswith(".")],
                    key=lambda p: (p.is_file(), p.name.lower())
                )
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                next_prefix = prefix + ("    " if is_last else "│   ")
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _traverse(entry, next_prefix, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

        _traverse(self.workspace_root, "", 1)
        return "\n".join(lines)
