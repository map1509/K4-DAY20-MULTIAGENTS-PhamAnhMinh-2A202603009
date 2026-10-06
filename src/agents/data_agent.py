"""CSV analysis and read-only SQLite tools, using Python's standard library."""
import csv
import math
import sqlite3
from pathlib import Path

from .base_worker import BaseWorker, make_tools


class DataAgent(BaseWorker):
    SYSTEM_PROMPT = (
        "Analyze data using the supplied tools. Validate numeric values and column names. "
        "Do not invent missing values or modify databases. Report row counts and calculations."
    )

    def __init__(self, model=None, db_connection=None, *, workspace="."):
        self.db_connection = db_connection
        tool_map = {"analyze_csv": self.analyze_csv, "query_sql": self.query_sql,
                    "query_database": self.query_database, "csv_parser": self.csv_parser,
                    "pandas_analysis": self.pandas_analysis, "data_validation": self.data_validation}
        super().__init__("data_agent", model, make_tools(tool_map), result_type="data",
                         system_prompt=self.SYSTEM_PROMPT, tool_map=tool_map, workspace=workspace)

    def csv_parser(self, path: str, max_rows: int = 1000) -> dict:
        """Read CSV records and report whether the row limit truncated them."""
        if not 1 <= max_rows <= 10000:
            raise ValueError("max_rows must be between 1 and 10000")
        with self.resolve_path(path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = []
            for row in reader:
                rows.append(row)
                if len(rows) > max_rows:
                    break
            return {"columns": reader.fieldnames or [], "rows": rows[:max_rows], "truncated": len(rows) > max_rows}

    def pandas_analysis(self, path: str, column: str, aggregation: str = "sum", group_by: str | None = None) -> dict:
        """Aggregate a numeric CSV column with pandas, optionally grouped by another column."""
        import pandas as pd
        if aggregation not in ("sum", "mean", "min", "max", "count"):
            raise ValueError("Unsupported aggregation")
        frame = pd.read_csv(self.resolve_path(path))
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame[column].isna().any() or any(not math.isfinite(float(value)) for value in frame[column]):
            raise ValueError("Missing or nonfinite numeric data")
        if group_by:
            result = frame.groupby(group_by, dropna=False)[column].agg(aggregation).reset_index()
            return {"rows": result.to_dict(orient="records"), "row_count": len(frame)}
        value = frame[column].agg(aggregation)
        return {"value": value.item() if hasattr(value, "item") else value, "row_count": len(frame)}

    def data_validation(self, rows: list[dict], required_columns: list[str]) -> dict:
        """Identify rows with missing required columns or empty values."""
        issues = []
        for index, row in enumerate(rows):
            for column in required_columns:
                if column not in row or row[column] is None or row[column] == "":
                    issues.append({"row": index, "column": column, "issue": "missing value"})
        return {"valid": not issues, "issues": issues}

    def query_database(self, query: str, parameters: list | None = None, max_rows: int = 1000) -> dict:
        """Query the configured SQLite database path (db_connection), read-only."""
        if not isinstance(self.db_connection, (str, Path)):
            raise ValueError("db_connection must be a relative SQLite database path; use query_sql otherwise")
        return self.query_sql(str(self.db_connection), query, parameters or (), max_rows)

    def analyze_csv(self, path, column, aggregation="sum"):
        if aggregation not in ("sum", "mean", "min", "max", "count"):
            raise ValueError("Unsupported aggregation")
        values = []
        with self.resolve_path(path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or column not in reader.fieldnames:
                raise ValueError(f"Unknown column: {column}")
            for line, row in enumerate(reader, 2):
                raw = row.get(column)
                if raw is None or not raw.strip():
                    raise ValueError(f"Missing value at row {line}")
                value = float(raw)
                if not math.isfinite(value):
                    raise ValueError(f"Nonfinite value at row {line}")
                values.append(value)
        if not values and aggregation not in ("sum", "count"):
            raise ValueError("Cannot aggregate empty data")
        total = math.fsum(values)
        result = {"sum": lambda: total, "mean": lambda: total / len(values),
                  "min": lambda: min(values), "max": lambda: max(values), "count": lambda: len(values)}[aggregation]()
        return {"column": column, "aggregation": aggregation, "value": result, "row_count": len(values)}

    def query_sql(self, path, query, parameters=(), max_rows=1000):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty")
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= 10000:
            raise ValueError("max_rows must be between 1 and 10000")
        database = self.resolve_path(path)
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            steps = 0
            def limit_steps():
                nonlocal steps
                steps += 1
                return int(steps > 1000)
            connection.set_progress_handler(limit_steps, 1000)
            cursor = connection.execute(query, parameters)
            if cursor.description is None:
                raise ValueError("query must return rows")
            rows = cursor.fetchmany(max_rows + 1)
            return {"columns": [field[0] for field in cursor.description],
                    "rows": [list(row) for row in rows[:max_rows]], "truncated": len(rows) > max_rows}
