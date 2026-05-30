"""
stop_slow.py — Background slow-path for the Stop hook.
Launched as a detached subprocess by stop.py so the hook returns immediately.
Runs: affect tagging, 3b KB annotation, stack snapshot, handoff_rebuild, kart drain.
"""
import json
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path

_root = str(Path(__file__).resolve().parents[4])
if _root not in sys.path:
    sys.path.insert(0, _root)

from willow.fylgja.events.stop import (
    _AGENT,
    _compute_affect_with_traces,
    _write_failure_atom,
    _write_reflection_atom,
    _promote_session_to_kb,
    _write_stack_snapshot,
    _drain_kart_queue,
    call,
)

_t0 = _time.monotonic()
session_id = sys.argv[1] if len(sys.argv) > 1 else ""

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

# Promote session to KB (3b inference + kb_ingest)
try:
    _promote_session_to_kb(session_id, affect, session_traces)
except Exception:
    pass

# Stack snapshot — authoritative "what's open" for next boot
try:
    _write_stack_snapshot(session_id)
except Exception:
    pass

# Rebuild handoff index so handoff_latest is current next session
try:
    if call is not None:
        call("handoff_rebuild", {"app_id": _AGENT}, timeout=30)
except Exception:
    pass

# Drain pending Kart tasks
try:
    _drain_kart_queue()
except Exception:
    pass

# Timing log
_dur_ms = int((_time.monotonic() - _t0) * 1000)
try:
    _log_dir = Path.home() / ".willow" / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    with open(_log_dir / "hook_timing.jsonl", "a") as _f:
        _f.write(json.dumps({
            "hook": "stop_slow",
            "duration_ms": _dur_ms,
            "affect": affect,
            "ts": datetime.now(timezone.utc).isoformat(),
        }) + "\n")
except Exception:
    pass
