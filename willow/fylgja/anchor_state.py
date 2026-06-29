"""anchor_state.py — prompt_count + context sentinel state (file is canonical).

SOIL agent/anchor/{agent} is mirrored for MCP visibility, but check_context.sh
and hooks must read the flat file — previously soil.put succeeded without
writing the file, leaving prompt_count stuck at 0.

State is scoped per **session** (anchor_state_{agent}__{session}.json), not just
per agent. Concurrent sessions under one agent namespace used to share a single
anchor_state_{agent}.json, so a freshly-booted session inherited another live
session's count and tripped HANDOFF_NOW prematurely (flag-handoff-prompt-count-
cross-session). Each session now owns its own counter. The legacy per-agent file
is still read/written when no session_id is supplied (back-compat).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from willow.fylgja.willow_home import willow_home

COMPACT_THRESHOLD = 15
HANDOFF_THRESHOLD = 25
ANCHOR_INTERVAL = 25
SOIL_COLLECTION = "agent/anchor"

# session_id values that mean "no real session" — fall back to the legacy
# per-agent bucket rather than minting a junk per-session file.
_NULL_SESSIONS = {"", "unknown", "none", "null"}


def _norm_session(session_id: str | None) -> str | None:
    if not session_id:
        return None
    sid = str(session_id).strip()
    if sid.lower() in _NULL_SESSIONS:
        return None
    return sid


def _safe_session(session_id: str) -> str:
    """Sanitise a session_id for use in a filename (uuids pass through)."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:64]


def state_file(agent: str, session_id: str | None = None) -> Path:
    sid = _norm_session(session_id)
    if sid:
        return willow_home() / f"anchor_state_{agent}__{_safe_session(sid)}.json"
    return willow_home() / f"anchor_state_{agent}.json"


def _soil_key(agent: str, session_id: str | None = None) -> str:
    sid = _norm_session(session_id)
    return f"{agent}__{_safe_session(sid)}" if sid else agent


def _newest_session_file(agent: str) -> Path | None:
    """Most-recently-written per-session state file for this agent, if any.

    Lets read-only callers without a session_id (e.g. check_context.sh) reflect
    the active session instead of a stale legacy file.
    """
    try:
        files = list(willow_home().glob(f"anchor_state_{agent}__*.json"))
    except Exception:
        return None
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def read_state(agent: str, session_id: str | None = None) -> dict:
    """Read anchor state; prefer flat file, fall back to SOIL.

    With a session_id: read only that session's file/SOIL key (no cross-session
    bleed). Without one: prefer the newest per-session file, else the legacy
    per-agent file, else legacy SOIL.
    """
    sid = _norm_session(session_id)
    if sid:
        path = state_file(agent, sid)
    else:
        path = _newest_session_file(agent) or state_file(agent)

    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    try:
        from core import soil

        record = soil.get(SOIL_COLLECTION, _soil_key(agent, sid))
        if isinstance(record, dict):
            return record
    except Exception:
        pass
    return {"prompt_count": 0}


def write_state(agent: str, state: dict, session_id: str | None = None) -> None:
    """Persist anchor state to flat file and SOIL (session-scoped when given)."""
    sid = _norm_session(session_id)
    path = state_file(agent, sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    try:
        from core import soil

        soil.put(SOIL_COLLECTION, _soil_key(agent, sid), state)
    except Exception:
        pass


def prompt_count(agent: str, session_id: str | None = None) -> int:
    return int(read_state(agent, session_id).get("prompt_count", 0) or 0)


def bump_prompt_count(agent: str, session_id: str | None = None) -> int:
    count = prompt_count(agent, session_id) + 1
    write_state(agent, {"prompt_count": count}, session_id)
    return count


def reset_prompt_count(agent: str, session_id: str | None = None) -> None:
    write_state(agent, {"prompt_count": 0}, session_id)


def prune_session_states(agent: str, max_age_hours: float = 48.0) -> int:
    """Delete this agent's per-session state files older than max_age_hours.

    Per-session files accumulate (one per Claude session). Best-effort cleanup
    run at session start; never raises. Returns the number removed.
    """
    import time

    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    try:
        files = list(willow_home().glob(f"anchor_state_{agent}__*.json"))
    except Exception:
        return 0
    for f in files:
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except Exception:
            pass
    return removed


def context_status(count: int | None = None, *, agent: str | None = None,
                   session_id: str | None = None) -> str:
    """One of STATUS_OK | COMPACT_NOW | HANDOFF_NOW."""
    if count is None:
        count = prompt_count(agent or os.environ.get("WILLOW_AGENT_NAME", ""),
                             session_id)
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
