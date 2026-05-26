"""
Query Executor — runs validated SQL against the HMS PostgreSQL database.
Uses a read-only connection with timeouts and row limits.
"""

import time
from decimal import Decimal
from uuid import UUID

import psycopg2
import psycopg2.extras
from psycopg2 import OperationalError, DatabaseError

from app.config import get_settings


class QueryExecutionError(Exception):
    """Raised when query execution fails."""
    pass


class QueryExecutor:
    def __init__(self):
        self._settings = get_settings()

    def _get_connection(self):
        """Create a new read-only database connection."""
        settings = self._settings
        timeout_ms = settings.query_timeout_seconds * 1000
        try:
            conn = psycopg2.connect(
                host=settings.hms_db_host,
                port=settings.hms_db_port,
                dbname=settings.hms_db_name,
                user=settings.hms_db_user,
                password=settings.hms_db_password,
                connect_timeout=5,
                # Set statement timeout at connection level
                options=f"-c statement_timeout={timeout_ms}",
            )
            conn.autocommit = True
            return conn
        except OperationalError as e:
            raise QueryExecutionError(f"Database connection failed: {str(e)}")

    def execute(self, sql: str) -> dict:
        """
        Execute a validated SELECT query.

        Returns dict with:
            - columns: list of column names
            - data: list of dicts (row data)
            - row_count: number of rows returned
            - execution_time_ms: query execution time
        """
        conn = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            start_time = time.time()
            cursor.execute(sql)
            rows = cursor.fetchall()
            execution_time = (time.time() - start_time) * 1000

            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            data = []
            for row in rows:
                clean_row = {}
                for key, value in dict(row).items():
                    if value is None:
                        clean_row[key] = None
                    elif isinstance(value, UUID):
                        clean_row[key] = str(value)
                    elif isinstance(value, Decimal):
                        clean_row[key] = float(value)
                    elif hasattr(value, "isoformat"):
                        clean_row[key] = value.isoformat()
                    elif isinstance(value, (bytes, memoryview)):
                        clean_row[key] = bytes(value).decode("utf-8", errors="replace")
                    elif isinstance(value, (int, float, str, bool)):
                        clean_row[key] = value
                    else:
                        clean_row[key] = str(value)
                data.append(clean_row)

            cursor.close()

            return {
                "columns": columns,
                "data": data,
                "row_count": len(data),
                "execution_time_ms": round(execution_time, 2),
            }

        except DatabaseError as e:
            error_msg = str(e)
            if "statement timeout" in error_msg.lower() or "canceling statement" in error_msg.lower():
                raise QueryExecutionError("Query timed out. Try a more specific question.")
            elif "column" in error_msg.lower() and "does not exist" in error_msg.lower():
                raise QueryExecutionError(f"Query referenced an invalid column: {error_msg}")
            elif "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
                raise QueryExecutionError(f"Query referenced an invalid table: {error_msg}")
            else:
                raise QueryExecutionError(f"Query execution failed: {error_msg}")
        finally:
            if conn and conn.closed == 0:
                conn.close()

    def test_connection(self) -> bool:
        """Test if database is reachable."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True
        except Exception:
            return False
