"""Shared task validation, tool dispatch and worker error handling."""
import asyncio
import inspect
import json
from contextvars import ContextVar
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter

from base_agent import BaseAgent
from coordinator import WorkerError
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool


def make_tools(tool_map):
    """Expose existing Python tools with schemas for model tool calling."""
    tools = []
    for name, function in tool_map.items():
        if inspect.iscoroutinefunction(function):
            def synchronous(_function=function, **kwargs):
                return asyncio.run(_function(**kwargs))
            synchronous.__signature__ = inspect.signature(function)
            synchronous.__annotations__ = dict(function.__annotations__)
            tool = StructuredTool.from_function(func=synchronous, coroutine=function, name=name,
                                                description=f"{name}: {function.__doc__ or 'Execute the named worker operation.'}")
        else:
            tool = StructuredTool.from_function(func=function, name=name,
                                                description=f"{name}: {function.__doc__ or 'Execute the named worker operation.'}")
        tools.append(tool)
    return tools


class BaseWorker(BaseAgent):
    result_type = None

    def __init__(self, name, model=None, tools=(), *, result_type=None,
                 system_prompt=None, tool_map=None, workspace=".", max_iterations=10):
        if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")
        tools = list(tools)
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ValueError("Tool names must be unique")
        super().__init__(name, model=model, system_prompt=system_prompt, tools=tools)
        self.tools = {tool.name: tool for tool in tools}
        self.result_type = result_type
        self.tool_map = dict(tool_map or {})
        self.max_iterations = max_iterations
        self._tool_history = ContextVar(f"{name}_tools", default=None)
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")

    @property
    def _executed_tools(self):
        return self._tool_history.get() or []

    def _build_prompt(self, task_content, parameters=None):
        if isinstance(task_content, Mapping) and "request" in task_content:
            parameters = parameters if parameters is not None else task_content.get("parameters", {})
            upstream = task_content.get("upstream_data")
            task_content = str(task_content["request"]) + (f"\nVerified upstream_data: {json.dumps(upstream, default=str)}" if upstream is not None else "")
        return (f"Task: {task_content}\n"
                f"Parameters: {json.dumps(parameters or {}, ensure_ascii=False, default=str)}\n"
                f"Available tools: {list(self.tools)}")

    def _execute_tool(self, tool_name, tool_input):
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        try:
            result = self.tools[tool_name].invoke(tool_input)
            history = self._tool_history.get()
            if history is not None:
                history.append(tool_name)
            return result
        except Exception:
            self.logger.exception("Tool %s failed", tool_name)
            raise

    def process(self, task_content, parameters=None):
        """Bounded model/tool loop with full conversation and structured errors."""
        token = self._tool_history.set([])
        started = perf_counter()
        try:
            if self.model is None:
                raise ValueError("process requires a model; use process_async for offline operations")
            if not isinstance(task_content, (str, Mapping)) or not task_content:
                raise ValueError("task_content must be nonempty text or mapping")
            if parameters is not None and not isinstance(parameters, Mapping):
                raise ValueError("parameters must be a mapping")
            prompt = self._build_prompt(task_content, parameters)
            messages = [SystemMessage(content=self.system_prompt or ""), HumanMessage(content=prompt)]
            model = self.model
            offered_tools = list(self.tools.values())
            if self.name == "data_agent" and ".csv" in prompt.lower():
                offered_tools = [tool for tool in offered_tools if tool.name not in ("query_sql", "query_database")]
            if self.tools and callable(getattr(model, "bind_tools", None)):
                model = model.bind_tools(offered_tools)
            completed = {}
            for iteration in range(self.max_iterations + 1):
                self.logger.debug("Model invocation iteration=%s", iteration)
                response = model.invoke(messages)
                calls = getattr(response, "tool_calls", None) or []
                if not calls:
                    value = response.content
                    return {"status": "success", "result": value,
                            "metadata": {"tools_used": len(self._executed_tools),
                                         "tool_names": list(self._executed_tools)},
                            "type": self.result_type, "content": value}
                if iteration == self.max_iterations:
                    raise WorkerError("Agentic loop iteration limit exceeded")
                # Support the sample's `input` as well as LangChain's `args`.
                normalized = []
                for index, call in enumerate(calls):
                    args = call.get("args", call.get("input", {}))
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must be an object")
                    normalized.append({"name": call["name"], "args": args,
                                       "id": call.get("id") or f"call-{iteration}-{index}"})
                messages.append(AIMessage(content=response.content or "", tool_calls=normalized))
                for call in normalized:
                    self.logger.debug("Tool call name=%s id=%s", call["name"], call["id"])
                    signature = json.dumps([call["name"], call["args"]], sort_keys=True)
                    if signature in completed:
                        raise WorkerError("Repeated tool call without progress")
                    if call["name"] not in self.tools:
                        raise ValueError(f"Unknown tool: {call['name']}")
                    if call["name"] not in {tool.name for tool in offered_tools}:
                        raise WorkerError("Tool is not appropriate for this task's file type")
                    result = self._execute_tool(call["name"], call["args"])
                    completed[signature] = result
                    messages.append(ToolMessage(content=json.dumps(result, ensure_ascii=False, default=str),
                                                tool_call_id=call["id"], name=call["name"]))
                    if isinstance(result, Mapping) and result.get("status") == "error":
                        continue
                    # Atomic analysis/report/scoring operations already have verified structured output.
                    terminal = {"analyze_csv", "pandas_analysis", "query_database", "query_sql", "create_file", "score", "score_result", "quality_check"}
                    if len(normalized) == 1 and call["name"] in terminal:
                        return {"status": "success", "result": json.dumps(result, ensure_ascii=False, default=str),
                                "type": self.result_type, "content": result,
                                "metadata": {"tools_used": len(self._executed_tools), "tool_names": list(self._executed_tools)}}
            raise WorkerError("Agentic loop iteration limit exceeded")
        except Exception as exc:
            self.logger.error("Worker %s failed: %s", self.name, exc)
            return {"status": "error", "error": str(exc), "result": None,
                    "metadata": {"tools_used": len(self._executed_tools)},
                    "type": self.result_type, "content": None}
        finally:
            self.logger.info("Worker %s end duration=%.3fs", self.name, perf_counter() - started)
            self._tool_history.reset(token)

    def resolve_path(self, path):
        if not isinstance(path, str) or not path:
            raise ValueError("path must be a nonempty relative string")
        relative = Path(path)
        if relative.is_absolute() or relative.drive:
            raise ValueError("path must be relative to workspace")
        resolved = (self.workspace / relative).resolve()
        if not resolved.is_relative_to(self.workspace):
            raise ValueError("path escapes workspace")
        return resolved

    async def process_async(self, content, parameters=None):
        """Accept {operation, ...} or coordinator's {parameters: {...}}.

        Sync tools run in a thread. Cancelling the await cannot forcibly stop a
        thread already running; Python execution uses a cancellable subprocess.
        No model is called by this deterministic offline worker implementation.
        """
        planned = content.get("parameters", content) if isinstance(content, Mapping) else None
        explicit_operation = (isinstance(planned, Mapping) and isinstance(planned.get("operation"), str)
                              and planned["operation"] in self.tool_map)
        if self.model is not None and not explicit_operation:
            return await asyncio.to_thread(self.process, content, parameters)
        if parameters is not None:
            content = {"request": content, "parameters": parameters}
        started = perf_counter()
        operation = None
        self.logger.info("Worker %s start", self.name)
        try:
            if not isinstance(content, Mapping):
                raise ValueError("Worker content must be a mapping")
            params = content.get("parameters", content)
            if not isinstance(params, Mapping):
                raise ValueError("parameters must be a mapping")
            # Complex requests can provide separate parameter dictionaries per worker.
            params = params.get(self.name, params)
            if not isinstance(params, Mapping):
                raise ValueError("worker parameters must be a mapping")
            params = dict(params)
            operation = params.pop("operation", None)
            if not isinstance(operation, str) or operation not in self.tool_map:
                raise ValueError(f"operation must be one of {', '.join(self.tool_map)}")
            tool = self.tool_map[operation]
            if inspect.iscoroutinefunction(tool):
                result = await tool(**params)
            else:
                result = await asyncio.to_thread(tool, **params)
            if isinstance(result, Mapping) and result.get("status") == "error":
                raise WorkerError(result.get("error", "Tool failed"))
            self.logger.info("Worker %s result type=%s operation=%s", self.name, self.result_type, operation)
            return {"type": self.result_type, "content": result}
        except Exception as exc:
            self.logger.error("Worker %s operation=%s failed: %s", self.name, operation, exc)
            raise WorkerError(f"{self.name}/{operation}: {exc}") from exc
        finally:
            self.logger.info("Worker %s end duration=%.3fs", self.name, perf_counter() - started)
