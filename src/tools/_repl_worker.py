"""Private persistent REPL subprocess; communicates over JSON lines."""
import builtins
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
import sys


def limit_memory(megabytes):
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (megabytes * 1024**2,) * 2)
        return None
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_ = [("ProcessTime", ctypes.c_longlong), ("JobTime", ctypes.c_longlong),
                    ("Flags", wintypes.DWORD), ("Min", ctypes.c_size_t), ("Max", ctypes.c_size_t),
                    ("Active", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                    ("Priority", wintypes.DWORD), ("Scheduling", wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ("Read", "Write", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]
    class Extended(ctypes.Structure):
        _fields_ = [("Basic", Basic), ("IO", IO), ("ProcessMemory", ctypes.c_size_t),
                    ("JobMemory", ctypes.c_size_t), ("PeakProcess", ctypes.c_size_t), ("PeakJob", ctypes.c_size_t)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.Basic.Flags = 0x100 | 0x2000  # process memory and kill-on-job-close
    limits.ProcessMemory = megabytes * 1024**2
    if not job or not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    return job  # retained until subprocess exits


class BoundedOutput(io.StringIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit
    def write(self, text):
        remaining = self.limit - self.tell()
        if remaining > 0:
            super().write(text[:remaining])
        return len(text)


def main():
    memory_job = limit_memory(int(sys.argv[2]))
    os.chdir(sys.argv[1])
    os.environ["MPLBACKEND"] = "Agg"
    allowed = {"math", "statistics", "datetime", "json", "csv", "random", "numpy", "pandas", "matplotlib", "sys"}
    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name.split(".")[0] not in allowed:
            raise ImportError(f"Import {name} not allowed")
        return builtins.__import__(name, globals, locals, fromlist, level)
    safe_builtins = dict(vars(builtins))
    for name in ("open", "eval", "exec", "compile", "input", "breakpoint", "globals", "locals", "vars", "getattr", "setattr", "delattr"):
        safe_builtins.pop(name, None)
    safe_builtins["__import__"] = safe_import
    namespace = {"__builtins__": safe_builtins, "__name__": "__main__"}
    for line in sys.stdin:
        request = json.loads(line)
        stdout = BoundedOutput(request["max_output_len"])
        stderr = BoundedOutput(request["max_output_len"])
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(request["code"], namespace)
            variables = {}
            for key, value in namespace.items():
                if not key.startswith("_"):
                    if len(variables) >= 100:
                        break
                    variables[key] = str(value)[:1000]
            result = {"status": "success", "stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "variables": variables}
        except BaseException as exc:
            result = {"status": "error", "error": str(exc), "type": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
