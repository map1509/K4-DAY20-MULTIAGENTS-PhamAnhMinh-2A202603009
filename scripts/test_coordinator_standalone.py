"""Offline end-to-end checks; run from the repository root."""
import asyncio

from lab.coordinator import Coordinator


class MockWorker:
    def __init__(self, name, kind, delay=0):
        self.name, self.kind, self.delay = name, kind, delay

    async def process_async(self, content):
        await asyncio.sleep(self.delay)
        return {"type": self.kind, "content": {"mock": True, "request": content}}


def main():
    print("Testing Coordinator with mock workers (no model API)...")
    coordinator = Coordinator(worker_agents=[MockWorker("data_agent", "data"), MockWorker("code_agent", "code")])
    assert coordinator.process({"task_type": "data_analysis"})["status"] == "success"
    print("Test 1: Simple task PASS")
    result = coordinator.process({"task_type": "complex"})
    assert result["status"] == "success" and result["data"] and result["code"]
    print("Test 2: Multiple workers PASS")
    slow = Coordinator(worker_agents=[MockWorker("data_agent", "data", delay=10)])
    result = slow.process({"task_type": "data_analysis"}, timeout=0.02)
    assert result["status"] == "error" and result["errors"][0]["status"] == "timeout"
    assert not slow.active_tasks
    print("Test 3: Timeout and cleanup PASS")
    print("All coordinator tests passed! (3/3)")


if __name__ == "__main__":
    main()
