"""Deduplicated correction writes for corpus/corrections.

Hooks fire on every blocked call and every correction-shaped prompt; uuid-keyed
inserts grew the collection to 768 rows (158 of them one identical sentence).
One row per unique (source, content) with a hit counter keeps the collection
readable at boot.
"""
import hashlib
from datetime import datetime, timezone

COLLECTION = "corpus/corrections"


def correction_record_id(source: str, content: str) -> str:
    digest = hashlib.sha1(f"{source}|{content}".encode()).hexdigest()
    return f"corr-{digest[:12]}"


def upsert_correction(store, *, source: str, content: str, session_id: str) -> str:
    """Insert or bump a correction record. Returns the record id."""
    content = content.strip()[:300]
    record_id = correction_record_id(source, content)
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
            "type": "correction",
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
