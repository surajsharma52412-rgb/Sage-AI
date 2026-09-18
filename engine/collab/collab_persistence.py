"""
Collaborative Persistence Layer for SAGE Collaborative IDE.

Provides SQLite-backed storage for:
    - CRDT document snapshots (binary serialized state)
    - File version history with full text and diffs
    - Auto-save and manual Ctrl+S checkpointing
    - Version rollback with cross-peer broadcast
"""

import json
import time
import sqlite3
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class CollabPersistence:
    """
    SQLite-backed persistence for collaborative workspace state.
    
    Stores version history per file, enabling:
    - Ctrl+S checkpoint snapshots
    - Auto-save at configurable intervals
    - Version timeline browsing
    - Rollback to any previous version
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from config import DATA_DIR
            db_path = DATA_DIR / "collab_state.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        """Creates tables if they don't exist."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS workspace_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workspace_id TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        crdt_snapshot TEXT,
                        content_text TEXT,
                        saved_by TEXT NOT NULL DEFAULT 'System',
                        saved_at REAL NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        message TEXT DEFAULT '',
                        UNIQUE(workspace_id, file_path, version)
                    );

                    CREATE TABLE IF NOT EXISTS file_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workspace_id TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        version_num INTEGER NOT NULL,
                        content_text TEXT NOT NULL,
                        diff_summary TEXT DEFAULT '',
                        saved_by TEXT NOT NULL DEFAULT 'System',
                        saved_at REAL NOT NULL,
                        is_auto_save INTEGER DEFAULT 0,
                        message TEXT DEFAULT ''
                    );

                    CREATE INDEX IF NOT EXISTS idx_versions_file
                        ON file_versions(workspace_id, file_path, version_num);

                    CREATE INDEX IF NOT EXISTS idx_snapshots_file
                        ON workspace_snapshots(workspace_id, file_path, version);

                    CREATE TABLE IF NOT EXISTS workspace_meta (
                        workspace_id TEXT PRIMARY KEY,
                        workspace_path TEXT NOT NULL,
                        last_active REAL NOT NULL,
                        owner_name TEXT DEFAULT 'Host'
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    def save_version(
        self,
        workspace_id: str,
        file_path: str,
        content: str,
        saved_by: str = "System",
        crdt_snapshot: Optional[dict] = None,
        is_auto_save: bool = False,
        message: str = "",
    ) -> int:
        """
        Saves a new version of a file.
        
        Returns the new version number.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                # Get current max version
                row = conn.execute(
                    "SELECT COALESCE(MAX(version_num), 0) as max_v "
                    "FROM file_versions WHERE workspace_id=? AND file_path=?",
                    (workspace_id, file_path)
                ).fetchone()
                new_version = row["max_v"] + 1

                # Compute diff summary (first 80 chars of change)
                prev_row = conn.execute(
                    "SELECT content_text FROM file_versions "
                    "WHERE workspace_id=? AND file_path=? AND version_num=? ",
                    (workspace_id, file_path, new_version - 1)
                ).fetchone()

                diff_summary = ""
                if prev_row:
                    prev_content = prev_row["content_text"]
                    if content != prev_content:
                        # Simple diff: count changed lines
                        prev_lines = prev_content.splitlines()
                        new_lines = content.splitlines()
                        added = max(0, len(new_lines) - len(prev_lines))
                        removed = max(0, len(prev_lines) - len(new_lines))
                        diff_summary = f"+{added} -{removed} lines"
                    else:
                        diff_summary = "No changes"

                # Save version
                conn.execute(
                    "INSERT INTO file_versions "
                    "(workspace_id, file_path, version_num, content_text, diff_summary, "
                    "saved_by, saved_at, is_auto_save, message) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (workspace_id, file_path, new_version, content,
                     diff_summary, saved_by, time.time(), int(is_auto_save), message)
                )

                # Save CRDT snapshot if provided
                if crdt_snapshot:
                    snapshot_json = json.dumps(crdt_snapshot)
                    conn.execute(
                        "INSERT OR REPLACE INTO workspace_snapshots "
                        "(workspace_id, file_path, crdt_snapshot, content_text, "
                        "saved_by, saved_at, version, message) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (workspace_id, file_path, snapshot_json, content,
                         saved_by, time.time(), new_version, message)
                    )

                conn.commit()
                return new_version
            finally:
                conn.close()

    def get_file_versions(
        self,
        workspace_id: str,
        file_path: str,
        limit: int = 50,
    ) -> List[dict]:
        """
        Returns the version history for a file, most recent first.
        
        Each entry includes: version_num, saved_by, saved_at, diff_summary,
        is_auto_save, message, preview (first 100 chars of content).
        """
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT version_num, saved_by, saved_at, diff_summary, "
                    "is_auto_save, message, SUBSTR(content_text, 1, 100) as preview "
                    "FROM file_versions "
                    "WHERE workspace_id=? AND file_path=? "
                    "ORDER BY version_num DESC LIMIT ?",
                    (workspace_id, file_path, limit)
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_version_content(
        self,
        workspace_id: str,
        file_path: str,
        version_num: int,
    ) -> Optional[str]:
        """Returns the full content of a specific version."""
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT content_text FROM file_versions "
                    "WHERE workspace_id=? AND file_path=? AND version_num=?",
                    (workspace_id, file_path, version_num)
                ).fetchone()
                return row["content_text"] if row else None
            finally:
                conn.close()

    def get_crdt_snapshot(
        self,
        workspace_id: str,
        file_path: str,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        """Returns a CRDT snapshot for a file (latest or specific version)."""
        with self._lock:
            conn = self._get_connection()
            try:
                if version:
                    row = conn.execute(
                        "SELECT crdt_snapshot FROM workspace_snapshots "
                        "WHERE workspace_id=? AND file_path=? AND version=?",
                        (workspace_id, file_path, version)
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT crdt_snapshot FROM workspace_snapshots "
                        "WHERE workspace_id=? AND file_path=? "
                        "ORDER BY version DESC LIMIT 1",
                        (workspace_id, file_path)
                    ).fetchone()
                
                if row and row["crdt_snapshot"]:
                    return json.loads(row["crdt_snapshot"])
                return None
            finally:
                conn.close()

    def write_to_disk(self, workspace_root: Path, file_path: str, content: str) -> bool:
        """Writes file content to disk (the actual file in the workspace)."""
        try:
            full_path = workspace_root / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to write {file_path} to disk: {e}")
            return False

    def save_workspace_meta(self, workspace_id: str, workspace_path: str, owner_name: str = "Host"):
        """Stores workspace metadata."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO workspace_meta "
                    "(workspace_id, workspace_path, last_active, owner_name) "
                    "VALUES (?, ?, ?, ?)",
                    (workspace_id, workspace_path, time.time(), owner_name)
                )
                conn.commit()
            finally:
                conn.close()

    def get_latest_version_num(self, workspace_id: str, file_path: str) -> int:
        """Returns the latest version number for a file, or 0 if no versions exist."""
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT COALESCE(MAX(version_num), 0) as max_v "
                    "FROM file_versions WHERE workspace_id=? AND file_path=?",
                    (workspace_id, file_path)
                ).fetchone()
                return row["max_v"]
            finally:
                conn.close()
