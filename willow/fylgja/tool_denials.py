"""Deduplicated tool denial writes for corpus/tool_denials.

Structural signal — the pre_tool hook blocked a tool call. Records the
denied tool name, the block reason, and a hit counter so preference patterns
can be inferred: repeated denials of Bash → user prefers MCP-first.

Distinct from corpus/block_telemetry (which counts rule hits for operators).
This collection surfaces denied tools as preference signals for the agent.
b17: CRPS0
"""
import hashlib
from datetime import datetime, timezone

COLLECTION = "corpus/tool_denials"


def tool_denial_record_id(tool_name: str, reason: str) -> str:
    digest = hashlib.sha1(f"{tool_name}|{reason[:80]}".encode()).hexdigest()
    return f"deny-{digest[:12]}"


def upsert_tool_denial(store, *, tool_name: str, reason: str, session_id: str) -> str:
    """Insert or bump a tool denial record. Returns the record id."""
    reason = reason.strip()[:300]
    record_id = tool_denial_record_id(tool_name, reason)
    now = datetime.now(timezone.utc).isoformat()
    existing = store.get(COLLECTION, record_id)
    if existing:
        record = dict(existing)
        record["count"] = int(existing.get("count", 1)) + 1
        record["last_seen"] = now
        record["session_id"] = session_id
    else:
        record = {
            "id": record_id,
            "type": "tool_denial",
            "valence": "negative",
            "source": "pre_tool_hook",
            "tool_name": tool_name,
            "content": f"Blocked {tool_name}: {reason[:200]}",
            "reason": reason,
            "session_id": session_id,
            "created_at": now,
            "last_seen": now,
            "count": 1,
            "sandbox": True,
            "b17": "CRPS0",
        }
    store.put(COLLECTION, record, record_id=record_id)
    return record_id
