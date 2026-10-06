"""User request through coordinator/workers, followed by result evaluation."""
import json
import uuid
import logging
from time import perf_counter

from coordinator import CoordinatorException


class MultiAgentSystem:
    def __init__(self, coordinator, workers):
        self.coordinator = coordinator
        for worker in workers:
            if coordinator.workers.get(worker.name) is not worker:
                raise ValueError("System workers must be registered with the coordinator")

    async def process(self, user_input, timeout=60, debug=False):
        import asyncio
        logger = logging.getLogger("system")
        started = perf_counter()
        if debug:
            logger.debug("Pipeline start timeout=%s", timeout)
        async def pipeline():
            result = await self.coordinator.handle_request(user_input, timeout)
            if result["status"] != "success" or result["evaluation"] is not None:
                return result
            if "evaluator_agent" not in self.coordinator.workers:
                raise CoordinatorException("Full pipeline requires evaluator_agent")
            # Deterministic checks establish output presence, not factual accuracy.
            checks = {"data_present": bool(result["data"]), "code_present": bool(result["code"])}
            requested_workers = {record["worker"] for record in result["results"]}
            expected = {key: True for key, worker in (("data_present", "data_agent"), ("code_present", "code_agent"))
                        if worker in requested_workers}
            if not expected:
                raise CoordinatorException("No worker output to evaluate")
            records = await self.coordinator.aexecute_tasks([{
                "id": str(uuid.uuid4()), "worker": "evaluator_agent",
                "content": {"parameters": {"operation": "score", "actual": checks, "expected": expected},
                            "request": json.dumps(result, ensure_ascii=False)}}], timeout)
            evaluated = self.coordinator.aggregate_results(records)
            result["evaluation"] = evaluated["evaluation"]
            result["results"].extend(evaluated["results"])
            result["errors"].extend(evaluated["errors"])
            if evaluated["status"] != "success":
                result["status"] = "partial"
            return result
        try:
            result = await asyncio.wait_for(pipeline(), timeout)
            logger.info("Pipeline end status=%s duration=%.3fs", result["status"], perf_counter() - started)
            return result
        except TimeoutError:
            logger.error("Pipeline timeout duration=%.3fs", perf_counter() - started)
            return {"status": "error", "data": {}, "code": None, "evaluation": None,
                    "errors": [{"status": "timeout", "error": "Full pipeline deadline exceeded"}]}
