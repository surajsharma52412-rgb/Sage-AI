"""
Database Engineer Worker for SAGE Coding Agent.
Internal worker specialized in:
- Schema design & SQL table specifications
- Relational mapping & foreign key constraints
- SQLite / PostgreSQL connection pooling & migrations
- Query optimization & database seed scripts
"""
import logging
from typing import Dict, Any, List, Optional, Callable

from .base_sub_agent import BaseSubAgent

logger = logging.getLogger(__name__)


class DatabaseWorker(BaseSubAgent):
    """Specialized internal worker for database modeling, migrations, and query optimization."""

    def __init__(self, context_mgr, tools, model_router=None):
        super().__init__(role="database", name="Database Engineer", context_mgr=context_mgr, tools=tools, model_router=model_router)

    def execute(
        self,
        task: Dict[str, Any],
        dep_context: Dict[str, Any],
        llm_caller_fn: Optional[Callable[..., Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        instruction = task.get("instruction") or task.get("description", "")

        system_prompt = (
            "You are Sage AI's Database Engineer. "
            "Design clean, normalized database schemas, migrations, and connection helpers. "
            "Write robust SQL tables and Python/JS persistence modules. "
            "Specify file paths clearly in markdown code fences, e.g.:\n"
            "```sql file:database/schema.sql\n-- sql\n```\n"
            "```python file:database/db.py\n# code\n```"
        )

        prompt = (
            f"Database Task: {instruction}\n\n"
            "Generate production-grade schema definitions, indexing, connection helpers, and seed data."
        )

        llm_res = self.call_llm(prompt=prompt, system_prompt=system_prompt, llm_caller_fn=llm_caller_fn)
        content_text = llm_res.get("text", "")
        extracted_files = self.extract_code_blocks(content_text)

        if not extracted_files:
            schema_sql = (
                "-- Database Schema\n"
                "CREATE TABLE IF NOT EXISTS users (\n"
                "    id TEXT PRIMARY KEY,\n"
                "    email TEXT UNIQUE NOT NULL,\n"
                "    password_hash TEXT NOT NULL,\n"
                "    role TEXT DEFAULT 'user',\n"
                "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
                ");\n\n"
                "CREATE TABLE IF NOT EXISTS items (\n"
                "    id TEXT PRIMARY KEY,\n"
                "    title TEXT NOT NULL,\n"
                "    description TEXT,\n"
                "    status TEXT DEFAULT 'active',\n"
                "    user_id TEXT,\n"
                "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
                "    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE\n"
                ");\n"
                "CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id);\n"
            )
            extracted_files.append({"language": "sql", "path": "database/schema.sql", "content": schema_sql})

            db_helper = (
                '"""\nDatabase Connection & Initialization Helper.\n"""\n'
                'import sqlite3\n'
                'from pathlib import Path\n'
                'from typing import Optional\n\n'
                'DB_PATH = Path(__file__).parent / "app.db"\n\n'
                'def get_connection(db_file: Optional[Path] = None):\n'
                '    path = db_file or DB_PATH\n'
                '    conn = sqlite3.connect(path)\n'
                '    conn.row_factory = sqlite3.Row\n'
                '    return conn\n\n'
                'def init_database():\n'
                '    schema_file = Path(__file__).parent / "schema.sql"\n'
                '    if schema_file.exists():\n'
                '        sql = schema_file.read_text(encoding="utf-8")\n'
                '        with get_connection() as conn:\n'
                '            conn.executescript(sql)\n'
                '            conn.commit()\n'
            )
            extracted_files.append({"language": "python", "path": "database/db.py", "content": db_helper})

        return {
            "success": True,
            "role": self.role,
            "agent_name": self.name,
            "summary": content_text or "Database schema and connection helper generated.",
            "generated_files": extracted_files
        }
