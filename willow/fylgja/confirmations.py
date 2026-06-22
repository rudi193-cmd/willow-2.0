"""Deduplicated confirmation writes for corpus/confirmations.

Positive signal — user approving agent behavior ("yes exactly", "perfect",
"good call", "keep doing that"). Mirrors corrections.py. Shorter minimum
length than corrections (4 chars) because confirmations are naturally brief.
b17: CRPS0
"""
import hashlib
from datetime import datetime, timezone

COLLECTION = "corpus/confirmations"


def confirmation_record_id(content: str) -> str:
    digest = hashlib.sha1(content.encode()).hexdigest()
    return f"conf-{digest[:12]}"


def upsert_confirmation(
    store,
    *,
    content: str,
    session_id: str,
    source: str = "prompt_submit_hook",
) -> str:
    """Insert or bump a confirmation record. Returns the record id."""
    content = content.strip()[:300]
    record_id = confirmation_record_id(content)
    now = datetime.now(timezone.utc).isoformat()
    existing = store.get(COLLECTION, record_id)
    if existing:
        record = dict(existing)
        record["count"] = int(existing.get("count", 1)) + 1
        record["last_seen"] = now
        record["session_id"] = session_id
        if source:
            record["source"] = source
    else:
        record = {
            "id": record_id,
            "type": "confirmation",
            "valence": "positive",
            "source": source,
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
