"""Deduplicated preference writes for corpus/preferences.

Analogous to corrections.py. One row per unique content with a hit counter —
avoids re-writing the same preference statement on every session.
"""
import hashlib
from datetime import datetime, timezone

COLLECTION = "corpus/preferences"


def preference_record_id(content: str) -> str:
    digest = hashlib.sha1(content.encode()).hexdigest()
    return f"pref-{digest[:12]}"


def upsert_preference(store, *, content: str, session_id: str) -> str:
    """Insert or bump a preference record. Returns the record id."""
    content = content.strip()[:300]
    record_id = preference_record_id(content)
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
            "type": "preference",
            "source": "prompt_submit_hook",
            "content": content,
            "session_id": session_id,
            "created_at": now,
            "last_seen": now,
            "count": 1,
            "sandbox": True,
            "b17": "CRPS0",
        }
    store.put(COLLECTION, record, record_id=record_id)
    return record_id
