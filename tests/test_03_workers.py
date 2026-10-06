import json
from langchain_core.messages import AIMessage
from lab.testing import ScriptedChatModel

from agents import CodeAgent, DataAgent, EvaluatorAgent


def test_data_agent_init(tmp_path):
    model = ScriptedChatModel(script=[AIMessage(content="Ready")])
    agent = DataAgent(model, workspace=tmp_path)
    assert agent.name == "data_agent" and agent.model is model
    assert agent.system_prompt
    assert {"query_database", "pandas_analysis", "csv_parser", "data_validation"} <= agent.tools.keys()


def test_data_agent_process(tmp_path):
    (tmp_path / "sales.csv").write_text("amount\n2\n3\n", encoding="utf-8")
    model = ScriptedChatModel(script=[
        AIMessage(content="", tool_calls=[{"name": "analyze_csv", "args": {
            "path": "sales.csv", "column": "amount"}, "id": "sales"}]),
        AIMessage(content="Sales total: 5")])
    result = DataAgent(model, workspace=tmp_path).process("Analyze sales")
    assert result["status"] == "success" and result["result"] == "Sales total: 5"
    assert result["metadata"]["tool_names"] == ["analyze_csv"]


def test_code_agent_process(tmp_path):
    model = ScriptedChatModel(script=[
        AIMessage(content="", tool_calls=[{"name": "write_file", "args": {
            "path": "report.py", "code": "print(5)"}, "id": "write"}]),
        AIMessage(content="", tool_calls=[{"name": "run_script", "args": {
            "path": "report.py"}, "id": "test"}]),
        AIMessage(content="Created and tested report.py; output: 5")])
    result = CodeAgent(model, workspace=tmp_path).process("Create and test a report")
    assert result["status"] == "success"
    assert (tmp_path / "report.py").read_text() == "print(5)"
    assert result["metadata"]["tool_names"] == ["write_file", "run_script"]


def test_evaluator_agent(tmp_path):
    model = ScriptedChatModel(script=[
        AIMessage(content="", tool_calls=[{"name": "quality_check", "args": {"criteria": {
            "accuracy": 100, "completeness": 100, "clarity": 50, "performance": 50}}, "id": "score"}]),
        AIMessage(content='{"score":80,"feedback":"Improve clarity","issues":["clarity"],"suggestions":["Explain results"]}')])
    result = EvaluatorAgent(model, workspace=tmp_path).process("Evaluate supplied criteria")
    assert result["status"] == "success"
    assert json.loads(result["result"])["score"] == 80
    assert result["metadata"]["tool_names"] == ["quality_check"]
