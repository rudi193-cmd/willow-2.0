"""
cross_runtime.py — Merge session metadata across Claude Code + Cursor runtimes.

Reads $WILLOW_HOME/handoffs/cross-runtime.json (written by scripts/bridge_cross_runtime.py)
and returns a compact anchor block for session_start.
"""
from __future__ import annotations

import json

from sap.handoff_index import latest_handoff_sort_key
from willow.fylgja.willow_home import willow_home

BRIDGE_PATH = willow_home() / "handoffs" / "cross-runtime.json"


def handoff_recency_key(filename: str = "", date: str = "") -> tuple[str, str, str, str]:
    """Sortable recency key for session handoff filenames or ISO dates."""
    name = (filename or "").strip()
    if name:
        key = latest_handoff_sort_key(name, (date or "")[:10])
        if key[0]:
            return key
    d = (date or "")[:10]
    if d:
        return (d, "", "", name)
    return ("", "", "", name)


def bridge_covers_handoff(
    bridge: dict,
    handoff_filename: str,
    handoff_date: str = "",
) -> bool:
    """True when the bridge was built from a handoff at least as new as the live handoff."""
    if not bridge:
        return False
    live_key = handoff_recency_key(handoff_filename, handoff_date)
    if not live_key[0]:
        return True
    bridge_source = str(bridge.get("handoff_source") or "").strip()
    if not bridge_source:
        return False
    return handoff_recency_key(bridge_source) >= live_key


def ensure_fresh_bridge(agent: str, handoff_filename: str = "", handoff_date: str = "") -> dict:
    """Return the cross-runtime bridge, rebuilt from disk at READ time.

    ADR-20260703: the daily 06:00 timer artifact goes stale intra-day by
    design; every consumer now pays the (cheap, local) rebuild instead of
    inheriting a laundered copy. The cached file is only a fallback when the
    rebuild itself fails. handoff_filename/handoff_date are kept for call-site
    compatibility; they no longer gate the rebuild.
    """
    try:
        from scripts.bridge_cross_runtime import BRIDGE_PATH as _path, HANDOFF_DIR, build_bridge

        HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
        fresh = build_bridge(agent=agent)
        _path.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8")
        return fresh
    except Exception:
        return read_bridge()


def read_bridge() -> dict:
    if not BRIDGE_PATH.is_file():
        return {}
    try:
        data = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def anchor_lines(max_open: int = 4) -> list[str]:
    """Return [CROSS-RUNTIME] + [DIGEST] lines for session_start additionalContext.

    Session metadata (which runtimes, how long, last topic) still comes from
    the bridge. Open threads and the next bite now come from the boot digest,
    which verifies each claim at read time — the bridge's copies are no longer
    injected (ADR-20260703: no action-driving line without a verification
    stamp).
    """
    bridge = read_bridge()
    lines: list[str] = []
    if bridge:
        lines.append("[CROSS-RUNTIME]")
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

    try:
        import os

        from willow.fylgja.boot_digest import build_boot_digest, render_lines

        agent = (os.environ.get("WILLOW_AGENT_NAME") or "willow").strip()
        # Boot-latency budget: verify at most 8 claims inline at session start.
        digest = build_boot_digest(agent, include_attention=False, max_claims=8)
        lines.extend(render_lines(digest))
    except Exception as exc:
        lines.append(f"[DIGEST] unavailable: {str(exc)[:100]}")

    return lines
