"""Run one worker independently. SQL debugging needs --database or --demo."""
import argparse
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from agents import DataAgent, CodeAgent, EvaluatorAgent
from logging_config import configure_logging, redact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, choices=["data_agent", "code_agent", "evaluator_agent"])
    parser.add_argument("--task", required=True, help="SQL, Python code, or evaluation text")
    parser.add_argument("--workspace", default="outputs/debug")
    parser.add_argument("--database", default="sales.db")
    parser.add_argument("--demo", action="store_true", help="Create a separate demo database if missing")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    configure_logging()
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if args.demo:
        database = (workspace / args.database).resolve()
        if not database.is_relative_to(workspace):
            parser.error("database must be inside workspace")
        if not database.exists():
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("CREATE TABLE sales (year INTEGER, quarter INTEGER, revenue REAL)")
                connection.executemany("INSERT INTO sales VALUES (2026, 3, ?)", [(100,), (150,), (250,)])
                connection.commit()
    if args.agent == "data_agent":
        worker = DataAgent(db_connection=args.database, workspace=workspace)
        params = {"operation": "query_database", "query": args.task}
    elif args.agent == "code_agent":
        worker = CodeAgent(workspace=workspace)
        params = {"operation": "python_repl", "code": args.task, "timeout": args.timeout}
    else:
        worker = EvaluatorAgent(workspace=workspace)
        params = {"operation": "score_result", "result": args.task}
    try:
        result = asyncio.run(asyncio.wait_for(worker.process_async(params), args.timeout))
        print(redact(json.dumps(result, ensure_ascii=False, indent=2)))
        return 0
    except Exception as exc:
        print(redact(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)))
        return 1
    finally:
        if hasattr(worker, "close"):
            worker.close()


if __name__ == "__main__":
    raise SystemExit(main())
