"""session_inject.py — session_start dedup + lite injection for compact/resume."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

_DEDUP_TTL_SEC = 300
_MARKER = Path("/tmp/willow-session-inject-marker.json")

# Caps for full boot injection (token budget). Human-sourced lanes get more slots.
MAX_CORRECTIONS = 4
MAX_PREFERENCES = 3
MAX_TOOL_DENIALS = 2
MAX_HUMAN_CONFIRMATIONS = 2
MAX_CROSS_RUNTIME_OPEN = 3


def is_continuation_source(source: str) -> bool:
    return source in ("compact", "resume")


def is_fresh_source(source: str) -> bool:
    return source in ("startup", "clear", "")


def dedup_fingerprint(session_id: str, lines: list[str]) -> str:
    payload = f"{session_id}\n" + "\n".join(lines[:12])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def should_skip_duplicate(session_id: str, fingerprint: str) -> bool:
    """Skip a second full injection for the same session within TTL."""
    if not session_id:
        return False
    try:
        if not _MARKER.is_file():
            return False
        data = json.loads(_MARKER.read_text(encoding="utf-8"))
        if data.get("session_id") != session_id:
            return False
        if data.get("fingerprint") != fingerprint:
            return False
        age = time.time() - float(data.get("ts", 0))
        return age < _DEDUP_TTL_SEC
    except Exception:
        return False


def record_injection(session_id: str, fingerprint: str, *, lite: bool) -> None:
    if not session_id:
        return
    try:
        _MARKER.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "fingerprint": fingerprint,
                    "lite": lite,
                    "ts": time.time(),
                }
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def minimal_continuation_block(agent: str, postgres: str, next_bite: str = "") -> list[str]:
    lines = [
        "[SESSION] continuation — prior INDEX omitted (dedup/token budget).",
        f"agent={agent}  postgres={postgres}",
    ]
    if next_bite:
        lines.append(f"NEXT: {next_bite[:160]}")
    return lines
