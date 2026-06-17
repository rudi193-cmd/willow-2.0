"""Deduplicated scope redirect writes for corpus/scope_redirects.

Behavioral signal — user changing direction mid-task ("actually don't",
"let's not", "skip that for now"). Distinct from corrections (which say
you did something wrong) and preferences (which state a standing rule).
A redirect says: not this, not now, different path. Mirrors corrections.py.
b17: CRPS0
"""
import hashlib
from datetime import datetime, timezone

COLLECTION = "corpus/scope_redirects"


def scope_redirect_record_id(content: str) -> str:
    digest = hashlib.sha1(content.encode()).hexdigest()
    return f"redir-{digest[:12]}"


def upsert_scope_redirect(store, *, content: str, session_id: str) -> str:
    """Insert or bump a scope redirect record. Returns the record id."""
    content = content.strip()[:300]
    record_id = scope_redirect_record_id(content)
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
            "type": "scope_redirect",
            "valence": "negative",
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
