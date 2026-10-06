import asyncio
from types import SimpleNamespace

import pytest

from coordinator import Coordinator, CoordinatorException
from base_agent import BaseAgent


class MockWorker(BaseAgent):
    def __init__(self, name="data_agent", kind="data", delay=0, fail=0):
        super().__init__(name)
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
    with pytest.raises(TypeError):
        BaseAgent("abstract")
    assert worker.model is None and worker.tools == []


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


def test_retry_after_timeout(caplog):
    class SlowFirstWorker(MockWorker):
        async def process_async(self, content):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(10)
            return {"type": "data", "content": content}
    worker = SlowFirstWorker()
    coordinator = Coordinator(worker_agents=[worker])
    result = coordinator.execute_tasks_with_retry([task()], max_retries=1, timeout=0.02)
    assert result["one"]["status"] == "success"
    assert worker.calls == 2 and result["one"]["attempts"] == 2
    assert "timeout" in caplog.text
    assert not coordinator.active_tasks


def test_invalid_model_response():
    class InvalidModel:
        def invoke(self, prompt):
            return SimpleNamespace(content="not JSON")
    with pytest.raises(CoordinatorException, match="parse model response"):
        Coordinator(model=InvalidModel()).parse_request("Analyze sales")


def test_resource_limit_across_concurrent_batches():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        class WaitingWorker(MockWorker):
            async def process_async(self, content):
                self.calls += 1
                started.set()
                await release.wait()
                return {"type": "data", "content": content}
        worker = WaitingWorker()
        coordinator = Coordinator(worker_agents=[worker], max_tasks=1)
        running = asyncio.create_task(coordinator.aexecute_tasks([task()], timeout=1))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            with pytest.raises(CoordinatorException, match="Active task limit"):
                await coordinator.aexecute_tasks([task(tid="two")])
            assert worker.calls == 1
        finally:
            release.set()
            await running
        assert not coordinator.active_tasks
    asyncio.run(scenario())


def test_invalid_worker_output():
    class InvalidWorker(MockWorker):
        async def process_async(self, content):
            return {"content": "missing type"}
    coordinator = Coordinator(worker_agents=[InvalidWorker()])
    result = coordinator.execute_tasks([task()])
    assert result["one"]["status"] == "error"
    assert "WorkerError" in result["one"]["error"]
