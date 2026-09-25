"""
Database Connection & Initialization Helper.
"""
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "app.db"

def get_connection(db_file: Optional[Path] = None):
    path = db_file or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    schema_file = Path(__file__).parent / "schema.sql"
    if schema_file.exists():
        sql = schema_file.read_text(encoding="utf-8")
        with get_connection() as conn:
            conn.executescript(sql)
            conn.commit()
