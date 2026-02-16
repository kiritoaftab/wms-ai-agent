"""
Thread Manager — manages conversation threads stored in SQLite.
Each thread is a chain of query/response nodes.
"""

import uuid
import json
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict

from app.config import get_settings


class ThreadManager:
    def __init__(self):
        self.db_path = get_settings().sqlite_db_path
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS thread_nodes (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    parent_node_id TEXT,
                    question TEXT NOT NULL,
                    sql_generated TEXT,
                    data_json TEXT,
                    row_count INTEGER DEFAULT 0,
                    summary TEXT,
                    chart_suggestion_json TEXT,
                    follow_ups_json TEXT,
                    error TEXT,
                    execution_time_ms REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (thread_id) REFERENCES threads(id)
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_thread
                    ON thread_nodes(thread_id);
            """)

    @contextmanager
    def _get_conn(self):
        """Context manager for SQLite connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create_thread(self, title: str) -> str:
        """Create a new thread. Returns thread_id."""
        thread_id = f"t-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (thread_id, title, now, now),
            )

        return thread_id

    def add_node(
        self,
        thread_id: str,
        question: str,
        sql_generated: Optional[str] = None,
        data: Optional[List[dict]] = None,
        row_count: int = 0,
        summary: str = "",
        chart_suggestion: Optional[dict] = None,
        follow_ups: Optional[List[str]] = None,
        error: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        parent_node_id: Optional[str] = None,
    ) -> str:
        """Add a query/response node to a thread. Returns node_id."""
        node_id = f"n-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO thread_nodes
                   (id, thread_id, parent_node_id, question, sql_generated,
                    data_json, row_count, summary, chart_suggestion_json,
                    follow_ups_json, error, execution_time_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    node_id, thread_id, parent_node_id, question,
                    sql_generated,
                    json.dumps(data) if data else None,
                    row_count, summary,
                    json.dumps(chart_suggestion) if chart_suggestion else None,
                    json.dumps(follow_ups) if follow_ups else None,
                    error, execution_time_ms, now,
                ),
            )
            # Update thread timestamp
            conn.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (now, thread_id),
            )

        return node_id

    def get_thread(self, thread_id: str) -> Optional[dict]:
        """Get a thread with all its nodes."""
        with self._get_conn() as conn:
            thread = conn.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()

            if not thread:
                return None

            nodes = conn.execute(
                "SELECT * FROM thread_nodes WHERE thread_id = ? ORDER BY created_at",
                (thread_id,),
            ).fetchall()

            return {
                "thread_id": thread["id"],
                "title": thread["title"],
                "created_at": thread["created_at"],
                "updated_at": thread["updated_at"],
                "nodes": [self._node_to_dict(n) for n in nodes],
            }

    def list_threads(self, limit: int = 50) -> list[dict]:
        """List recent threads."""
        with self._get_conn() as conn:
            threads = conn.execute(
                """SELECT t.*, COUNT(n.id) as node_count
                   FROM threads t
                   LEFT JOIN thread_nodes n ON t.id = n.thread_id
                   GROUP BY t.id
                   ORDER BY t.updated_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            return [
                {
                    "thread_id": t["id"],
                    "title": t["title"],
                    "created_at": t["created_at"],
                    "updated_at": t["updated_at"],
                    "node_count": t["node_count"],
                }
                for t in threads
            ]

    def get_conversation_history(self, thread_id: str) -> list[dict]:
        """Get Q&A history for a thread (for context in follow-ups)."""
        with self._get_conn() as conn:
            nodes = conn.execute(
                """SELECT question, sql_generated, summary
                   FROM thread_nodes WHERE thread_id = ?
                   ORDER BY created_at""",
                (thread_id,),
            ).fetchall()

            history = []
            for node in nodes:
                history.append({
                    "question": node["question"],
                    "response": f"SQL: {node['sql_generated']}\nResult: {node['summary']}",
                })
            return history

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and all its nodes."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM thread_nodes WHERE thread_id = ?", (thread_id,))
            result = conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            return result.rowcount > 0

    def _node_to_dict(self, node) -> dict:
        """Convert a SQLite Row to a clean dict."""
        return {
            "node_id": node["id"],
            "parent_node_id": node["parent_node_id"],
            "question": node["question"],
            "sql_generated": node["sql_generated"],
            "data": json.loads(node["data_json"]) if node["data_json"] else [],
            "row_count": node["row_count"],
            "summary": node["summary"] or "",
            "chart_suggestion": json.loads(node["chart_suggestion_json"]) if node["chart_suggestion_json"] else None,
            "follow_ups": json.loads(node["follow_ups_json"]) if node["follow_ups_json"] else [],
            "error": node["error"],
            "execution_time_ms": node["execution_time_ms"],
            "created_at": node["created_at"],
        }
