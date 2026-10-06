"""Process-isolated Python REPL and workspace file creation."""
import ast
import json
import logging
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
from threading import RLock, Thread
from time import perf_counter

from .base_tool import BaseTool


class PythonREPLTool(BaseTool):
    """Resource-limited local REPL; not an OS security sandbox for hostile code."""
    ALLOWED_IMPORTS = {"math", "statistics", "datetime", "json", "csv", "random", "numpy", "pandas", "matplotlib", "sys"}

    def __init__(self, base_path="./outputs", timeout=30, memory_limit_mb=1024):
        super().__init__("python_repl", "Execute Python in a process-isolated REPL with timeout, memory and output limits")
        if not isinstance(memory_limit_mb, int) or isinstance(memory_limit_mb, bool) or memory_limit_mb < 64:
            raise ValueError("memory_limit_mb must be an integer >= 64")
        self.base_path = Path(base_path).resolve()
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
        self.globals = {}
        self.max_output_len = 10000
        self._process = None
        self._lock = RLock()
        self.logger = logging.getLogger(self.name)

    def validate_input(self, input_dict):
        if not isinstance(input_dict, dict) or not isinstance(input_dict.get("code"), str) or not input_dict["code"].strip():
            raise ValueError("code must be nonempty text")
        timeout = input_dict.get("timeout", self.timeout)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        tree = ast.parse(input_dict["code"])
        banned = {"open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr", "delattr", "input", "breakpoint"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if any(name.split(".")[0] not in self.ALLOWED_IMPORTS for name in names) or getattr(node, "level", 0):
                    raise ValueError("Import not allowed")
                if isinstance(node, ast.ImportFrom) and node.module == "sys" and any(alias.name not in ("version", "version_info") for alias in node.names):
                    raise ValueError("Only sys.version and sys.version_info are allowed")
            if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in ("exit", "modules", "getframe", "_getframe")):
                raise ValueError("Unsafe attribute access")
            if isinstance(node, ast.Name) and (node.id in banned or (node.id.startswith("__") and node.id != "__name__")):
                raise ValueError(f"Unsafe name: {node.id}")
        return True

    def _start(self):
        self.base_path.mkdir(parents=True, exist_ok=True)
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
        self._process = subprocess.Popen([sys.executable, "-I", "-u", str(Path(__file__).with_name("_repl_worker.py")),
                                          str(self.base_path), str(self.memory_limit_mb)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         text=True, encoding="utf-8", env=env,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self._replies = queue.Queue()
        def read_replies(process, replies):
            try:
                for line in process.stdout:
                    replies.put(line)
            finally:
                replies.put(None)
        self._reader = Thread(target=read_replies, args=(self._process, self._replies), daemon=True)
        self._reader.start()

    def invoke(self, input_dict):
        started = perf_counter()
        try:
            self.validate_input(input_dict)
            with self._lock:
                if self._process is None or self._process.poll() is not None:
                    self.close()
                    self._start()
                self._process.stdin.write(json.dumps({"code": input_dict["code"], "max_output_len": self.max_output_len}) + "\n")
                self._process.stdin.flush()
                try:
                    reply = self._replies.get(timeout=input_dict.get("timeout", self.timeout))
                except queue.Empty:
                    self.close()
                    raise TimeoutError("Python execution timed out; REPL state reset")
                if reply is None:
                    self.close()
                    raise RuntimeError("REPL exited (possible memory limit or startup failure)")
                result = json.loads(reply)
                if result["status"] == "success":
                    self.globals = result["variables"]
                self.logger.info("python_repl status=%s duration=%.3fs", result["status"], perf_counter() - started)
                return result
        except Exception as exc:
            self.logger.error("python_repl failed duration=%.3fs: %s", perf_counter() - started, exc)
            return {"status": "error", "error": str(exc), "type": type(exc).__name__}

    def close(self):
        with self._lock:
            if self._process is not None:
                if self._process.poll() is None:
                    self._process.kill()
                self._process.wait()
                self._process.stdin.close()
                self._reader.join(timeout=2)
                self._process.stdout.close()
                self._process = None
            self.globals = {}


class CreateFileTool(BaseTool):
    def __init__(self, base_path="./outputs"):
        super().__init__("create_file", "Create a UTF-8 file within the output directory")
        self.base_path = Path(base_path).resolve()

    def _path(self, filename):
        if not isinstance(filename, str) or not filename:
            raise ValueError("Invalid filename")
        relative = Path(filename)
        target = (self.base_path / relative).resolve()
        if relative.is_absolute() or relative.drive or ".." in relative.parts or not target.is_relative_to(self.base_path):
            raise ValueError("Invalid filename")
        return target

    def validate_input(self, input_dict):
        if not isinstance(input_dict, dict):
            raise ValueError("input must be a dictionary")
        self._path(input_dict.get("filename"))
        if not isinstance(input_dict.get("content"), str):
            raise ValueError("content must be text")
        return True

    def invoke(self, input_dict):
        try:
            self.validate_input(input_dict)
            path = self._path(input_dict["filename"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(input_dict["content"], encoding="utf-8")
            logging.getLogger(self.name).info("Created %s", path)
            return {"status": "success", "path": str(path), "size": len(input_dict["content"])}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
