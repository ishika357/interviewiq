"""Runs INSIDE the sandbox subprocess. Reads JSON from stdin, executes candidate code against tests.

Defence-in-depth layers applied here (the parent process adds timeout, empty env, temp cwd,
process-group kill and optional network namespace / Docker):
  1. OS resource limits: CPU seconds, address space, file size 0 (no file writes), open files.
  2. Import allow-list: os, sys, subprocess, socket, ctypes, ... cannot be imported.
  3. Reduced builtins: open, eval, exec, compile, input, breakpoint, getattr-family are removed.
  4. Per-test alarm so a single infinite loop is reported as a timeout.
NOTE: Python-level restrictions cannot be a perfect jail. For public deployment use SANDBOX_MODE=docker.
"""
import builtins
import io
import json
import signal
import sys
import time
import traceback

ALLOWED_IMPORTS = {
    "math", "collections", "itertools", "heapq", "bisect", "re", "functools", "string", "typing", "json",
    "statistics", "random", "operator", "decimal", "fractions", "copy", "datetime", "array", "queue", "dataclasses",
}
MARK = "@@IIQ_RESULT@@"


def apply_limits(cpu_seconds, mem_mb):
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:
        pass


class Timeout(BaseException):
    pass


def _alarm(_s, _f):
    raise Timeout()


def main():
    payload = json.loads(sys.stdin.read())
    real_stdout = sys.stdout
    apply_limits(payload["cpu_seconds"], payload["memory_mb"])

    real_import = builtins.__import__

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.split(".")[0] not in ALLOWED_IMPORTS:
            raise ImportError(f"import of '{name}' is not allowed in the sandbox")
        return real_import(name, globals, locals, fromlist, level)

    safe_builtins = {k: v for k, v in vars(builtins).items()
                     if k not in {"open", "eval", "exec", "compile", "input", "breakpoint", "exit", "quit",
                                  "help", "memoryview", "getattr", "setattr", "delattr", "globals", "locals", "vars"}}
    safe_builtins["__import__"] = safe_import
    env = {"__builtins__": safe_builtins, "__name__": "candidate"}

    results = []
    out = {"compile_error": None, "results": results}
    buf = io.StringIO()
    sys.stdout = buf
    try:
        try:
            code = compile(payload["code"], "<candidate>", "exec")
            exec(code, env)  # noqa: S102 - intentional, inside the restricted subprocess
            fn = env.get(payload["fn"])
            if not callable(fn):
                out["compile_error"] = f"Function '{payload['fn']}' was not defined."
        except BaseException:
            out["compile_error"] = "".join(traceback.format_exception_only(*sys.exc_info()[:2])).strip()[:500]
            fn = None
        signal.signal(signal.SIGALRM, _alarm)
        if fn is not None:
            timed_out = False
            for t in payload["tests"]:
                if timed_out:  # stop burning CPU: report the remaining tests as not run
                    results.append({"passed": False, "expected": t["expected"], "got": None,
                                    "error": "Not run because an earlier test timed out", "stdout": "", "ms": 0})
                    continue
                buf.seek(0), buf.truncate()
                start = time.perf_counter()
                rec = {"passed": False, "expected": t["expected"], "got": None, "error": None, "stdout": ""}
                try:
                    signal.setitimer(signal.ITIMER_REAL, payload["per_test_seconds"])
                    got = fn(*json.loads(json.dumps(t["args"])))
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    try:
                        json.dumps(got)
                        rec["got"] = got
                    except TypeError:
                        rec["got"] = repr(got)[:200]
                    rec["passed"] = rec["got"] == t["expected"]
                except Timeout:
                    rec["error"] = "Time limit exceeded (possible infinite loop or very slow algorithm)"
                    timed_out = True
                except MemoryError:
                    rec["error"] = "Memory limit exceeded"
                except BaseException as exc:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    rec["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                rec["ms"] = round((time.perf_counter() - start) * 1000, 1)
                rec["stdout"] = buf.getvalue()[:500]
                results.append(rec)
    finally:
        sys.stdout = real_stdout
    real_stdout.write("\n" + MARK + json.dumps(out) + "\n")
    real_stdout.flush()


if __name__ == "__main__":
    main()
