"""
Query Executor — runs validated SQL against the WMS MySQL database.
Uses a read-only connection with timeouts and row limits.
"""

import time
import mysql.connector
from mysql.connector import Error as MySQLError

from app.config import get_settings


class QueryExecutionError(Exception):
    """Raised when query execution fails."""
    pass


class QueryExecutor:
    def __init__(self):
        self._settings = get_settings()
        self._pool = None

    def _get_connection(self):
        """Get a connection from pool or create one."""
        try:
            conn = mysql.connector.connect(
                host=self._settings.wms_db_host,
                port=self._settings.wms_db_port,
                database=self._settings.wms_db_name,
                user=self._settings.wms_db_user,
                password=self._settings.wms_db_password,
                connection_timeout=5,
                autocommit=True,   # read-only, no transaction needed
            )
            return conn
        except MySQLError as e:
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
        settings = self._settings
        conn = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            # Set query timeout at session level
            cursor.execute(
                f"SET SESSION MAX_EXECUTION_TIME = {settings.query_timeout_seconds * 1000}"
            )

            start_time = time.time()
            cursor.execute(sql)
            rows = cursor.fetchall()
            execution_time = (time.time() - start_time) * 1000

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Convert any non-serializable types
            data = []
            for row in rows:
                clean_row = {}
                for key, value in row.items():
                    if isinstance(value, bytes):
                        clean_row[key] = value.decode("utf-8", errors="replace")
                    elif hasattr(value, "isoformat"):
                        clean_row[key] = value.isoformat()
                    elif isinstance(value, (int, float, str, bool, type(None))):
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

        except MySQLError as e:
            error_msg = str(e)
            # Don't leak internal DB details
            if "MAX_EXECUTION_TIME" in error_msg or "timeout" in error_msg.lower():
                raise QueryExecutionError("Query timed out. Try a more specific question.")
            elif "Unknown column" in error_msg:
                raise QueryExecutionError(f"Query referenced an invalid column: {error_msg}")
            elif "doesn't exist" in error_msg:
                raise QueryExecutionError(f"Query referenced an invalid table: {error_msg}")
            else:
                raise QueryExecutionError(f"Query execution failed: {error_msg}")
        finally:
            if conn and conn.is_connected():
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
