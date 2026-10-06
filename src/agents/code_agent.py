"""Python syntax, file creation/editing, and trusted script execution tools."""
import ast
import asyncio
import math
import os
import sys
from tools import PythonREPLTool, CreateFileTool, EditFileTool

from .base_worker import BaseWorker, make_tools


class CodeAgent(BaseWorker):
    SYSTEM_PROMPT = (
        "Work on Python code within the workspace. Check syntax before writing. "
        "Run only explicitly requested trusted code. ALWAYS test code before returning. "
        "Report actual files and execution results."
        " If upstream_data is provided, use that verified data; do not redo analysis. "
        "For a plain text report, use create_file(filename, content), then finish."
        " For charts, read the source CSV to obtain individual rows and execute matplotlib savefig. "
        "PNG files must be produced by matplotlib, never by create_file or write_file. "
        "After successful savefig, return the path immediately; do not recreate or overwrite the image."
        " When asked to create and test a Python script, use write_and_run_script in one call."
    )

    def __init__(self, model=None, *, workspace="."):
        self.repl_tool = PythonREPLTool(base_path=workspace)
        self.create_file_tool = CreateFileTool(base_path=workspace)
        self.edit_file_tool = EditFileTool(base_path=workspace)
        tool_map = {"validate_python": self.validate_python, "write_file": self.write_file,
                    "edit_file": self.edit_file, "execute_python": self.execute_python,
                    "run_script": self.run_script, "python_repl": self.python_repl,
                    "create_file": self.create_file}
        tool_map["write_and_run_script"] = self.write_and_run_script
        super().__init__("code_agent", model, make_tools(tool_map), result_type="code",
                         system_prompt=self.SYSTEM_PROMPT, tool_map=tool_map, workspace=workspace)

    def python_repl(self, code: str, timeout: float = 30) -> dict:
        """Execute Python in the persistent resource-limited REPL."""
        return self.repl_tool.invoke({"code": code, "timeout": timeout})

    def create_file(self, filename: str, content: str) -> dict:
        """Create a file inside the workspace."""
        return self.create_file_tool.invoke({"filename": filename, "content": content})

    def close(self):
        self.repl_tool.close()

    async def run_script(self, path: str, timeout: float = 10) -> dict:
        """Run a trusted Python file in the workspace and return console output."""
        target = self.resolve_path(path)
        if target.suffix != ".py":
            raise ValueError("Only .py scripts are supported")
        return await self.execute_python(target.read_text(encoding="utf-8"), timeout)

    async def write_and_run_script(self, path: str, code: str, timeout: float = 10) -> dict:
        """Create a Python script and test it; return file path and actual execution output."""
        written = self.write_file(path, code)
        execution = await self.run_script(path, timeout)
        return {**written, **execution, "tested": True}

    @staticmethod
    def validate_python(code):
        if not isinstance(code, str):
            raise ValueError("code must be a string")
        ast.parse(code)
        return {"valid": True}

    def write_file(self, path, code, overwrite=False):
        self.validate_python(code)
        target = self.resolve_path(path)
        if target.suffix != ".py":
            raise ValueError("Only .py files are supported")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w" if overwrite else "x", encoding="utf-8") as stream:
            stream.write(code)
        return {"path": str(target.relative_to(self.workspace)), "written": True}

    def edit_file(self, path, old, new):
        target = self.resolve_path(path)
        if target.suffix != ".py":
            raise ValueError("Only .py files are supported")
        result = self.edit_file_tool.invoke({"filename": path, "old": old, "new": new})
        if result["status"] == "error":
            raise ValueError(result["error"])
        return {"path": result["path"], "written": True}

    async def execute_python(self, code, timeout=10):
        """Run trusted Python in a child process, not a security sandbox."""
        self.validate_python(code)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("timeout must be in (0, 60]")
        # API keys and unrelated environment variables are not forwarded.
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-c", code, cwd=self.workspace, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        finally:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.communicate()
        if process.returncode:
            raise RuntimeError(f"Python exit {process.returncode}: {stderr.decode('utf-8', errors='replace')[:4000]}")
        return {"stdout": stdout.decode("utf-8", errors="replace")[:4000],
                "stderr": stderr.decode("utf-8", errors="replace")[:4000], "exit_code": process.returncode}
