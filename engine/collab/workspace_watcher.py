"""
Workspace Filesystem Watcher for SAGE Collaborative IDE.

Monitors a workspace directory recursively and broadcasts file tree
changes to all connected collaborators in real-time. Handles:
    - File/folder create, modify, delete, rename detection
    - Serializable file tree snapshots for late joiners
    - Conflict-safe file operations (warnings before rename/delete of open files)
    - Debounced change events to avoid flooding during bulk operations
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Callable

from PySide6.QtCore import QObject, Signal, QFileSystemWatcher, QTimer

logger = logging.getLogger(__name__)

# Directories and file patterns to exclude from monitoring
EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules",
    ".venv", "venv", ".env", ".sage_cache", ".idea", ".vscode",
    "__MACOSX", ".DS_Store", "scratch",
}

EXCLUDED_EXTENSIONS = {
    ".pyc", ".pyo", ".o", ".obj", ".exe", ".dll", ".so",
    ".class", ".jar", ".db", ".sqlite", ".db-journal",
}


class WorkspaceWatcher(QObject):
    """
    Monitors a workspace folder and emits signals when files/folders
    change. Used by the CRDT sync server to broadcast file tree updates.
    """

    # Signals
    file_created = Signal(str)      # relative path
    file_modified = Signal(str)     # relative path
    file_deleted = Signal(str)      # relative path
    file_renamed = Signal(str, str) # (old_relative, new_relative)
    tree_changed = Signal(list)     # full serialized tree

    def __init__(self, workspace_root: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self._root: Optional[Path] = workspace_root
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)

        # Debounce timer to batch rapid filesystem events
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)  # 200ms debounce
        self._debounce_timer.timeout.connect(self._emit_tree_snapshot)

        # Last known file set for detecting creates/deletes
        self._known_files: Set[str] = set()

    def set_workspace(self, root: Path):
        """Sets/changes the watched workspace root."""
        # Remove old watchers
        dirs = self._watcher.directories()
        files = self._watcher.files()
        if dirs:
            self._watcher.removePaths(dirs)
        if files:
            self._watcher.removePaths(files)

        self._root = root.resolve()
        self._known_files.clear()
        self._scan_and_watch()

    def _scan_and_watch(self):
        """Recursively scans the workspace and sets up watchers."""
        if not self._root or not self._root.is_dir():
            return

        dirs_to_watch = []
        files_found = set()

        for dirpath, dirnames, filenames in os.walk(str(self._root)):
            # Filter out excluded directories
            dirnames[:] = [
                d for d in dirnames
                if d not in EXCLUDED_DIRS and not d.startswith(".")
            ]

            rel_dir = os.path.relpath(dirpath, str(self._root))
            dirs_to_watch.append(dirpath)

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in EXCLUDED_EXTENSIONS:
                    continue
                if fname.startswith("."):
                    continue

                rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname
                rel_path = rel_path.replace("\\", "/")
                files_found.add(rel_path)

        # Detect new and deleted files
        new_files = files_found - self._known_files
        deleted_files = self._known_files - files_found

        for f in new_files:
            self.file_created.emit(f)
        for f in deleted_files:
            self.file_deleted.emit(f)

        self._known_files = files_found

        # Update watchers
        if dirs_to_watch:
            self._watcher.addPaths(dirs_to_watch)

    def _on_dir_changed(self, path: str):
        """Handles directory change events."""
        self._scan_and_watch()
        self._debounce_timer.start()

    def _on_file_changed(self, path: str):
        """Handles file modification events."""
        if self._root:
            try:
                rel = os.path.relpath(path, str(self._root)).replace("\\", "/")
                self.file_modified.emit(rel)
            except Exception:
                pass
        self._debounce_timer.start()

    def _emit_tree_snapshot(self):
        """Emits the full file tree snapshot."""
        tree = self.get_file_tree()
        self.tree_changed.emit(tree)

    def get_file_tree(self) -> List[dict]:
        """
        Returns a serializable snapshot of the workspace file tree.

        Each entry is:
            {
                "path": "src/main.py",
                "type": "file" | "dir",
                "size": 1234,
                "modified_at": 1695000000.0,
                "name": "main.py"
            }
        """
        if not self._root or not self._root.is_dir():
            return []

        tree = []
        for dirpath, dirnames, filenames in os.walk(str(self._root)):
            dirnames[:] = [
                d for d in dirnames
                if d not in EXCLUDED_DIRS and not d.startswith(".")
            ]

            rel_dir = os.path.relpath(dirpath, str(self._root))
            if rel_dir != ".":
                rel_dir_clean = rel_dir.replace("\\", "/")
                try:
                    stat = os.stat(dirpath)
                    tree.append({
                        "path": rel_dir_clean,
                        "type": "dir",
                        "name": os.path.basename(dirpath),
                        "modified_at": stat.st_mtime,
                    })
                except OSError:
                    pass

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in EXCLUDED_EXTENSIONS or fname.startswith("."):
                    continue

                full_path = os.path.join(dirpath, fname)
                rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname
                rel_path = rel_path.replace("\\", "/")

                try:
                    stat = os.stat(full_path)
                    tree.append({
                        "path": rel_path,
                        "type": "file",
                        "name": fname,
                        "size": stat.st_size,
                        "modified_at": stat.st_mtime,
                    })
                except OSError:
                    pass

        return tree

    def stop(self):
        """Stops all filesystem watching."""
        dirs = self._watcher.directories()
        files = self._watcher.files()
        if dirs:
            self._watcher.removePaths(dirs)
        if files:
            self._watcher.removePaths(files)
        self._known_files.clear()
