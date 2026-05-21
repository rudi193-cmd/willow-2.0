"""SAFE → @node9/policy-engine bridge (spike).

Layer 2 in the dispatch stack — runs after sap.core.gate.permitted().
Opt-in via WILLOW_NODE9_POLICY=1.

b17: N9POL  ΔΣ=42
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

_ADAPTER_DIR = Path(__file__).resolve().parent.parent / "adapters" / "node9_policy"
_EVALUATE_JS = _ADAPTER_DIR / "evaluate.mjs"
_DEFAULT_CONFIG = _ADAPTER_DIR / "default-policy.json"

_ENABLED = os.environ.get("WILLOW_NODE9_POLICY", "").strip().lower() in {
    "1", "true", "yes", "on",
}
_CONFIG_PATH = os.environ.get("WILLOW_NODE9_POLICY_CONFIG", str(_DEFAULT_CONFIG))
_NODE_BIN = os.environ.get("WILLOW_NODE_BIN", "node")


def enabled() -> bool:
    return _ENABLED and _EVALUATE_JS.is_file()


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

    payload = {
        "tool": tool_name,
        "args": args or {},
        "context": {
            "agent": app_id,
            "app_id": app_id,
            "cwd": cwd or os.getcwd(),
        },
        "config_path": _CONFIG_PATH,
    }

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
        return {
            "decision": "review",
            "reason": f"policy-engine error: {proc.stderr.strip() or proc.stdout.strip()}",
            "latency_ms": wall_ms,
            "error": True,
        }

    try:
        verdict = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        return {
            "decision": "review",
            "reason": f"policy-engine invalid JSON: {exc}",
            "latency_ms": wall_ms,
            "error": True,
        }

    verdict.setdefault("latency_ms", wall_ms)
    return verdict


def should_block(verdict: dict[str, Any]) -> bool:
    return verdict.get("decision") == "block"


def should_review(verdict: dict[str, Any]) -> bool:
    return verdict.get("decision") == "review"
