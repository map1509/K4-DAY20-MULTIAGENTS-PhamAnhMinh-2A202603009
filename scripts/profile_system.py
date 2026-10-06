"""Part 5.3: cProfile and measured latency/throughput/utilization/error/token metrics."""
import argparse
import asyncio
import cProfile
import json
from pathlib import Path
import pstats
from time import perf_counter
import uuid

from langchain_core.callbacks import UsageMetadataCallbackHandler
from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator
from lab.model import make_model
from logging_config import configure_logging, redact
from system import MultiAgentSystem


class TimedWorker:
    def __init__(self, worker):
        self.worker = worker
        self.name = worker.name
        self.busy_seconds = 0
        self.calls = 0

    async def process_async(self, *args, **kwargs):
        start = perf_counter()
        self.calls += 1
        try:
            return await self.worker.process_async(*args, **kwargs)
        finally:
            self.busy_seconds += perf_counter() - start


def percentile(values, percent):
    values = sorted(values)
    position = (len(values) - 1) * percent / 100
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


async def run_system(args, output_dir):
    workspace = output_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "sales.csv").write_text("month,revenue\n7,100\n8,150\n9,250\n", encoding="utf-8")
    usage = UsageMetadataCallbackHandler()
    def model():
        if not args.live:
            return None
        instance = make_model()
        instance.callbacks = [usage]
        return instance
    underlying = [DataAgent(model(), workspace=workspace), CodeAgent(model(), workspace=workspace),
                  EvaluatorAgent(model(), workspace=workspace)]
    workers = [TimedWorker(worker) for worker in underlying]
    coordinator = Coordinator(model(), workers)
    system = MultiAgentSystem(coordinator, workers)
    latencies, records = [], []
    started = perf_counter()
    try:
        for index in range(args.requests):
            if args.live:
                request = (
                    f"Test request {index}: Analyze Q3 total revenue in sales.csv (columns month,revenue). "
                    f"Delegate data analysis to data_agent and create report-{index}.txt with the analysis to code_agent. "
                    "The CSV is in your workspace. Use tools to read the data; use create_file for the report."
                )
            else:
                request = {"task_type": "complex", "parameters": {
                    "data_agent": {"operation": "analyze_csv", "path": "sales.csv", "column": "revenue"},
                    "code_agent": {"operation": "create_file", "filename": f"report-{index}.txt",
                                   "content": "Q3 fixture: 100 + 150 + 250 = 500"}}}
            tick = perf_counter()
            try:
                result = await system.process(request, timeout=args.timeout)
                status = result["status"]
                record = {"request": index, "status": status, "errors": result.get("errors", [])}
            except Exception as exc:
                status = "error"
                record = {"request": index, "status": status, "error": redact(str(exc))}
            latency = perf_counter() - tick
            latencies.append(latency)
            record["latency_seconds"] = latency
            records.append(record)
            print(f"Request {index + 1}/{args.requests}: status={status} latency={latency:.3f}s", flush=True)
        duration = perf_counter() - started
        totals = {field: sum(entry.get(field, 0) for entry in usage.usage_metadata.values())
                  for field in ("input_tokens", "output_tokens", "total_tokens")}
        errors = sum(record["status"] != "success" for record in records)
        p50, p99 = percentile(latencies, 50), percentile(latencies, 99)
        throughput = args.requests * 60 / duration
        utilization = {worker.name: {"calls": worker.calls, "busy_seconds": worker.busy_seconds,
                                    "percent": worker.busy_seconds / duration * 100} for worker in workers}
        estimated_tokens = totals["total_tokens"] / args.requests * 100
        return {"mode": "live" if args.live else "local_no_model", "requests": args.requests,
                "wall_seconds": duration, "latency_p50_seconds": p50, "latency_p99_seconds": p99,
                "throughput_requests_per_minute": throughput, "worker_utilization": utilization,
                "successful_throughput_requests_per_minute": (args.requests - errors) * 60 / duration,
                "error_rate_percent": errors / args.requests * 100, "token_usage": totals,
                "token_usage_by_model": usage.usage_metadata, "tokens_per_100_requests_projected": estimated_tokens,
                "targets": {"p50_below_5s": p50 < 5, "p99_below_15s": p99 < 15,
                            "throughput_above_10_per_minute": throughput > 10,
                            "worker_utilization_70_to_90_percent": all(70 <= entry["percent"] <= 90 for entry in utilization.values()),
                            "error_rate_below_1_percent": errors / args.requests < .01,
                            "tokens_at_most_150k_per_100": estimated_tokens <= 150000 if args.live else None},
                "records": records,
                "notes": ["Five default sequential samples; P99 is an interpolated estimate, not a reliable tail latency.",
                          "Latency includes failed requests; throughput counts completed attempts, not only successes.",
                          "Worker utilization measures awaited processing time, including I/O/model waits; not CPU utilization.",
                          "cProfile covers the main event-loop thread; worker threads and REPL child processes are excluded.",
                          "Local mode has no model calls; do not compare its speed/token usage to LLM performance."]}
    finally:
        for worker in underlying:
            if hasattr(worker, "close"):
                worker.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--live", action="store_true", help="Use configured LLM for coordinator/workers; consumes tokens")
    args = parser.parse_args()
    if args.requests < 1 or args.timeout <= 0:
        parser.error("requests and timeout must be positive")
    directory = Path("results/profiling") / str(uuid.uuid4())
    directory.mkdir(parents=True)
    configure_logging(directory / "logs")
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        metrics = asyncio.run(run_system(args, directory))
    finally:
        profiler.disable()
        profiler.dump_stats(str(directory / "profile.prof"))
    with (directory / "top20.txt").open("w", encoding="utf-8") as stream:
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(20)
    (directory / "metrics.json").write_text(redact(json.dumps(metrics, ensure_ascii=False, indent=2)), encoding="utf-8")
    print(json.dumps({key: value for key, value in metrics.items() if key not in ("records", "token_usage_by_model")}, indent=2))
    pstats.Stats(profiler).sort_stats("cumulative").print_stats(20)
    print(f"Artifacts: {directory}")


if __name__ == "__main__":
    main()
