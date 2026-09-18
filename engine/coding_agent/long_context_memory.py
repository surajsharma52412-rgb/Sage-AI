"""
Long-Context Memory for SAGE Coding Agent Architecture (v6).
Stores and indexes:
- Conversation memory across project tasks
- Project memory (files, dependencies, tech stack details)
- Codebase indexing (RAG with cosine similarity / BM25 token matching)
- Technical decisions log (ADRs - Architectural Decision Records)
- Previous solutions and pattern library
- SQLite short-term persistence
"""
import os
import re
import math
import json
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LongContextMemory:
    """Manages cross-task memory, RAG indexing of code, ADRs, and solution history."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path.home() / ".sage" / "coding_agent_memory"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "project_memory.db")
        else:
            self.db_path = str(db_path)
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.indexed_chunks: List[Dict[str, Any]] = []
        self._init_db()

    @contextmanager
    def _conn(self):
        """Safely opens and closes SQLite connection to avoid file locks on Windows."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Initializes SQLite tables for memory persistence."""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS technical_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT,
                    title TEXT,
                    status TEXT,
                    decision TEXT,
                    consequences TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS previous_solutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem_signature TEXT UNIQUE,
                    solution_summary TEXT,
                    code_snippet TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    # --- Conversation & Project Memory ---

    def add_conversation_turn(self, role: str, content: str, task_id: str = ""):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversation_memory (task_id, role, content) VALUES (?, ?, ?)",
                (task_id, role, content)
            )

    def get_conversation_history(self, task_id: Optional[str] = None, limit: int = 15) -> List[Dict[str, str]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            if task_id:
                cur = conn.execute(
                    "SELECT role, content FROM conversation_memory WHERE task_id = ? ORDER BY id DESC LIMIT ?",
                    (task_id, limit)
                )
            else:
                cur = conn.execute(
                    "SELECT role, content FROM conversation_memory ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            rows = cur.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def record_technical_decision(self, project_name: str, title: str, decision: str, consequences: str = "", status: str = "Accepted"):
        """Records an Architectural Decision Record (ADR)."""
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO technical_decisions (project_name, title, status, decision, consequences)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_name, title, status, decision, consequences)
            )

    def get_technical_decisions(self, project_name: str = "") -> List[Dict[str, Any]]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            if project_name:
                cur = conn.execute(
                    "SELECT title, status, decision, consequences FROM technical_decisions WHERE project_name = ? ORDER BY id ASC",
                    (project_name,)
                )
            else:
                cur = conn.execute(
                    "SELECT title, status, decision, consequences FROM technical_decisions ORDER BY id ASC"
                )
            return [dict(r) for r in cur.fetchall()]

    def record_solution(self, problem_signature: str, solution_summary: str, code_snippet: str = ""):
        """Stores a successful pattern or fix for future reference."""
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO previous_solutions (problem_signature, solution_summary, code_snippet)
                   VALUES (?, ?, ?)""",
                (problem_signature, solution_summary, code_snippet)
            )

    def find_previous_solution(self, problem_query: str) -> Optional[Dict[str, Any]]:
        """Finds any previously cached fix matching the problem pattern."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT problem_signature, solution_summary, code_snippet FROM previous_solutions")
            rows = cur.fetchall()
            q_words = set(re.findall(r"\w+", problem_query.lower()))
            best_match = None
            best_score = 0
            for r in rows:
                sig_words = set(re.findall(r"\w+", r["problem_signature"].lower()))
                overlap = len(q_words & sig_words)
                if overlap > best_score and overlap >= 2:
                    best_score = overlap
                    best_match = dict(r)
            return best_match

    # --- Codebase Indexing (RAG Engine) ---

    def index_codebase_chunks(self, chunks: List[Dict[str, Any]]):
        """Indexes extracted file chunks into in-memory RAG catalog."""
        self.indexed_chunks = chunks

    def search_code_rag(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves relevant code chunks using TF-IDF / lexical cosine similarity.
        Operates fully offline without external vector API requirements.
        """
        if not self.indexed_chunks:
            return []

        query_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        if not query_tokens:
            return self.indexed_chunks[:top_k]

        q_tf = {}
        for t in query_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1

        scored = []
        for chunk in self.indexed_chunks:
            content_lower = chunk["content"].lower()
            path_lower = chunk["path"].lower()

            chunk_tokens = re.findall(r"\w+", content_lower)
            doc_len = max(len(chunk_tokens), 1)

            score = 0.0
            for t, q_count in q_tf.items():
                if t in path_lower:
                    score += 2.5
                c_matches = content_lower.count(t)
                if c_matches > 0:
                    score += (c_matches / (c_matches + 1.2 * (doc_len / 50.0))) * q_count

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
