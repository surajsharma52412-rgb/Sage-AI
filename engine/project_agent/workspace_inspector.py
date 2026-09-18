"""
Workspace Inspector for Autonomous Project Coding Agent.
Safely scans directories, respects ignore rules, prevents path traversal,
and produces project manifests for LLM reasoning.
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

IGNORED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".tox", ".idea", ".vscode", "dist", "build"
}

BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".zip", ".tar", ".gz",
    ".7z", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".mp4",
    ".mp3", ".wav", ".pyc", ".pyd", ".db", ".sqlite", ".sqlite3"
}


class WorkspaceSecurityError(Exception):
    """Raised when a path escapes the project workspace boundaries."""
    pass


class WorkspaceInspector:
    """Safe workspace scanner and file manifest generator."""

    def __init__(self, workspace_root: Path):
        self.root = Path(workspace_root).resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise ValueError(f"Workspace root directory does not exist: {self.root}")

    def resolve_safe_path(self, relative_path: str) -> Path:
        """
        Safely resolves a path relative to workspace root, preventing directory traversal.
        """
        clean_rel = os.path.normpath(relative_path).lstrip("/\\")
        resolved = (self.root / clean_rel).resolve()

        # Guard against traversal attack
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise WorkspaceSecurityError(f"Security Violation: Path escapes workspace root: {relative_path}")

        return resolved

    def _parse_gitignore(self) -> Set[str]:
        """Parses basic .gitignore patterns if available."""
        patterns = set(IGNORED_DIRS)
        gitignore_path = self.root / ".gitignore"
        if gitignore_path.is_file():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            clean_line = line.rstrip("/")
                            patterns.add(clean_line)
            except Exception:
                pass
        return patterns

    def scan_manifest(self, max_files: int = 400) -> List[Dict[str, Any]]:
        """Scans workspace and returns a list of relative file entries."""
        manifest = []
        ignore_patterns = self._parse_gitignore()

        for dirpath, dirnames, filenames in os.walk(self.root):
            # Prune ignored directories in place
            dirnames[:] = [
                d for d in dirnames
                if d not in ignore_patterns and not d.startswith(".")
            ]

            rel_dir = os.path.relpath(dirpath, self.root)
            if rel_dir == ".":
                rel_dir = ""

            for fname in sorted(filenames):
                if fname.startswith(".") or fname in ignore_patterns:
                    continue

                ext = os.path.splitext(fname)[1].lower()
                is_binary = ext in BINARY_EXTENSIONS

                full_path = Path(dirpath) / fname
                rel_path = os.path.normpath(os.path.join(rel_dir, fname)).replace("\\", "/")

                try:
                    file_size = full_path.stat().st_size
                except Exception:
                    file_size = 0

                manifest.append({
                    "path": rel_path,
                    "size": file_size,
                    "is_binary": is_binary,
                })

                if len(manifest) >= max_files:
                    break

            if len(manifest) >= max_files:
                break

        return manifest

    def get_tree_view(self) -> str:
        """Generates a visual ASCII tree of the workspace files."""
        lines = [f"{self.root.name}/"]
        manifest = self.scan_manifest(max_files=150)
        
        # Group by path depth
        for item in manifest:
            parts = item["path"].split("/")
            indent = "  " * len(parts)
            prefix = "[BIN] " if item["is_binary"] else ""
            lines.append(f"{indent}|-- {prefix}{parts[-1]} ({item['size']} B)")

        if not manifest:
            lines.append("  (Empty workspace)")

        return "\n".join(lines)

    def read_file(self, relative_path: str, max_bytes: int = 50000) -> Optional[str]:
        """Safely reads the content of a text file inside the workspace."""
        path = self.resolve_safe_path(relative_path)
        if not path.is_file():
            return None

        ext = path.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return f"[Binary file: {path.name}]"

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(max_bytes)
        except Exception as e:
            return f"[Error reading file: {str(e)}]"
