"""SQLite query tool for Part 4.2."""
from pathlib import Path
import re
import sqlite3
import logging
from time import perf_counter
from threading import RLock

from .base_tool import BaseTool


class QueryDatabaseTool(BaseTool):
    def __init__(self, connection_string):
        super().__init__("query_database", "Execute read-only SELECT queries on the connected SQLite database")
        self.conn_string = str(connection_string)
        self.connection = None
        self._lock = RLock()

    def connect(self):
        """Open an existing SQLite database with read-only access."""
        with self._lock:
            if self.connection is None:
                database = Path(self.conn_string).resolve()
                self.connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True,
                                                  check_same_thread=False, timeout=5)
                self.connection.row_factory = sqlite3.Row
                self.connection.execute("PRAGMA query_only=ON")
            return self.connection

    def validate_input(self, input_dict):
        if not isinstance(input_dict, dict):
            raise ValueError("input must be a dictionary")
        query = input_dict.get("query", "")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a nonempty string")
        for keyword in ("DROP", "DELETE", "TRUNCATE", "ALTER"):
            if re.search(rf"\b{keyword}\b", query, re.IGNORECASE):
                raise ValueError(f"Dangerous operation: {keyword} not allowed")
        if not re.match(r"^\s*SELECT\b", query, re.IGNORECASE):
            raise ValueError("Only SELECT queries allowed")
        limit = input_dict.get("limit", 1000)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        if not isinstance(input_dict.get("parameters", ()), (list, tuple, dict)):
            raise ValueError("parameters must be a list, tuple or dictionary")
        return True

    def invoke(self, input_dict):
        started = perf_counter()
        try:
            self.validate_input(input_dict)
            query = input_dict["query"].strip()
            if query.endswith(";"):
                query = query[:-1].rstrip()
            limit = input_dict.get("limit", 1000)
            with self._lock:
                connection = self.connect()
                steps = 0
                def limit_work():
                    nonlocal steps
                    steps += 1
                    return int(steps > 1000)
                connection.set_progress_handler(limit_work, 1000)
                try:
                    # Wrapping respects an existing LIMIT and a trailing semicolon.
                    cursor = connection.execute(f"SELECT * FROM ({query}) AS tool_result LIMIT {limit}",
                                                input_dict.get("parameters", ()))
                    try:
                        rows = cursor.fetchall()
                        columns = [field[0] for field in cursor.description]
                        logging.getLogger(self.name).info("SQL query rows=%s duration=%.3fs", len(rows), perf_counter() - started)
                        return {"status": "success", "rows": len(rows), "columns": columns,
                                "data": [dict(row) for row in rows[:100]]}
                    finally:
                        cursor.close()
                finally:
                    connection.set_progress_handler(None, 0)
        except Exception as exc:
            logging.getLogger(self.name).error("SQL failed duration=%.3fs: %s", perf_counter() - started, exc)
            return {"status": "error", "error": str(exc)}

    def close(self):
        with self._lock:
            if self.connection is not None:
                self.connection.close()
                self.connection = None
