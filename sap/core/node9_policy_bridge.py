"""SAFE → @node9/policy-engine bridge (spike).

Layer 2 in the dispatch stack — runs after sap.core.gate.permitted().
Opt-in via WILLOW_NODE9_POLICY=1.

Uses a persistent node worker by default (WILLOW_NODE9_POLICY_SUBPROCESS=1 to
fall back to one-shot subprocess per call).

b17: N9POL  ΔΣ=42
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

_ADAPTER_DIR = Path(__file__).resolve().parent.parent / "adapters" / "node9_policy"
_EVALUATE_JS = _ADAPTER_DIR / "evaluate.mjs"
_WORKER_JS = _ADAPTER_DIR / "worker.mjs"
_DEFAULT_CONFIG = _ADAPTER_DIR / "default-policy.json"

_ENABLED = os.environ.get("WILLOW_NODE9_POLICY", "").strip().lower() in {
    "1", "true", "yes", "on",
}
_USE_SUBPROCESS = os.environ.get("WILLOW_NODE9_POLICY_SUBPROCESS", "").strip().lower() in {
    "1", "true", "yes", "on",
}
_CONFIG_PATH = os.environ.get("WILLOW_NODE9_POLICY_CONFIG", str(_DEFAULT_CONFIG))
_NODE_BIN = os.environ.get("WILLOW_NODE_BIN", "node")

_worker_lock = threading.Lock()
_worker_proc: subprocess.Popen[str] | None = None


def enabled() -> bool:
    if not _ENABLED:
        return False
    if _USE_SUBPROCESS:
        return _EVALUATE_JS.is_file()
    return _WORKER_JS.is_file()


def _build_payload(
    *,
    app_id: str,
    tool_name: str,
    args: Optional[dict[str, Any]],
    cwd: Optional[str],
) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "args": args or {},
        "context": {
            "agent": app_id,
            "app_id": app_id,
            "cwd": cwd or os.getcwd(),
        },
        "config_path": _CONFIG_PATH,
    }


def _error_verdict(reason: str, *, wall_ms: int) -> dict[str, Any]:
    return {
        "decision": "review",
        "reason": reason,
        "latency_ms": wall_ms,
        "error": True,
    }


def _parse_verdict(raw: str, *, wall_ms: int) -> dict[str, Any]:
    try:
        verdict = json.loads(raw.strip() or "{}")
    except json.JSONDecodeError as exc:
        return _error_verdict(f"policy-engine invalid JSON: {exc}", wall_ms=wall_ms)
    verdict.setdefault("latency_ms", wall_ms)
    return verdict


def _evaluate_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    proc = subprocess.run(
        [_NODE_BIN, str(_EVALUATE_JS)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=float(os.environ.get("WILLOW_NODE9_POLICY_TIMEOUT", "5")),
        check=False,
    )
    wall_ms = int((time.monotonic() - t0) * 1000)
    if proc.returncode != 0:
        return _error_verdict(
            f"policy-engine error: {proc.stderr.strip() or proc.stdout.strip()}",
            wall_ms=wall_ms,
        )
    return _parse_verdict(proc.stdout, wall_ms=wall_ms)


def _stop_worker() -> None:
    global _worker_proc
    proc = _worker_proc
    _worker_proc = None
    if proc is None:
        return
    try:
        if proc.stdin:
            proc.stdin.close()
    except Exception:
        pass
    try:
        proc.wait(timeout=1)
    except Exception:
        proc.kill()


def _start_worker() -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.setdefault("WILLOW_NODE9_POLICY_CONFIG", _CONFIG_PATH)
    proc = subprocess.Popen(
        [_NODE_BIN, str(_WORKER_JS)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    assert proc.stdout is not None
    ready_line = proc.stdout.readline()
    if proc.poll() is not None:
        err = (proc.stderr.read() if proc.stderr else "") or ready_line
        raise RuntimeError(f"policy worker failed to start: {err.strip()}")
    try:
        ready = json.loads(ready_line.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"policy worker bad ready line: {exc}") from exc
    if not ready.get("ready"):
        raise RuntimeError(f"policy worker not ready: {ready_line.strip()}")
    return proc


def _ensure_worker() -> subprocess.Popen[str]:
    global _worker_proc
    if _worker_proc is not None and _worker_proc.poll() is None:
        return _worker_proc
    _stop_worker()
    _worker_proc = _start_worker()
    return _worker_proc


def _evaluate_worker(payload: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    with _worker_lock:
        try:
            proc = _ensure_worker()
            assert proc.stdin is not None
            assert proc.stdout is not None
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            if not line:
                _stop_worker()
                return _error_verdict("policy worker closed stdout", wall_ms=int((time.monotonic() - t0) * 1000))
            return _parse_verdict(line, wall_ms=int((time.monotonic() - t0) * 1000))
        except Exception as exc:
            _stop_worker()
            return _error_verdict(f"policy worker error: {exc}", wall_ms=int((time.monotonic() - t0) * 1000))


def evaluate_tool_call(
    *,
    app_id: str,
    tool_name: str,
    args: Optional[dict[str, Any]] = None,
    cwd: Optional[str] = None,
) -> dict[str, Any]:
    """Run policy-engine on a normalized tool call. Returns verdict dict."""
    if not enabled():
        return {"decision": "allow", "skipped": True, "reason": "node9 policy disabled"}

    payload = _build_payload(app_id=app_id, tool_name=tool_name, args=args, cwd=cwd)
    if _USE_SUBPROCESS:
        return _evaluate_subprocess(payload)
    return _evaluate_worker(payload)


def should_block(verdict: dict[str, Any]) -> bool:
    return verdict.get("decision") == "block"


def should_review(verdict: dict[str, Any]) -> bool:
    return verdict.get("decision") == "review"
