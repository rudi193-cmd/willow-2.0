"""
cross_runtime.py — Merge session metadata across Claude Code + Cursor runtimes.

Reads $WILLOW_HOME/handoffs/cross-runtime.json (written by scripts/bridge_cross_runtime.py)
and returns a compact anchor block for session_start.
"""
from __future__ import annotations

import json

from willow.fylgja.willow_home import willow_home

BRIDGE_PATH = willow_home() / "handoffs" / "cross-runtime.json"


def read_bridge() -> dict:
    if not BRIDGE_PATH.is_file():
        return {}
    try:
        data = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def anchor_lines(max_open: int = 4) -> list[str]:
    """Return [CROSS-RUNTIME] lines for session_start additionalContext."""
    bridge = read_bridge()
    if not bridge:
        return []

    lines = ["[CROSS-RUNTIME]"]
    for label in ("claude_latest", "cursor_latest"):
        block = bridge.get(label)
        if not isinstance(block, dict):
            continue
        sid = str(block.get("session_id", ""))[:8]
        runtime = block.get("runtime", label.replace("_latest", ""))
        duration = block.get("duration_minutes")
        turns = block.get("turn_count") or block.get("user_message_count")
        parts = [f"{runtime} {sid}"]
        if duration is not None:
            parts.append(f"{duration}min")
        if turns is not None:
            parts.append(f"{turns} turns")
        lines.append("  " + " · ".join(parts))
        topic = block.get("last_topic") or block.get("summary")
        if topic:
            lines.append(f"  last: {str(topic)[:120]}")

    open_threads = bridge.get("open_threads") or []
    if open_threads:
        lines.append(f"open ({len(open_threads)}):")
        for item in open_threads[:max_open]:
            lines.append(f"  · {str(item)[:100]}")
        if len(open_threads) > max_open:
            lines.append(f"  · … +{len(open_threads) - max_open} more")

    next_bite = bridge.get("next_bite")
    if next_bite:
        lines.append(f"next: {str(next_bite)[:140]}")

    return lines
