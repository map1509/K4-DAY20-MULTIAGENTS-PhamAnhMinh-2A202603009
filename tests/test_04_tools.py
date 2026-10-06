from contextlib import closing
import sqlite3
from tools import QueryDatabaseTool, PythonREPLTool, CreateFileTool, ScoringTool


def test_query_database_tool(tmp_path):
    database = tmp_path / "sales.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE sales (amount INTEGER)")
        connection.executemany("INSERT INTO sales VALUES (?)", [(2,), (3,)])
        connection.commit()
    tool = QueryDatabaseTool(database)
    try:
        result = tool.invoke({"query": "SELECT SUM(amount) AS total FROM sales;"})
        assert result["status"] == "success" and result["data"] == [{"total": 5}]
        assert tool.invoke({"query": "SELECT * FROM sales LIMIT 1"})["rows"] == 1
        assert tool.invoke({"query": "DELETE FROM sales"})["status"] == "error"
    finally:
        tool.close()


def test_python_repl_tool(tmp_path):
    tool = PythonREPLTool(tmp_path)
    try:
        result = tool.invoke({"code": "value = 5\nprint(value)"})
        assert result["status"] == "success", result
        assert result["stdout"] == "5\n"
        assert tool.invoke({"code": "print(value + 1)"})["stdout"] == "6\n"
        assert tool.invoke({"code": "import os"})["status"] == "error"
        assert tool.invoke({"code": "import sys\nsys.exit()"})["status"] == "error"
        assert tool.invoke({"code": "print('x' * 20000)"})["stdout"] == "x" * 10000
        assert tool.invoke({"code": "while True: pass", "timeout": .1})["type"] == "TimeoutError"
        assert tool.invoke({"code": "print(2)"})["stdout"] == "2\n"
    finally:
        tool.close()


def test_create_file_tool(tmp_path):
    tool = CreateFileTool(tmp_path)
    result = tool.invoke({"filename": "nested/report.txt", "content": "Doanh thu: 5"})
    assert result["status"] == "success"
    assert (tmp_path / "nested/report.txt").read_text(encoding="utf-8") == "Doanh thu: 5"
    assert tool.invoke({"filename": "../escape.txt", "content": "bad"})["status"] == "error"


def test_scoring_tool():
    tool = ScoringTool()
    result = tool.invoke({"result": "Sales analysis", "scores": {
        "accuracy": 85, "completeness": 90, "clarity": 80, "performance": 82.5}})
    assert result["status"] == "success" and result["weighted_score"] == 85
    assert result["grade"] == "B"
    assert tool.invoke({"result": "", "criteria": {"accuracy": 0}})["status"] == "error"
