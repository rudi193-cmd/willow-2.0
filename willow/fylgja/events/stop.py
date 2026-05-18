"""
events/stop.py — Stop hook: per-turn cleanup + session composite writer.
b17: PC001  ΔΣ=42
Depth stack and thread file cleanup. Session composite written to {agent}/sessions/store.
Heavy pipeline (handoff writing) lives in events/shutdown.py — run via /shutdown skill.
Personal signal scanner: scans last user turn for family/health/creative/emotion patterns,
stages candidates to personal/candidates for Loki review → sean.db write gate.
"""
import json
import os
import re
import sys
import time as _time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.agent_identity import require_agent_name
from willow.fylgja._state import get_trust_state, save_trust_state

try:
    from willow.fylgja._mcp import call
except Exception:
    call = None  # type: ignore[assignment]

try:
    from core.yggdrasil import ask_structured as _ygg_structured
except Exception:
    def _ygg_structured(prompt: str, timeout: int = 30) -> dict:  # type: ignore
        return {"summary": None, "importance": 0}

DEPTH_FILE = Path("/tmp/willow-agent-depth-stack.txt")
THREAD_FILE = Path("/tmp/willow-context-thread.json")
_AGENT = require_agent_name()


def read_turns_since(cursor: str, turns_file: Path) -> list[str]:
    """Return lines from turns_file whose timestamp is after cursor."""
    if not turns_file.exists():
        return []
    lines = []
    try:
        for line in turns_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("[") and "]" in line:
                ts = line[1:line.index("]")]
                if ts > cursor:
                    lines.append(line)
    except Exception:
        pass
    return lines


def _compute_affect_with_traces(session_id: str) -> tuple[str, list]:
    """Derive affect from trace atoms. Returns (affect, session_traces)."""
    if call is None:
        return "neutral", []
    try:
        traces = call("store_search", {
            "app_id": _AGENT,
            "collection": f"{_AGENT}/turns/store",
            "query": "",
            "limit": 50,
        }, timeout=5) or []
    except Exception:
        return "neutral", []

    session_traces = [t for t in traces if t.get("session_id") == session_id]
    if not session_traces:
        return "neutral", []

    pairs = Counter((t.get("tool", ""), t.get("target", "")) for t in session_traces)
    repeated = sum(1 for count in pairs.values() if count > 1)
    affect = "friction" if repeated >= 1 else "clean"
    return affect, session_traces


def _compute_affect(session_id: str) -> str:
    """Derive affect from trace atoms. Returns affect only (neutral|clean|friction)."""
    affect, _traces = _compute_affect_with_traces(session_id)
    return affect


def _write_failure_atom(session_id: str, traces: list) -> None:
    """Write failure atom to hanuman/atoms/store. Only called for friction sessions."""
    if call is None:
        return
    pairs = Counter((t.get("tool", ""), t.get("target", "")) for t in traces)
    primary_target = pairs.most_common(1)[0][0][1] if pairs else "unknown"
    n_retries = sum(c - 1 for c in pairs.values() if c > 1)

    try:
        call("store_put", {
            "app_id": _AGENT,
            "collection": f"{_AGENT}/atoms/store",
            "record": {
                "id": f"failure-{session_id[:8]}",
                "type": "failure",
                "source": "failure",
                "session_id": session_id,
                "target": primary_target,
                "summary": (
                    f"Session had friction on {primary_target}. "
                    f"{n_retries} repeated tool+target pair(s) detected."
                ),
                "affect": "friction",
                "resolved": False,
                "valid_at": datetime.now(timezone.utc).isoformat(),
                "invalid_at": None,
            },
        }, timeout=4)
    except Exception:
        pass


def _write_reflection_atom(session_id: str, affect: str, traces: list) -> None:
    """Write reflection atom (yggdrasil for friction) or pending flag (clean/neutral)."""
    if call is None:
        return

    if affect == "friction":
        trace_lines = "\n".join(
            f"- {t.get('tool', '?')} on {t.get('target', '?')}: {t.get('summary', '')}"
            for t in traces[:10]
        )
        prompt = (
            f"Session {session_id[:8]} trace atoms:\n{trace_lines}\n\n"
            "Write one sentence: what does the next instance need to know "
            "that isn't in these raw traces?\n"
            "Format exactly: SUMMARY: <sentence> | IMPORTANCE: <1-10>"
        )
        result = _ygg_structured(prompt, timeout=4)
        if result["summary"]:
            next_review = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            try:
                call("store_put", {
                    "app_id": _AGENT,
                    "collection": f"{_AGENT}/atoms/store",
                    "record": {
                        "id": f"reflection-{session_id[:8]}",
                        "type": "reflection",
                        "source": "reflection",
                        "session_id": session_id,
                        "summary": result["summary"],
                        "importance": result["importance"],
                        "affect": affect,
                        "next_review": next_review,
                        "review_interval_days": 2,
                        "stability": 1.0,
                        "valid_at": datetime.now(timezone.utc).isoformat(),
                        "invalid_at": None,
                        "superseded_by": None,
                    },
                }, timeout=4)
                return
            except Exception:
                pass

    # Fallback: write pending flag for norn_pass
    try:
        call("store_put", {
            "app_id": _AGENT,
            "collection": f"{_AGENT}/atoms/store",
            "record": {
                "id": f"reflection-pending-{session_id[:8]}",
                "type": "reflection_pending",
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }, timeout=3)
    except Exception:
        pass


def mark_session_clean(turn_count: int = 0) -> None:
    if turn_count == 0:
        return
    state = get_trust_state()
    if not state:
        return
    state["clean_session_count"] = state.get("clean_session_count", 0) + 1
    save_trust_state(state)


def _write_session_composite(session_id: str) -> None:
    """Write session composite atom. Fast — no LLM, pure store_put.
    next_bite is populated later by the /handoff skill via store_update.
    """
    if call is None:
        return
    try:
        sid = (session_id or "unknown")[:8]
        record = {
            "id": f"session-{sid}",
            "session_id": session_id or "unknown",
            "date": datetime.now(timezone.utc).isoformat(),
            "turn_count": 0,
            "tools_fired": [],
            "next_bite": "",
            "type": "session",
        }
        call("store_put", {
            "app_id": _AGENT,
            "collection": f"{_AGENT}/sessions/store",
            "record": record,
        }, timeout=4)
    except Exception:
        pass


_PERSONAL_PATTERNS: list[tuple[str, list[str]]] = [
    ("family",   [r"\b(mom|dad|mother|father|brother|sister|family|wife|husband|partner|son|daughter|parent|child|kids?|grandma|grandpa)\b"]),
    ("health",   [r"\b(doctor|hospital|surgery|medication|pain|injury|herniated|disc|back|health|diagnosis|prescription|therapy|therapist)\b"]),
    ("creative", [r"\b(writing|wrote|book|character|story|chapter|novel|manuscript|poem|scene|draft|gerald|oakenscroll|saxophone|books of mann)\b"]),
    ("emotion",  [r"\b(feel|feeling|stressed|anxious|excited|scared|worried|happy|sad|frustrated|overwhelmed|proud|lonely|hopeful|angry)\b"]),
    ("finance",  [r"\b(bankruptcy|court|filing|mortgage|debt|loan|rent|bill|money|broke|budget|chapter 7|ch7)\b"]),
    ("job",      [r"\b(start work|new job|hired|fired|quit|laid off|promotion|interview|employer|coworker|boss)\b"]),
    ("date_ref", [r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|this week|next week|by [a-z]+ \d|on [a-z]+ \d{1,2})\b"]),
]


def _extract_user_text_from_jsonl(session_id: str) -> str:
    """Find JSONL for session_id, return last user message text."""
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return ""
    for jsonl in claude_dir.rglob(f"{session_id}.jsonl"):
        try:
            lines = jsonl.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            for line in reversed(lines[-50:]):
                try:
                    obj = json.loads(line)
                    role = obj.get("role") or (obj.get("message") or {}).get("role", "")
                    if role == "user":
                        content = obj.get("content") or (obj.get("message") or {}).get("content", "")
                        if isinstance(content, list):
                            return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                        return str(content)
                except Exception:
                    continue
        except Exception:
            pass
    return ""


def _scan_personal_signal(session_id: str) -> None:
    """Scan last user turn for personal signal. Stage candidates to personal/candidates."""
    if call is None:
        return
    text = _extract_user_text_from_jsonl(session_id)
    if not text or len(text) < 20:
        return

    matches = []
    for category, patterns in _PERSONAL_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(category)
                break

    if not matches:
        return

    try:
        ts = datetime.now(timezone.utc).isoformat()
        call("store_put", {
            "app_id": _AGENT,
            "collection": "personal/candidates",
            "record": {
                "id": f"candidate-{session_id[:8]}-{int(_time.time())}",
                "session_id": session_id,
                "categories": matches,
                "text_excerpt": text[:300],
                "status": "pending",
                "created_at": ts,
                "reviewed_by": None,
            },
        }, timeout=4)
    except Exception:
        pass


def _is_isolated_directory() -> bool:
    """Return True if CWD is a sandbox/isolated directory — skip all fleet hooks."""
    mcp = Path.cwd() / ".mcp.json"
    try:
        data = __import__("json").loads(mcp.read_text())
        return data.get("mcpServers") == {}
    except Exception:
        return False


def main():
    if _is_isolated_directory():
        import sys as _sys; _sys.exit(0)

    _t0 = _time.monotonic()

    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    session_id = data.get("session_id", "")

    # Cleanup depth stack
    try:
        depth = int(DEPTH_FILE.read_text().strip()) if DEPTH_FILE.exists() else 0
        if depth > 1:
            DEPTH_FILE.write_text(str(depth - 1))
        else:
            DEPTH_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    # Cleanup context thread
    try:
        THREAD_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    # Write session composite
    _write_session_composite(session_id)

    # Affect tagging + failure atom
    affect = "neutral"
    session_traces: list = []
    try:
        affect, session_traces = _compute_affect_with_traces(session_id)
        if affect == "friction":
            _write_failure_atom(session_id, session_traces)
    except Exception:
        pass

    # Reflection atom (affect-gated)
    try:
        _write_reflection_atom(session_id, affect, session_traces)
    except Exception:
        pass

    # Personal signal scan → personal/candidates (Loki reviews → sean.db)
    try:
        _scan_personal_signal(session_id)
    except Exception:
        pass

    # Hook timing log
    _dur_ms = int((_time.monotonic() - _t0) * 1000)
    try:
        _log_dir = Path.home() / ".willow" / "logs"
        _log_dir.mkdir(parents=True, exist_ok=True)
        with open(_log_dir / "hook_timing.jsonl", "a") as _f:
            import json as _json
            _f.write(_json.dumps({
                "hook": "stop",
                "duration_ms": _dur_ms,
                "ts": datetime.now(timezone.utc).isoformat(),
            }) + "\n")
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
