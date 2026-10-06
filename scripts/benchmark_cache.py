"""Bonus 6c: compare identical local CSV requests, no model/API calls."""
import asyncio
import json
from pathlib import Path
from time import perf_counter
import uuid
from agents import DataAgent
from coordinator import Coordinator, CachingCoordinator


async def main():
    directory = Path("results/caching") / str(uuid.uuid4())
    directory.mkdir(parents=True)
    (directory / "sales.csv").write_text("revenue\n" + "1\n" * 10000, encoding="utf-8")
    request = {"task_type": "data_analysis", "parameters": {
        "operation": "analyze_csv", "path": "sales.csv", "column": "revenue"}}
    results = {"mode": "local_no_model", "requests_per_mode": 20, "modes": {}}
    for name, kind in (("uncached", Coordinator), ("cached", CachingCoordinator)):
        coord = kind(worker_agents=[DataAgent(workspace=directory)])
        started = perf_counter()
        for _ in range(20):
            result = await coord.handle_request(request)
            assert result["status"] == "success" and result["data"]["value"] == 10000
        elapsed = perf_counter() - started
        results["modes"][name] = {"seconds": elapsed, "average_seconds": elapsed / 20,
                                  "requests_per_minute": 1200 / elapsed,
                                  "task_messages": sum(m["type"] == "task" for m in coord.task_queue.get_message_log())}
        if name == "cached":
            results["modes"][name]["cache_stats"] = coord.cache_stats
    results["note"] = "Local CSV workload only; first cold cache miss included; no claim about live LLM throughput."
    (directory / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Artifacts: {directory}")


if __name__ == "__main__":
    asyncio.run(main())
