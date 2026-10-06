"""Part 5.1: five requested tests; offline model, real queue/workers/tools."""
import asyncio
import json
from time import perf_counter
from types import SimpleNamespace

import pytest

from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator
from system import MultiAgentSystem
from langchain_core.messages import AIMessage
from lab.testing import ScriptedChatModel


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


def test_script_is_written_and_executed_in_one_model_call(tmp_path):
    model = ScriptedChatModel(script=[AIMessage(content="", tool_calls=[{
        "name": "write_and_run_script", "args": {"path": "answer.py", "code": "print(500)"}, "id": "write-test"}])])
    worker = CodeAgent(model, workspace=tmp_path)
    result = asyncio.run(worker.process_async("Write Python script answer.py and test it"))
    assert result["status"] == "success"
    assert result["content"]["tested"] and result["content"]["stdout"].strip() == "500"
    assert (tmp_path / "answer.py").read_text() == "print(500)"
    assert model.calls == 1


def test_explicit_routing_keeps_model_for_offline_worker_parameters(tmp_path):
    class NoCalls:
        def invoke(self, prompt):
            raise AssertionError("Unnecessary coordinator model call")
    model = NoCalls()
    workers = [DataAgent(model, workspace=tmp_path), CodeAgent(model, workspace=tmp_path)]
    coord = Coordinator(model, workers)
    assert coord.parse_request("Analyze sales AND create chart")['task_type'] == "complex"
    assert coord.parse_request("Write Python script to read CSV")['task_type'] == "code_generation"
    offline = Coordinator(RoutingModel(), [DataAgent(workspace=tmp_path), CodeAgent(workspace=tmp_path)])
    assert offline.parse_request("Calculate revenue and create chart")["parameters"]["data_agent"]["operation"] == "analyze_csv"


def test_logging_redacts_nested_secrets_and_reconfiguration(tmp_path, monkeypatch):
    import logging
    from logging_config import configure_logging, refresh_redaction
    secret = "synthetic-private-value-for-test"
    monkeypatch.setenv("LAB_API_KEY", secret)
    names = ("coordinator", "communication", "data_agent", "code_agent", "evaluator_agent", "system",
             "query_database", "python_repl", "create_file", "score_result")
    previous = {name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level,
                       logging.getLogger(name).propagate) for name in names}
    try:
        configure_logging(tmp_path / "first")
        configure_logging(tmp_path / "second")
        logging.getLogger("coordinator").error("Worker error %s", secret)
        logging.getLogger("communication").info(json.dumps({"message": {
            "api_key": secret, "nested": [secret, {"text": "sk-synthetic-key", "count": 3}]}}))
        text = (tmp_path / "second/coordinator.log").read_text(encoding="utf-8")
        envelope = (tmp_path / "second/communication.log").read_text(encoding="utf-8")
        assert secret not in text + envelope and "sk-synthetic-key" not in envelope
        assert json.loads(envelope)["message"]["nested"][1]["count"] == 3
        assert len([h for h in logging.getLogger("communication").handlers if getattr(h, "multi_agent_debug", False)]) == 1
    finally:
        for name, (handlers, level, propagate) in previous.items():
            logger = logging.getLogger(name)
            for handler in list(logger.handlers):
                if handler not in handlers:
                    logger.removeHandler(handler)
                    handler.close()
            logger.handlers = handlers
            logger.setLevel(level)
            logger.propagate = propagate
        monkeypatch.undo()
        refresh_redaction()


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
