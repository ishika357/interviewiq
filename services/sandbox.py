"""Secure(ish) execution of candidate Python. NEVER runs candidate code in the Flask process.

Modes
  subprocess (default): separate Python process, `-I -S`, empty environment, throw-away temp cwd,
      rlimits + import allow-list (see sandbox_runner.py), wall-clock timeout, own process group that
      is killed on timeout, and a network namespace via `unshare -rn` when the OS allows it.
  docker (SANDBOX_MODE=docker): throw-away container with --network none, memory/CPU/pids limits,
      read-only filesystem and non-root user. Recommended for any public deployment.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("interviewiq.sandbox")
RUNNER = Path(__file__).resolve().parent / "sandbox_runner.py"
MARK = "@@IIQ_RESULT@@"
MAX_CODE_CHARS = 20000


@lru_cache(maxsize=1)
def _can_unshare_net() -> bool:
    exe = shutil.which("unshare")
    if not exe:
        return False
    try:
        return subprocess.run([exe, "-rn", "true"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def isolation_report() -> dict:
    return {"network_namespace": _can_unshare_net(), "docker": bool(shutil.which("docker"))}


def run_tests(code: str, fn: str, tests: list[dict], mode: str = "subprocess", timeout: int = 10, memory_mb: int = 256) -> dict:
    """Execute `fn` from `code` against `tests` -> {ok, error, compile_error, results[], timed_out}."""
    if len(code) > MAX_CODE_CHARS:
        return {"ok": False, "error": f"Code is too long (max {MAX_CODE_CHARS} characters).", "results": []}
    payload = json.dumps({"code": code, "fn": fn, "tests": tests, "cpu_seconds": timeout,
                          "memory_mb": memory_mb, "per_test_seconds": 2})
    with tempfile.TemporaryDirectory(prefix="iiq_sbx_") as tmp:
        if mode == "docker" and shutil.which("docker"):
            cmd = ["docker", "run", "--rm", "-i", "--network", "none", "--memory", f"{memory_mb + 64}m", "--cpus", "0.5",
                   "--pids-limit", "32", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--user", "65534:65534", "-v", f"{RUNNER}:/sandbox/runner.py:ro", "python:3.11-slim",
                   "python", "-I", "-S", "/sandbox/runner.py"]
        else:
            cmd = [sys.executable, "-I", "-S", str(RUNNER)]
            if _can_unshare_net():
                cmd = ["unshare", "-rn"] + cmd
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=tmp, env={"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"},
                start_new_session=True, text=True,
            )
        except OSError as exc:
            log.error("Sandbox failed to start: %s", exc)
            return {"ok": False, "error": "Code runner is unavailable on this server.", "results": []}
        try:
            stdout, stderr = proc.communicate(payload, timeout=timeout + 3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.communicate()
            return {"ok": False, "error": "Time limit exceeded. Check for infinite loops or very slow algorithms.", "results": [], "timed_out": True}

    if MARK not in stdout:
        reason = "The program was stopped (time or memory limit reached)." if proc.returncode and proc.returncode < 0 else "The program crashed before producing results."
        if "MemoryError" in stderr:
            reason = "Memory limit exceeded."
        return {"ok": False, "error": reason, "results": [], "stderr": stderr[-300:]}
    try:
        data = json.loads(stdout.split(MARK, 1)[1].strip().splitlines()[0])
    except (ValueError, IndexError):
        return {"ok": False, "error": "Could not read the runner output.", "results": []}
    return {"ok": True, "error": None, "compile_error": data.get("compile_error"), "results": data.get("results", [])}
