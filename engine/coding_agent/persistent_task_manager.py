"""
Persistent Task Manager & DAG for SAGE Autonomous Coding Agent.
Provides:
- Granular task DAG creation (task_id, dependencies, priority, status, assigned_agent)
- Topological staging (independent tasks run in parallel, dependent tasks wait)
- SQLite state persistence: resumes long-running development tasks across restarts
- Real-time progress updates & structured state emission
"""
import json
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class PersistentTaskManager:
    """Manages DAG task planning, dependency resolution, and resumable session state."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path.home() / ".sage" / "coding_tasks"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "tasks.db")
        else:
            self.db_path = str(db_path)
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.active_session_id: Optional[str] = None
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coding_sessions (
                    session_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_phase TEXT,
                    progress_pct INTEGER DEFAULT 0,
                    project_root TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coding_tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER DEFAULT 50,
                    dependencies_json TEXT,
                    required_files_json TEXT,
                    expected_output TEXT,
                    validation_criteria TEXT,
                    retry_count INTEGER DEFAULT 0,
                    error_state TEXT,
                    result_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES coding_sessions(session_id)
                )
            """)

    def create_plan_dag(
        self,
        session_id: str,
        goal: str,
        project_root: str,
        structured_tasks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Initializes a task DAG for a software engineering goal.
        If structured_tasks not provided, generates default full-lifecycle tasks.
        """
        self.active_session_id = session_id
        self.tasks.clear()

        # Create session record
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO coding_sessions (session_id, goal, status, current_phase, progress_pct, project_root)
                   VALUES (?, ?, 'running', 'planning', 0, ?)""",
                (session_id, goal, project_root)
            )

        if not structured_tasks:
            structured_tasks = self._generate_default_tasks(goal)

        with self._conn() as conn:
            for t in structured_tasks:
                tid = t["task_id"]
                self.tasks[tid] = t
                conn.execute(
                    """INSERT OR REPLACE INTO coding_tasks
                       (task_id, session_id, description, role, status, priority,
                        dependencies_json, required_files_json, expected_output,
                        validation_criteria, retry_count, error_state)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tid,
                        session_id,
                        t["description"],
                        t["role"],
                        t.get("status", "pending"),
                        t.get("priority", 50),
                        json.dumps(t.get("dependencies", [])),
                        json.dumps(t.get("required_files", [])),
                        t.get("expected_output", ""),
                        t.get("validation_criteria", ""),
                        t.get("retry_count", 0),
                        t.get("error_state", "")
                    )
                )

        stages = self.compute_execution_stages()
        return {
            "session_id": session_id,
            "goal": goal,
            "total_tasks": len(self.tasks),
            "stages": stages,
            "tasks": self.tasks
        }

    def compute_execution_stages(self) -> List[List[str]]:
        """
        Topological sort: groups tasks into parallel execution stages.
        Tasks in Stage N only depend on tasks in Stages < N.
        """
        completed: Set[str] = set()
        remaining = dict(self.tasks)
        stages = []

        while remaining:
            ready = [
                tid for tid, t in remaining.items()
                if all(dep in completed for dep in t.get("dependencies", []))
            ]

            if not ready:
                # Cycle break fallback
                ready = [max(remaining.keys(), key=lambda k: remaining[k].get("priority", 0))]

            stages.append(ready)
            for tid in ready:
                completed.add(tid)
                del remaining[tid]

        return stages

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_msg: Optional[str] = None
    ):
        """Updates task state in memory and SQLite."""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            if error_msg:
                self.tasks[task_id]["error_state"] = error_msg
            if result:
                self.tasks[task_id]["result"] = result

        with self._conn() as conn:
            conn.execute(
                """UPDATE coding_tasks
                   SET status = ?, error_state = ?, result_json = ?
                   WHERE task_id = ?""",
                (status, error_msg or "", json.dumps(result or {}), task_id)
            )

        self._recalculate_session_progress()

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves resumable state for a session."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            s_cur = conn.execute("SELECT * FROM coding_sessions WHERE session_id = ?", (session_id,))
            s_row = s_cur.fetchone()
            if not s_row:
                return None

            t_cur = conn.execute("SELECT * FROM coding_tasks WHERE session_id = ? ORDER BY priority DESC", (session_id,))
            t_rows = t_cur.fetchall()

            tasks = {}
            for tr in t_rows:
                tasks[tr["task_id"]] = {
                    "task_id": tr["task_id"],
                    "description": tr["description"],
                    "role": tr["role"],
                    "status": tr["status"],
                    "priority": tr["priority"],
                    "dependencies": json.loads(tr["dependencies_json"] or "[]"),
                    "required_files": json.loads(tr["required_files_json"] or "[]"),
                    "expected_output": tr["expected_output"],
                    "validation_criteria": tr["validation_criteria"],
                    "retry_count": tr["retry_count"],
                    "error_state": tr["error_state"],
                    "result": json.loads(tr["result_json"] or "{}")
                }

            return {
                "session": dict(s_row),
                "tasks": tasks
            }

    def _recalculate_session_progress(self):
        if not self.active_session_id or not self.tasks:
            return
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.get("status") == "completed")
        pct = int((completed / total) * 100) if total > 0 else 0

        with self._conn() as conn:
            conn.execute(
                "UPDATE coding_sessions SET progress_pct = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (pct, self.active_session_id)
            )

    def _generate_default_tasks(self, goal: str) -> List[Dict[str, Any]]:
        return [
            {
                "task_id": "TASK-001",
                "description": f"Analyze architecture & specify contracts for: {goal}",
                "role": "architect",
                "dependencies": [],
                "priority": 100,
                "required_files": ["docs/architecture.md", "models.py"],
                "expected_output": "System blueprint & data models",
                "validation_criteria": "Models parse cleanly"
            },
            {
                "task_id": "TASK-002",
                "description": f"Design & implement database schema/migrations for: {goal}",
                "role": "database",
                "dependencies": ["TASK-001"],
                "priority": 90,
                "required_files": ["database/schema.sql", "database/db.py"],
                "expected_output": "Database schema and connection pooling",
                "validation_criteria": "Tables created successfully"
            },
            {
                "task_id": "TASK-003",
                "description": f"Implement backend REST APIs & auth business logic for: {goal}",
                "role": "backend",
                "dependencies": ["TASK-001", "TASK-002"],
                "priority": 80,
                "required_files": ["backend/server.py", "backend/routes.py"],
                "expected_output": "Working REST API endpoints",
                "validation_criteria": "Endpoints respond with JSON"
            },
            {
                "task_id": "TASK-004",
                "description": f"Implement responsive UI, components & client integration for: {goal}",
                "role": "frontend",
                "dependencies": ["TASK-001"],
                "priority": 80,
                "required_files": ["frontend/index.html", "frontend/styles.css", "frontend/app.js"],
                "expected_output": "Responsive web UI connecting to API",
                "validation_criteria": "HTML/CSS loads cleanly"
            },
            {
                "task_id": "TASK-005",
                "description": f"Write automated test suites for backend APIs & UI for: {goal}",
                "role": "tester",
                "dependencies": ["TASK-003", "TASK-004"],
                "priority": 60,
                "required_files": ["tests/test_api.py"],
                "expected_output": "Automated unit & integration test files",
                "validation_criteria": "Tests pass with 0 exit code"
            },
            {
                "task_id": "TASK-006",
                "description": f"Code review & security vulnerability audit for: {goal}",
                "role": "security",
                "dependencies": ["TASK-003", "TASK-004", "TASK-005"],
                "priority": 50,
                "required_files": [],
                "expected_output": "Audit report and quality pass",
                "validation_criteria": "No critical vulnerabilities"
            },
            {
                "task_id": "TASK-007",
                "description": f"DevOps containerization & CI/CD deployment configuration for: {goal}",
                "role": "devops",
                "dependencies": ["TASK-003", "TASK-004"],
                "priority": 40,
                "required_files": ["Dockerfile", "docker-compose.yml", ".env.example"],
                "expected_output": "Docker container and compose definitions",
                "validation_criteria": "Valid Dockerfile syntax"
            },
            {
                "task_id": "TASK-008",
                "description": f"Generate developer documentation & setup guides for: {goal}",
                "role": "documentation",
                "dependencies": ["TASK-003", "TASK-004", "TASK-005", "TASK-007"],
                "priority": 30,
                "required_files": ["README.md", "docs/api.md"],
                "expected_output": "Production README & setup instructions",
                "validation_criteria": "Complete README with usage instructions"
            }
        ]
