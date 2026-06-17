"""anchor_state.py — prompt_count + context sentinel state (file is canonical).

SOIL agent/anchor/{agent} is mirrored for MCP visibility, but check_context.sh
and hooks must read the flat file — previously soil.put succeeded without
writing the file, leaving prompt_count stuck at 0.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from willow.fylgja.willow_home import willow_home

COMPACT_THRESHOLD = 15
HANDOFF_THRESHOLD = 25
ANCHOR_INTERVAL = 25
SOIL_COLLECTION = "agent/anchor"


def state_file(agent: str) -> Path:
    return willow_home() / f"anchor_state_{agent}.json"


def read_state(agent: str) -> dict:
    """Read anchor state; prefer flat file, fall back to SOIL."""
    path = state_file(agent)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    try:
        from core import soil

        record = soil.get(SOIL_COLLECTION, agent)
        if isinstance(record, dict):
            return record
    except Exception:
        pass
    return {"prompt_count": 0}


def write_state(agent: str, state: dict) -> None:
    """Persist anchor state to flat file and SOIL."""
    path = state_file(agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    try:
        from core import soil

        soil.put(SOIL_COLLECTION, agent, state)
    except Exception:
        pass


def prompt_count(agent: str) -> int:
    return int(read_state(agent).get("prompt_count", 0) or 0)


def bump_prompt_count(agent: str) -> int:
    count = prompt_count(agent) + 1
    write_state(agent, {"prompt_count": count})
    return count


def reset_prompt_count(agent: str) -> None:
    write_state(agent, {"prompt_count": 0})


def context_status(count: int | None = None, *, agent: str | None = None) -> str:
    """One of STATUS_OK | COMPACT_NOW | HANDOFF_NOW."""
    if count is None:
        count = prompt_count(agent or os.environ.get("WILLOW_AGENT_NAME", ""))
    if count > HANDOFF_THRESHOLD:
        return "HANDOFF_NOW"
    if count >= COMPACT_THRESHOLD:
        return "COMPACT_NOW"
    return "STATUS_OK"


def context_advisory(count: int) -> str | None:
    if count == COMPACT_THRESHOLD:
        return (
            "[CONTEXT] COMPACT_NOW — prompt_count reached 15. "
            "Invoke /compact or strategic-compact before large work."
        )
    if count > HANDOFF_THRESHOLD:
        return (
            "[CONTEXT] HANDOFF_NOW — prompt_count exceeded 25. "
            "Write handoff via /shutdown and start a fresh session."
        )
    if count == HANDOFF_THRESHOLD:
        return (
            "[CONTEXT] HANDOFF_SOON — one more prompt hits HANDOFF_NOW. "
            "Finish the current bite and /shutdown."
        )
    return None
