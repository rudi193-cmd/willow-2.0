"""
events/stop.py — Stop hook: per-turn cleanup only.
b17: PC001  ΔΣ=42
Depth stack and thread file cleanup. Session composite + stack snapshot written per-turn.
Heavy pipeline (compost, handoff rebuild, KB promotion, reflection) lives in
events/shutdown.py — run via /shutdown skill only.
"""
import json
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path

from core.agent_identity import require_agent_name
from willow.fylgja._state import get_trust_state, save_trust_state

try:
    from willow.fylgja._mcp import call
except Exception:
    call = None  # type: ignore[assignment]

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
                ts = line[1 : line.index("]")]
                if ts > cursor:
                    lines.append(line)
    except Exception:
        pass
    return lines


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

    # Write session composite (fast — no LLM)
    _write_session_composite(session_id)

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
