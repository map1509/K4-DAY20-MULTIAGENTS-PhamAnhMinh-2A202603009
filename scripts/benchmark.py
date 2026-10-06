"""Part 5.4: three benchmark cases, three iterations each by default."""
import argparse
import asyncio
import ast
import json
from pathlib import Path
import statistics
from time import perf_counter
import uuid

from langchain_core.callbacks import UsageMetadataCallbackHandler
from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator
from lab.model import make_model
from logging_config import configure_logging, redact
from system import MultiAgentSystem


class Benchmark:
    def __init__(self):
        self.results = []

    async def run_test(self, name, request, system, iterations=3, validator=None):
        print(f"\nBenchmarking: {name}", flush=True)
        latencies, runs = [], []
        for index in range(iterations):
            start = perf_counter()
            try:
                result = await system.process(request(index) if callable(request) else request)
                latency = perf_counter() - start
                valid = validator(result, index) if validator is not None else True
                status = "success" if result["status"] == "success" and valid else "error"
                run = {"iteration": index + 1, "status": status, "pipeline_status": result["status"],
                       "output_validation": valid, "errors": result.get("errors", [])}
            except Exception as exc:
                latency = perf_counter() - start
                status = "error"
                run = {"iteration": index + 1, "status": status, "error": redact(str(exc))}
            latencies.append(latency)
            run["latency_seconds"] = latency
            runs.append(run)
            print(f"  Iteration {index + 1}: {latency:.3f}s {status}", flush=True)
        stats = {"name": name, "iterations": iterations, "min": min(latencies), "max": max(latencies),
                 "avg": statistics.mean(latencies), "median": statistics.median(latencies),
                 "success_count": sum(run["status"] == "success" for run in runs), "runs": runs}
        self.results.append(stats)
        print(f"  Min={stats['min']:.3f}s Max={stats['max']:.3f}s Avg={stats['avg']:.3f}s Median={stats['median']:.3f}s", flush=True)
        return stats


async def main(args):
    directory = Path("results/benchmark") / str(uuid.uuid4())
    workspace = directory / "workspace"
    workspace.mkdir(parents=True)
    configure_logging(directory / "logs")
    (workspace / "sales.csv").write_text("month,revenue\n7,100\n8,150\n9,250\n", encoding="utf-8")
    usage = UsageMetadataCallbackHandler()
    def model():
        if args.offline:
            return None
        instance = make_model()
        instance.callbacks = [usage]
        return instance
    workers = [DataAgent(model(), workspace=workspace), CodeAgent(model(), workspace=workspace), EvaluatorAgent(model(), workspace=workspace)]
    system = MultiAgentSystem(Coordinator(model(), workers), workers)
    bench = Benchmark()

    def simple(index):
        if not args.offline:
            return "What is total revenue? Source: sales.csv, numeric column revenue. Use analyze_csv with sum."
        return {"task_type": "data_analysis", "parameters": {"operation": "analyze_csv", "path": "sales.csv", "column": "revenue"}}

    def code(index):
        if not args.offline:
            return (f"Write Python script to read CSV sales.csv with pandas and print total revenue. "
                    f"Create read_csv-{index}.py. Use write_file then run_script to test it. Return the script path and console output.")
        return {"task_type": "code_generation", "parameters": {"operation": "create_file", "filename": f"read_csv-{index}.py",
                "content": "import pandas as pd\ndata = pd.read_csv('sales.csv')\nprint(data['revenue'].sum())\n"}}

    def complex_request(index):
        plotting = f"import matplotlib.pyplot as plt\nplt.figure()\nplt.bar([7,8,9], [100,150,250])\nplt.savefig('chart-{index}.png')\nplt.close()\nprint('Chart created')"
        if not args.offline:
            return (f"Analyze sales data AND create chart AND evaluate result. Source sales.csv (month,revenue). "
                    f"Data agent: analyze_csv sum revenue. Code agent: use verified upstream data and python_repl with matplotlib, "
                    f"save chart-{index}.png showing monthly sales. Return the saved path after successful execution.")
        return {"task_type": "complex", "parameters": {"data_agent": {"operation": "analyze_csv", "path": "sales.csv", "column": "revenue"},
                "code_agent": {"operation": "python_repl", "code": plotting}}}

    def data_valid(result, index):
        return isinstance(result.get("data"), dict) and result["data"].get("value") == 500

    def code_valid(result, index):
        path = workspace / f"read_csv-{index}.py"
        if not path.exists():
            return False
        ast.parse(path.read_text(encoding="utf-8"))
        return bool(result.get("code"))

    def complex_valid(result, index):
        path = workspace / f"chart-{index}.png"
        return data_valid(result, index) and path.exists() and path.read_bytes().startswith(b"\x89PNG") and result.get("evaluation") is not None

    start = perf_counter()
    try:
        for name, request, validator in (("Simple data query", simple, data_valid), ("Code generation", code, code_valid),
                                         ("Complex workflow", complex_request, complex_valid)):
            await bench.run_test(name, request, system, args.iterations, validator)
        elapsed = perf_counter() - start
        latencies = sorted(run["latency_seconds"] for case in bench.results for run in case["runs"])
        total = len(latencies)
        successes = sum(case["success_count"] for case in bench.results)
        p99_position = (total - 1) * .99
        low = int(p99_position)
        p99 = latencies[low] + (latencies[min(low+1,total-1)] - latencies[low]) * (p99_position-low)
        tokens = {key: sum(value.get(key, 0) for value in usage.usage_metadata.values()) for key in ("input_tokens", "output_tokens", "total_tokens")}
        metrics = {"mode": "local" if args.offline else "live", "requests": total, "successes": successes,
                   "p50_seconds": statistics.median(latencies), "p99_seconds": p99,
                   "throughput_attempts_per_minute": total * 60 / elapsed,
                   "throughput_successes_per_minute": successes * 60 / elapsed,
                   "error_rate_percent": (total - successes) * 100 / total, "token_usage": tokens,
                   "tokens_per_100_projected": tokens["total_tokens"] / total * 100,
                   "note": "Nine default samples, including failures; code validator checks file/syntax, not arbitrary code correctness."}
        text = redact(json.dumps(bench.results, indent=2, ensure_ascii=False))
        (directory / "benchmark_results.json").write_text(text, encoding="utf-8")
        Path("benchmark_results.json").write_text(text, encoding="utf-8")
        (directory / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(json.dumps(metrics, indent=2))
        print(f"Benchmark complete. benchmark_results.json; artifacts: {directory}")
    finally:
        for worker in workers:
            if hasattr(worker, "close"):
                worker.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--offline", action="store_true", help="Use structured local tasks without model calls")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    asyncio.run(main(args))
