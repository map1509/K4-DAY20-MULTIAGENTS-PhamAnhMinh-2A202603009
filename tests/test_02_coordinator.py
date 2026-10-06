import asyncio
from types import SimpleNamespace

import pytest

from lab.coordinator import Coordinator, CoordinatorException


class MockWorker:
    def __init__(self, name="data_agent", kind="data", delay=0, fail=0):
        self.name, self.kind, self.delay, self.fail = name, kind, delay, fail
        self.calls = 0
        self.cancelled = False

    async def process_async(self, content):
        self.calls += 1
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.calls <= self.fail:
            raise RuntimeError("mock failure")
        return {"type": self.kind, "content": content}


def task(name="data_agent", tid="one"):
    return {"id": tid, "worker": name, "content": {"sales": 5}}


def test_coordinator_init():
    worker = MockWorker()
    queue = asyncio.Queue()
    coordinator = Coordinator(worker_agents=[worker], message_queue=queue)
    assert coordinator.workers == {"data_agent": worker}
    assert coordinator.task_queue is queue
    with pytest.raises(ValueError):
        Coordinator(worker_agents=[worker, worker])


def test_parse_request():
    coordinator = Coordinator()
    assert coordinator.parse_request({"task_type": "data_analysis"})["priority"] == "normal"
    class Model:
        def invoke(self, prompt):
            return SimpleNamespace(content='{"task_type":"complex","parameters":{"quarter":3},"priority":"high"}')
    assert Coordinator(model=Model()).parse_request("Analyze and plot Q3")["parameters"] == {"quarter": 3}
    for invalid in ("", "[]", {"task_type": "unknown"}, {"task_type": "data_analysis", "parameters": []}):
        with pytest.raises(CoordinatorException):
            coordinator.parse_request(invalid)


def test_route_task():
    coordinator = Coordinator(worker_agents=[MockWorker(), MockWorker("code_agent", "code")])
    assert coordinator.route_task("complex") == ["data_agent", "code_agent"]
    with pytest.raises(CoordinatorException):
        coordinator.route_task("evaluation")
    with pytest.raises(CoordinatorException):
        coordinator.route_task("unknown")


def test_execute_tasks():
    async def scenario():
        entered = 0
        ready = asyncio.Event()
        class ParallelWorker(MockWorker):
            async def process_async(self, content):
                nonlocal entered
                entered += 1
                if entered == 2:
                    ready.set()
                await ready.wait()
                return {"type": self.kind, "content": content}
        coordinator = Coordinator(worker_agents=[ParallelWorker(), ParallelWorker("code_agent", "code")])
        records = await coordinator.aexecute_tasks([task(), task("code_agent", "two")], timeout=1)
        assert all(record["status"] == "success" for record in records.values())
        assert coordinator.active_tasks == {}
        with pytest.raises(CoordinatorException, match="async API"):
            coordinator.execute_tasks([task()])
    asyncio.run(scenario())


def test_aggregate_results():
    coordinator = Coordinator()
    result = coordinator.aggregate_results([
        {"type": "data", "content": {"total": 5}},
        {"type": "data", "content": {"total": 6}},
        {"type": "code", "content": "chart.png"},
        {"status": "timeout", "id": "three", "error": "deadline"},
    ])
    assert result["status"] == "partial"
    assert result["data"] == [{"total": 5}, {"total": 6}]
    assert result["code"] == "chart.png"


def test_timeout_error_and_cleanup():
    slow = MockWorker(delay=10)
    failed = MockWorker("code_agent", "code", fail=10)
    coordinator = Coordinator(worker_agents=[slow, failed])
    results = coordinator.execute_tasks([task(), task("code_agent", "two")], timeout=0.02)
    assert results["one"]["status"] == "timeout"
    assert results["two"]["status"] == "error"
    assert slow.cancelled and not coordinator.active_tasks
    assert coordinator.aggregate_results(results)["status"] == "error"


def test_retry_preserves_success_and_exhaustion():
    worker, flaky = MockWorker(), MockWorker("code_agent", "code", fail=1)
    coordinator = Coordinator(worker_agents=[worker, flaky])
    results = coordinator.execute_tasks_with_retry([task(), task("code_agent", "two")])
    assert worker.calls == 1 and flaky.calls == 2
    assert results["two"]["attempts"] == 2
    failed = Coordinator(worker_agents=[MockWorker(fail=10)])
    with pytest.raises(CoordinatorException, match="exhausted") as exc:
        failed.execute_tasks_with_retry([task()], max_retries=1)
    assert exc.value.results["one"]["attempts"] == 2


def test_invalid_batch_and_resource_limit():
    worker = MockWorker()
    coordinator = Coordinator(worker_agents=[worker], max_tasks=1)
    for tasks in ([task(), task(tid="two")], [{"id": "one", "worker": "missing", "content": "x"}]):
        with pytest.raises(CoordinatorException):
            coordinator.execute_tasks(tasks)
    with pytest.raises(ValueError):
        coordinator.execute_tasks([task()], timeout=float("nan"))
    assert worker.calls == 0


def test_caller_cancellation():
    async def scenario():
        worker = MockWorker(delay=10)
        coordinator = Coordinator(worker_agents=[worker])
        running = asyncio.create_task(coordinator.aexecute_tasks([task()]))
        while not worker.calls:
            await asyncio.sleep(0)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert worker.cancelled and not coordinator.active_tasks
    asyncio.run(scenario())


def test_end_to_end():
    coordinator = Coordinator(worker_agents=[MockWorker(), MockWorker("code_agent", "code")])
    result = coordinator.process({"task_type": "complex", "parameters": {"quarter": 3}})
    assert result["status"] == "success"
    assert result["data"]["parameters"] == {"quarter": 3}
    assert result["code"]["request"]["task_type"] == "complex"
