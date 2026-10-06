"""Part 5.1: five requested tests; offline model, real queue/workers/tools."""
import asyncio
import json
from time import perf_counter
from types import SimpleNamespace

import pytest

from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator
from system import MultiAgentSystem


class RoutingModel:
    """Return a deterministic plan for fixture data, with no provider requests."""
    def invoke(self, prompt):
        request = json.loads(prompt.split("user data: ", 1)[1])
        kind = "data_analysis" if request == "Analyze sales data" or request == "Simple task" else "complex"
        parameters = {"operation": "analyze_csv", "path": "sales.csv", "column": "revenue"}
        if kind == "complex":
            parameters = {"data_agent": parameters, "code_agent": {
                "operation": "python_repl", "code": (
                    "import pandas as pd\nimport matplotlib.pyplot as plt\n"
                    "data = pd.read_csv('sales.csv')\nplt.figure()\n"
                    "plt.bar(data['month'], data['revenue'])\nplt.title('Q3 revenue')\n"
                    "plt.savefig('chart.png')\nplt.close()\nprint('chart.png created')")}}
        return SimpleNamespace(content=json.dumps({"task_type": kind, "parameters": parameters, "priority": "normal"}))


@pytest.fixture
def system(tmp_path):
    (tmp_path / "sales.csv").write_text("month,revenue\n7,100\n8,150\n9,250\n", encoding="utf-8")
    workers = [DataAgent(workspace=tmp_path), CodeAgent(workspace=tmp_path), EvaluatorAgent(workspace=tmp_path)]
    coordinator = Coordinator(model=RoutingModel(), worker_agents=workers)
    yield MultiAgentSystem(coordinator=coordinator, workers=workers)
    for worker in workers:
        if hasattr(worker, "close"):
            worker.close()


def test_coordinator_parse_request(system):
    result = system.coordinator.parse_request("Analyze sales data")
    assert result["task_type"] == "data_analysis"
    assert result["parameters"]["column"] == "revenue"


def test_coordinator_with_workers(system):
    response = asyncio.run(system.coordinator.handle_request("Calculate revenue and create chart"))
    assert response["status"] == "success"
    assert response["data"]["value"] == 500
    assert "chart.png" in response["code"]["stdout"]
    log = system.coordinator.task_queue.get_message_log()
    assert len([message for message in log if message["type"] == "task"]) == 2
    assert len([message for message in log if message["type"] == "result"]) == 2


def test_full_pipeline(system, tmp_path):
    result = asyncio.run(system.process("What was Q3 revenue? Create a visualization."))
    assert result["status"] == "success"
    assert result["data"]["value"] == 500
    assert (tmp_path / "chart.png").read_bytes().startswith(b"\x89PNG")
    assert result["evaluation"]["score"] == 1
    assert all(check["passed"] for check in result["evaluation"]["checks"])


def test_latency(system, record_property):
    start = perf_counter()
    result = asyncio.run(system.process("Simple task"))
    latency = perf_counter() - start
    assert result["status"] == "success"
    assert latency < 10
    record_property("latency_seconds", latency)
    print(f"Latency: {latency:.4f}s")


def test_concurrent_requests(system, record_property):
    async def scenario():
        start = perf_counter()
        # Read-only analysis requests avoid concurrent writes to the same artifact.
        results = await asyncio.gather(*(system.process("Simple task") for _ in range(10)))
        seconds = perf_counter() - start
        success = sum(result["status"] == "success" for result in results)
        assert success >= 8
        assert all(result["data"]["value"] == 500 for result in results if result["status"] == "success")
        assert not system.coordinator.active_tasks
        record_property("success_count", success)
        record_property("throughput_requests_per_second", len(results) / seconds)
        print(f"Concurrent: {success}/10 success; {seconds:.4f}s; throughput={len(results)/seconds:.2f} requests/s")
    asyncio.run(scenario())
