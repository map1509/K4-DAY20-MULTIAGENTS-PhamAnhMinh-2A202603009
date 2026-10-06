"""Offline end-to-end checks; run from the repository root."""
import asyncio
import json
import logging
from time import perf_counter
from types import SimpleNamespace

from coordinator import Coordinator
from base_agent import BaseAgent


class MockModel:
    """Deterministic fixture responses for the three example requests."""
    def invoke(self, prompt):
        request = json.loads(prompt.split("user data: ", 1)[1])
        kinds = {"Analyze sales data": "data_analysis",
                 "Analyze AND create report": "complex", "Long task": "data_analysis"}
        return SimpleNamespace(content=json.dumps({"task_type": kinds[request],
                                                   "parameters": {}, "priority": "normal"}))


class MockWorker(BaseAgent):
    def __init__(self, name, kind, delay=0):
        super().__init__(name)
        self.name, self.kind, self.delay = name, kind, delay

    async def process_async(self, content):
        await asyncio.sleep(self.delay)
        return {"type": self.kind, "content": {"mock": True, "request": content}}


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("Testing Coordinator with mock workers (no model API)...")
    coordinator = Coordinator(model=MockModel(), worker_agents=[MockWorker("data_agent", "data"), MockWorker("code_agent", "code")])
    request = "Analyze sales data"
    parsed = coordinator.parse_request(request)
    routed = coordinator.route_task(parsed["task_type"], request)
    result = coordinator.process(request)
    assert result["status"] == "success"
    assert parsed["task_type"] == "data_analysis" and routed == ["data_agent"]
    assert result["data"]["request"]["request"] == request
    print(f'\nTest 1: Simple task\n  Input: "{request}"\n  Parsed: task_type={parsed["task_type"]}\n  Routed to: {", ".join(routed)}\n  Result: mock data returned\n  PASS')
    request = "Analyze AND create report"
    started = perf_counter()
    result = coordinator.process(request)
    elapsed = perf_counter() - started
    assert result["status"] == "success" and result["data"] and result["code"]
    assert {record["worker"] for record in result["results"]} == {"data_agent", "code_agent"}
    print(f'\nTest 2: Multiple tasks\n  Input: "{request}"\n  Routed to: data_agent, code_agent\n  Results: both returned in {elapsed:.3f}s\n  PASS')
    slow = Coordinator(model=MockModel(), worker_agents=[MockWorker("data_agent", "data", delay=10)])
    result = slow.process("Long task", timeout=0.02)
    assert result["status"] == "error" and result["errors"][0]["status"] == "timeout"
    assert not slow.active_tasks
    # Explicit application-level fallback; the coordinator reports the timeout.
    fallback = coordinator.process("Long task")
    assert fallback["status"] == "success" and fallback["data"]["mock"]
    print('\nTest 3: Timeout handling\n  Input: "Long task"\n  Timeout after 0.02s\n  Pending task cancelled\n  Fallback: fast mock worker returned data\n  PASS')
    print("\nAll coordinator tests passed! (3/3)")


if __name__ == "__main__":
    main()
