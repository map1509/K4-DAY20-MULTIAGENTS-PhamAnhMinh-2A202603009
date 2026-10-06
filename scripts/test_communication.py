"""Offline coordinator/worker communication check for Part 3."""
import asyncio
import json

from base_agent import BaseAgent
from communication import MessageQueue
from coordinator import Coordinator


class MockWorker(BaseAgent):
    def __init__(self, name, kind, delay=0, fail=False):
        super().__init__(name)
        self.kind, self.delay, self.fail = kind, delay, fail

    async def process_async(self, content, parameters=None):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise ValueError("mock worker error")
        return {"type": self.kind, "content": {"text": content, "parameters": parameters}}


async def main():
    queue = MessageQueue()
    queue.register_agent("data_agent")
    payload = {"type": "task", "content": "hello"}
    mid = await queue.send_message("coordinator", "data_agent", payload)
    assert "id" not in payload
    received = await queue.receive_message("data_agent", message_id=mid)
    assert received["from"] == "coordinator" and received["to"] == "data_agent"
    assert received["timestamp"] and received["id"] == mid
    try:
        await queue.receive_message("data_agent", timeout=.01)
    except TimeoutError:
        pass
    else:
        raise AssertionError("Empty mailbox must time out")
    try:
        await queue.send_message("coordinator", "missing", {})
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown recipient must fail")
    print("MessageQueue: send/receive, metadata, timeout and logging PASS")
    coordinator = Coordinator(worker_agents=[MockWorker("data_agent", "data", .03),
                                              MockWorker("code_agent", "code")], message_queue=queue)
    results = await coordinator.aexecute_tasks([
        {"id": "data", "worker": "data_agent", "content": "sales", "parameters": {"quarter": 3}},
        {"id": "code", "worker": "code_agent", "content": "report"}], timeout=1)
    assert results["data"]["result"]["content"] == {"text": "sales", "parameters": {"quarter": 3}}
    assert results["code"]["result"]["content"]["text"] == "report"
    replies = [message for message in queue.get_message_log() if message["type"] == "result"]
    assert [message["task_id"] for message in replies] == ["code", "data"]
    assert all(message["in_reply_to"] for message in replies)
    assert all(queue.queues[name].empty() for name in queue.queues)
    print("Coordinator <-> workers: parallel dispatch and correct result correlation PASS")
    failing = Coordinator(worker_agents=[MockWorker("data_agent", "data", fail=True)])
    result = await failing.aexecute_tasks([{"id": "error", "worker": "data_agent", "content": "fail"}])
    assert result["error"]["status"] == "error"
    slow = Coordinator(worker_agents=[MockWorker("data_agent", "data", delay=10)])
    result = await slow.aexecute_tasks([{"id": "timeout", "worker": "data_agent", "content": "slow"}], timeout=.02)
    assert result["timeout"]["status"] == "timeout" and not slow.active_tasks
    print("Worker errors and timeout cleanup PASS")
    json.dumps(queue.get_message_log())
    assert queue.get_message_log("code_agent")
    print("All communication checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
