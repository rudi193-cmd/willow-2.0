"""Weekly WCE scheduling — SOIL state + Kart queue (mirrors dream_state pattern)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

WCE_INTERVAL_DAYS = float(os.environ.get("WCE_INTERVAL_DAYS", "7"))


def wce_conditions(app_id: str, store) -> dict[str, Any]:
    """Return whether the weekly WCE witness should run for *app_id*."""
    state = store.get(f"{app_id}/wce", "state") or {}
    if state.get("locked"):
        return {
            "should_run": False,
            "locked": True,
            "reason": "WCE witness already running",
        }

    now = datetime.now(timezone.utc)
    last_str = state.get("last_run_at", "")
    days_elapsed = 999.0
    if last_str:
        try:
            last = datetime.fromisoformat(last_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days_elapsed = (now - last).total_seconds() / 86400
        except Exception:
            pass

    should_run = days_elapsed >= WCE_INTERVAL_DAYS
    return {
        "should_run": should_run,
        "days_since_run": round(days_elapsed, 2),
        "last_run_at": last_str or None,
        "interval_days": WCE_INTERVAL_DAYS,
        "reason": (
            f"{days_elapsed:.1f}d elapsed (interval {WCE_INTERVAL_DAYS:.0f}d)"
            if should_run
            else f"conditions not met: {days_elapsed:.1f}d / {WCE_INTERVAL_DAYS:.0f}d"
        ),
    }


def queue_wce_task(
    pg,
    app_id: str,
    *,
    submitted_by: str = "willow",
    force: bool = False,
    pair_limit: int = 0,
) -> Optional[str]:
    """Queue scripts/wce_witness.py via Kart. Returns task_id or None."""
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "wce_witness.py"
    cmd_parts = [sys.executable, str(script), f"--agent={app_id}"]
    if force:
        cmd_parts.append("--force")
    if pair_limit:
        cmd_parts.append(f"--pair-limit={pair_limit}")
    cmd = " ".join(cmd_parts) + "\n# allow_net"
    return pg.submit_task(cmd, submitted_by=submitted_by, agent="kart")


def _resolve_cold_recall_mode(cold: dict[str, Any]) -> str:
    """Pick the live ranking mode from a cold_recall section."""
    config = cold.get("config") or {}
    declared = config.get("weight_modes") or config.get("variant_labels") or []
    if len(declared) == 1:
        return str(declared[0])
    by_mode = (cold.get("summary") or {}).get("by_mode") or {}
    if len(by_mode) == 1:
        return next(iter(by_mode))
    if by_mode:
        for pref in ("cap", "log", "off"):
            if pref in by_mode:
                return pref
        return sorted(by_mode)[0]
    return "log"


def extract_wce_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact metric vector from a full WCE run payload."""
    metrics: dict[str, Any] = {"timestamp": payload.get("timestamp")}
    handoff = payload.get("handoff") or {}
    hs = handoff.get("summary") or {}
    for key in (
        "thread_recall_mean",
        "next_bite_hit_rate",
        "surfacing_precision_mean",
        "relitigation_rate_mean",
        "stale_flag_rate_mean",
        "acted_on_stale_rate_mean",
        "pairs_evaluated",
        "handoffs_loaded",
    ):
        if hs.get(key) is not None:
            metrics[key] = hs.get(key)

    cold = payload.get("cold_recall") or {}
    cs = cold.get("summary") or {}
    config = cold.get("config") or {}
    mode = _resolve_cold_recall_mode(cold)
    by_mode = cs.get("by_mode") or {}
    live = by_mode.get(mode) or {}
    for key in ("cold_relevant_recall", "warm_relevant_recall", "surfacing_precision"):
        if live.get(key) is not None:
            metrics[key if key != "surfacing_precision" else "retrieval_precision"] = live.get(key)
    metrics["weight_mode"] = mode
    if config.get("weight_cap") is not None:
        metrics["weight_cap"] = config.get("weight_cap")
    return metrics


def format_wce_summary_line(metrics: dict[str, Any]) -> str:
    """One-line human summary for logs / Grove."""
    parts = [f"WCE {metrics.get('timestamp', '?')}"]
    pairs = [
        ("thread", metrics.get("thread_recall_mean")),
        ("next_bite", metrics.get("next_bite_hit_rate")),
        ("surfacing", metrics.get("surfacing_precision_mean")),
        ("re-lit", metrics.get("relitigation_rate_mean")),
        ("cold_rec", metrics.get("cold_relevant_recall")),
    ]
    for label, val in pairs:
        if isinstance(val, (int, float)):
            parts.append(f"{label}={val:.2f}")
    mode = metrics.get("weight_mode")
    if mode:
        cap = metrics.get("weight_cap")
        if mode == "cap" and cap is not None:
            parts.append(f"mode=cap@{cap}")
        else:
            parts.append(f"mode={mode}")
    return " · ".join(parts)
