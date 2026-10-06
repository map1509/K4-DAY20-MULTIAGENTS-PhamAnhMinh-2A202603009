import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from agents.base_worker import BaseWorker
from agents import CodeAgent, DataAgent, EvaluatorAgent
from coordinator import Coordinator


class FakeModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.messages = []
        self.bound = []

    def bind_tools(self, tools):
        self.bound = tools
        return self

    def invoke(self, messages):
        self.messages.append(list(messages))
        return self.replies.pop(0)


def plus(value: int) -> int:
    """Add one to a number."""
    return value + 1


def worker(model, **kwargs):
    return BaseWorker("worker", model, [StructuredTool.from_function(plus)],
                      result_type="data", system_prompt="Test specialist", **kwargs)


def test_base_worker_multiple_calls_and_history():
    model = FakeModel([
        AIMessage(content="", tool_calls=[{"name": "plus", "args": {"value": 1}, "id": "a"},
                                          {"name": "plus", "args": {"value": 2}, "id": "b"}]),
        AIMessage(content="", tool_calls=[{"name": "plus", "args": {"value": 3}, "id": "c"}]),
        AIMessage(content="Done"), AIMessage(content="Second task")])
    agent = worker(model)
    result = agent.process("Add numbers", {"limit": 3})
    assert result["status"] == "success" and result["result"] == "Done"
    assert result["metadata"]["tools_used"] == 3
    assert [message.content for message in model.messages[2] if isinstance(message, ToolMessage)] == ["2", "3", "4"]
    assert model.bound[0].name == "plus"
    assert agent.process("Another task")["metadata"]["tools_used"] == 0


def test_sample_input_format_and_async():
    model = FakeModel([SimpleNamespace(content="", tool_calls=[{"name": "plus", "input": {"value": 4}}]),
                       AIMessage(content="5")])
    result = asyncio.run(worker(model).process_async("Add one", {"value": 4}))
    assert result["result"] == "5" and result["metadata"]["tools_used"] == 1


def test_unknown_tool_and_model_error():
    model = FakeModel([AIMessage(content="", tool_calls=[{"name": "missing", "args": {}, "id": "a"}])])
    result = worker(model).process("Task")
    assert result["status"] == "error" and "Unknown tool" in result["error"]
    result = worker(FakeModel([])).process("Task")
    assert result["status"] == "error" and result["result"] is None


def test_tool_failure_and_iteration_limit():
    def fail() -> str:
        """Always fail."""
        raise ValueError("Tool failed")
    agent = BaseWorker("worker", FakeModel([AIMessage(content="", tool_calls=[{"name": "fail", "args": {}, "id": "a"}])]),
                       [StructuredTool.from_function(fail)])
    assert "Tool failed" in agent.process("Task")["error"]
    call = AIMessage(content="", tool_calls=[{"name": "plus", "args": {"value": 1}, "id": "a"}])
    result = worker(FakeModel([call, call]), max_iterations=1).process("Loop")
    assert result["status"] == "error" and "iteration limit" in result["error"]
    assert result["metadata"]["tools_used"] == 1


def test_specialist_model_loop_and_coordinator(tmp_path):
    (tmp_path / "sales.csv").write_text("amount\n2\n3\n", encoding="utf-8")
    model = FakeModel([AIMessage(content="", tool_calls=[{"name": "analyze_csv", "args": {
        "path": "sales.csv", "column": "amount"}, "id": "data"}]), AIMessage(content="Sales total: 5")])
    agent = DataAgent(model, workspace=tmp_path)
    result = Coordinator(worker_agents=[agent]).process({"task_type": "data_analysis"})
    assert result["status"] == "success" and result["data"]["value"] == 5
    assert len(model.messages) == 1
    assert CodeAgent(FakeModel([]), workspace=tmp_path).system_prompt
    assert EvaluatorAgent(FakeModel([]), workspace=tmp_path).tools


def test_worker_error_not_treated_as_success(tmp_path):
    agent = DataAgent(FakeModel([]), workspace=tmp_path)
    result = Coordinator(worker_agents=[agent]).process({"task_type": "data_analysis"})
    assert result["status"] == "error"


def test_specialized_tools(tmp_path):
    (tmp_path / "sales.csv").write_text("category,amount\na,2\na,3\nb,4\n", encoding="utf-8")
    data = DataAgent(workspace=tmp_path)
    assert data.tools["pandas_analysis"].invoke({"path": "sales.csv", "column": "amount", "group_by": "category"})["rows"] == [
        {"category": "a", "amount": 5}, {"category": "b", "amount": 4}]
    assert data.tools["csv_parser"].invoke({"path": "sales.csv", "max_rows": 1})["truncated"]
    assert not data.tools["data_validation"].invoke({"rows": [{}], "required_columns": ["amount"]})["valid"]
    evaluator = EvaluatorAgent(workspace=tmp_path)
    scored = evaluator.tools["quality_check"].invoke({"criteria": {
        "accuracy": 100, "completeness": 100, "clarity": 50, "performance": 50}})
    assert scored["score"] == 80
    feedback = evaluator.tools["feedback_generator"].invoke({"score": 80, "issues": ["slow"], "suggestions": ["optimize"]})
    assert feedback["issues"] == ["slow"]
    code = CodeAgent(workspace=tmp_path)
    code.tools["write_file"].invoke({"path": "hello.py", "code": "print(5)"})
    assert code.tools["run_script"].invoke({"path": "hello.py"})["stdout"].strip() == "5"
