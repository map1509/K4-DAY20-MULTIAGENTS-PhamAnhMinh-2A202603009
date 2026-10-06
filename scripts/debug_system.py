"""Debug one complete request; --live uses the configured model/provider."""
import argparse
import asyncio
import json
from pathlib import Path
import traceback

from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator
from lab.model import make_model
from logging_config import configure_logging, redact
from system import MultiAgentSystem


async def debug_request(request, workspace, timeout=60, live=False):
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    model = make_model() if live else None
    workers = [DataAgent(model, workspace=workspace), CodeAgent(model, workspace=workspace), EvaluatorAgent(model, workspace=workspace)]
    system = MultiAgentSystem(Coordinator(model, workers), workers)
    print(f"Debugging: {request}\n{'-' * 50}")
    try:
        if live:
            task = request
        else:
            # A repeatable local debug fixture; not natural-language classification.
            (workspace / "sales.csv").write_text("month,revenue\n7,100\n8,150\n9,250\n", encoding="utf-8")
            task = {"task_type": "complex", "parameters": {
                "data_agent": {"operation": "analyze_csv", "path": "sales.csv", "column": "revenue"},
                "code_agent": {"operation": "create_file", "filename": "report.txt", "content": "Q3 fixture: 100 + 150 + 250 = 500"}}}
        result = await system.process(task, timeout=timeout, debug=True)
        print(redact(json.dumps(result, ensure_ascii=False, indent=2)))
        print("Logs: logs/coordinator.log, logs/communication.log, logs/*_agent.log")
        return 0 if result["status"] == "success" else 1
    except Exception:
        print(redact(traceback.format_exc()))
        return 1
    finally:
        for worker in workers:
            if hasattr(worker, "close"):
                worker.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", default="Analyze Q3 sales and create report")
    parser.add_argument("--workspace", default="outputs/debug")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--live", action="store_true", help="Use the configured LLM; consumes tokens")
    args = parser.parse_args()
    configure_logging()
    return asyncio.run(debug_request(args.request, args.workspace, args.timeout, args.live))


if __name__ == "__main__":
    raise SystemExit(main())
