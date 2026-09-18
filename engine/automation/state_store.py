"""
State Persistence Store for SAGE Autonomous Automation Agent.
Stores automation runs, plans, steps, status transitions, tool outputs,
and audit logs in SQLite to ensure atomic state tracking and safe resumption.
"""
import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AutomationStateStore:
    """Manages SQLite storage for autonomous automation workflows."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            cache_dir = Path(".sage_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = cache_dir / "automation_state.db"
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
                CREATE TABLE IF NOT EXISTS automation_runs (
                    run_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    done_criteria TEXT NOT NULL,
                    status TEXT NOT NULL, -- PENDING, RUNNING, COMPLETED, FAILED, ABORTED
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified_outcome TEXT,
                    verification_summary TEXT
                );

                CREATE TABLE IF NOT EXISTS automation_steps (
                    run_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    step_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_args TEXT NOT NULL,
                    is_risky INTEGER DEFAULT 0,
                    is_idempotent INTEGER DEFAULT 1,
                    risk_reason TEXT,
                    expected_outcome TEXT,
                    status TEXT NOT NULL, -- PENDING, CONFIRMING, RUNNING, DONE, FAILED, SKIPPED
                    result_payload TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    started_at TEXT,
                    finished_at TEXT,
                    PRIMARY KEY (run_id, step_index),
                    FOREIGN KEY (run_id) REFERENCES automation_runs(run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS automation_audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT
                );
            """)

    def create_run(self, run_id: str, goal: str, done_criteria: str) -> Dict[str, Any]:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO automation_runs (run_id, goal, done_criteria, status, created_at, updated_at)
                VALUES (?, ?, ?, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (run_id, goal, done_criteria)
            )
        return {
            "run_id": run_id,
            "goal": goal,
            "done_criteria": done_criteria,
            "status": "PENDING"
        }

    def save_steps(self, run_id: str, steps: List[Dict[str, Any]]):
        with self._conn() as conn:
            for idx, s in enumerate(steps):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO automation_steps (
                        run_id, step_index, step_id, name, tool_name, tool_args,
                        is_risky, is_idempotent, risk_reason, expected_outcome,
                        status, retry_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        idx,
                        s.get("step_id", f"step_{idx+1}"),
                        s.get("name", f"Step {idx+1}"),
                        s.get("tool_name", ""),
                        json.dumps(s.get("tool_args", {})),
                        1 if s.get("is_risky") else 0,
                        1 if s.get("is_idempotent", True) else 0,
                        s.get("risk_reason", ""),
                        s.get("expected_outcome", ""),
                        s.get("status", "PENDING"),
                        s.get("retry_count", 0)
                    )
                )

    def update_run_status(self, run_id: str, status: str, verified_outcome: Optional[str] = None, verification_summary: Optional[str] = None):
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE automation_runs
                SET status = ?, verified_outcome = COALESCE(?, verified_outcome),
                    verification_summary = COALESCE(?, verification_summary),
                    updated_at = CURRENT_TIMESTAMP
                WHERE run_id = ?
                """,
                (status, verified_outcome, verification_summary, run_id)
            )

    def update_step_status(
        self,
        run_id: str,
        step_index: int,
        status: str,
        result_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        increment_retry: bool = False
    ):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            extra_set = ""
            params: List[Any] = [status]

            if result_payload is not None:
                extra_set += ", result_payload = ?"
                params.append(json.dumps(result_payload))
            if error_message is not None:
                extra_set += ", error_message = ?"
                params.append(error_message)
            if status == "RUNNING":
                extra_set += ", started_at = ?"
                params.append(now)
            elif status in ("DONE", "FAILED", "SKIPPED"):
                extra_set += ", finished_at = ?"
                params.append(now)
            if increment_retry:
                extra_set += ", retry_count = retry_count + 1"

            params.extend([run_id, step_index])
            conn.execute(
                f"""
                UPDATE automation_steps
                SET status = ? {extra_set}
                WHERE run_id = ? AND step_index = ?
                """,
                params
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM automation_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            run = dict(row)
            step_rows = conn.execute(
                "SELECT * FROM automation_steps WHERE run_id = ? ORDER BY step_index ASC",
                (run_id,)
            ).fetchall()
            steps = []
            for s in step_rows:
                s_dict = dict(s)
                s_dict["tool_args"] = json.loads(s_dict["tool_args"]) if s_dict.get("tool_args") else {}
                s_dict["result_payload"] = json.loads(s_dict["result_payload"]) if s_dict.get("result_payload") else None
                s_dict["is_risky"] = bool(s_dict.get("is_risky"))
                s_dict["is_idempotent"] = bool(s_dict.get("is_idempotent"))
                steps.append(s_dict)
            run["steps"] = steps
            return run

    def get_pending_steps(self, run_id: str) -> List[Dict[str, Any]]:
        run = self.get_run(run_id)
        if not run:
            return []
        return [s for s in run.get("steps", []) if s.get("status") not in ("DONE", "SKIPPED")]

    def record_audit(self, run_id: str, action_type: str, target: str, decision: str, status: str, details: str):
        now = datetime.now().strftime("%H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO automation_audit_events (run_id, timestamp, action_type, target, decision, status, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, now, action_type, target, decision, status, details)
            )

    def get_audit_history(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            if run_id:
                rows = conn.execute(
                    "SELECT * FROM automation_audit_events WHERE run_id = ? ORDER BY event_id DESC",
                    (run_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM automation_audit_events ORDER BY event_id DESC LIMIT 100"
                ).fetchall()
            return [dict(r) for r in rows]
