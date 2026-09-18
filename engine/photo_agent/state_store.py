"""
State Persistence Store for SAGE Autonomous Photo & Media Agent.
Stores photo library runs, analyzed items, status, tags, and a separate log
of all destructive/irreversible actions taken with original path, action, and timestamp.
"""
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PhotoStateStore:
    """Manages SQLite storage for photo library analysis, organization, and audit trails."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            cache_dir = Path(".sage_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = cache_dir / "photo_state.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    @contextmanager
    def _conn(self):
        """Context manager guaranteeing connection closure to avoid Windows SQLite file locks."""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS photo_runs (
                    run_id TEXT PRIMARY KEY,
                    library_path TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    done_criteria TEXT NOT NULL,
                    status TEXT NOT NULL, -- PENDING, RUNNING, COMPLETED, FAILED, ABORTED
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    summary TEXT
                );

                CREATE TABLE IF NOT EXISTS photo_items (
                    run_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    format TEXT,
                    width INTEGER,
                    height INTEGER,
                    sha256 TEXT,
                    phash TEXT,
                    exif_data TEXT, -- JSON
                    tags TEXT,      -- JSON list
                    status TEXT NOT NULL, -- PENDING, PROCESSED, FLAGGED_REVIEW, SKIPPED, CORRUPT
                    action_taken TEXT,
                    destination_path TEXT,
                    PRIMARY KEY (run_id, file_path),
                    FOREIGN KEY (run_id) REFERENCES photo_runs(run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS photo_destructive_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    action_type TEXT NOT NULL, -- DELETE, OVERWRITE, MOVE, MERGE
                    destination_path TEXT,
                    details TEXT
                );
            """)

    def create_run(self, run_id: str, library_path: str, goal: str, done_criteria: str) -> Dict[str, Any]:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO photo_runs (run_id, library_path, goal, done_criteria, status)
                VALUES (?, ?, ?, ?, 'PENDING')
                """,
                (run_id, library_path, goal, done_criteria)
            )
        return {
            "run_id": run_id,
            "library_path": library_path,
            "goal": goal,
            "done_criteria": done_criteria,
            "status": "PENDING"
        }

    def register_items(self, run_id: str, items: List[Dict[str, Any]]):
        with self._conn() as conn:
            for it in items:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO photo_items (
                        run_id, file_path, file_name, file_size, format,
                        width, height, sha256, phash, exif_data, tags, status,
                        action_taken, destination_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        it.get("file_path"),
                        it.get("file_name"),
                        it.get("file_size", 0),
                        it.get("format", ""),
                        it.get("width", 0),
                        it.get("height", 0),
                        it.get("sha256", ""),
                        it.get("phash", ""),
                        json.dumps(it.get("exif_data", {})),
                        json.dumps(it.get("tags", [])),
                        it.get("status", "PENDING"),
                        it.get("action_taken", ""),
                        it.get("destination_path", "")
                    )
                )

    def update_item(
        self,
        run_id: str,
        file_path: str,
        status: str,
        action_taken: Optional[str] = None,
        destination_path: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        with self._conn() as conn:
            updates = ["status = ?"]
            params: List[Any] = [status]
            if action_taken is not None:
                updates.append("action_taken = ?")
                params.append(action_taken)
            if destination_path is not None:
                updates.append("destination_path = ?")
                params.append(destination_path)
            if tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(tags))
            params.extend([run_id, file_path])
            conn.execute(
                f"UPDATE photo_items SET {', '.join(updates)} WHERE run_id = ? AND file_path = ?",
                params
            )

    def log_destructive_action(
        self,
        run_id: str,
        original_path: str,
        action_type: str,
        destination_path: Optional[str] = None,
        details: str = ""
    ):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO photo_destructive_actions (
                    run_id, timestamp, original_path, action_type, destination_path, details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, now, original_path, action_type, destination_path or "", details)
            )

    def get_destructive_actions(self, run_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM photo_destructive_actions WHERE run_id = ? ORDER BY action_id ASC",
                (run_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM photo_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            run = dict(row)
            items = conn.execute("SELECT * FROM photo_items WHERE run_id = ?", (run_id,)).fetchall()
            parsed_items = []
            for it in items:
                d = dict(it)
                d["exif_data"] = json.loads(d["exif_data"]) if d.get("exif_data") else {}
                d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
                parsed_items.append(d)
            run["items"] = parsed_items
            run["destructive_actions"] = self.get_destructive_actions(run_id)
            return run

    def get_pending_items(self, run_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM photo_items WHERE run_id = ? AND status = 'PENDING'",
                (run_id,)
            ).fetchall()
            parsed = []
            for r in rows:
                d = dict(r)
                d["exif_data"] = json.loads(d["exif_data"]) if d.get("exif_data") else {}
                d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
                parsed.append(d)
            return parsed

    def update_run_status(self, run_id: str, status: str, summary: Optional[str] = None):
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE photo_runs
                SET status = ?, summary = COALESCE(?, summary), updated_at = CURRENT_TIMESTAMP
                WHERE run_id = ?
                """,
                (status, summary, run_id)
            )
