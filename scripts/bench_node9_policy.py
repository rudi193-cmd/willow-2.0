#!/usr/bin/env python3
"""Benchmark @node9/policy-engine pass latency via the Willow bridge."""
from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ["WILLOW_NODE9_POLICY"] = "1"

from sap.core.node9_policy_bridge import evaluate_tool_call, enabled  # noqa: E402


def _bench(label: str, tool: str, args: dict, n: int = 50) -> None:
    latencies: list[int] = []
    engine_latencies: list[int] = []
    verdict = None
    for _ in range(n):
        t0 = time.monotonic()
        verdict = evaluate_tool_call(app_id="hanuman", tool_name=tool, args=args)
        latencies.append(int((time.monotonic() - t0) * 1000))
        if isinstance(verdict.get("latency_ms"), int):
            engine_latencies.append(verdict["latency_ms"])
    mode = "subprocess" if os.environ.get("WILLOW_NODE9_POLICY_SUBPROCESS") else "worker"
    print(
        f"{label:28} mode={mode:9} decision={verdict.get('decision') if verdict else '?':6} "
        f"n={n} wall_p50={statistics.median(latencies):.0f}ms "
        f"engine_p50={statistics.median(engine_latencies) if engine_latencies else 0:.0f}ms "
        f"wall_p95={sorted(latencies)[int(n * 0.95) - 1]}ms"
    )


def main() -> int:
    if not enabled():
        print("node9 bridge not enabled — run npm install in sap/adapters/node9_policy")
        return 1

    print("WILLOW_NODE9_POLICY benchmark")
    if not os.environ.get("WILLOW_NODE9_POLICY_SUBPROCESS"):
        evaluate_tool_call(app_id="hanuman", tool_name="kb_search", args={"query": "warmup"})

    _bench("kb_search (benign)", "kb_search", {"query": "fleet status"})
    _bench("agent_task_submit echo", "agent_task_submit", {"task": "echo hello"})
    _bench("agent_task_submit rm -rf", "agent_task_submit", {"task": "rm -rf /tmp/foo"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
