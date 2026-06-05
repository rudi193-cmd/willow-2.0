"""Session composite store keys — aligned between stop (write) and session_start (read)."""
from __future__ import annotations

from datetime import datetime, timedelta


def session_composite_record_id(session_id: str) -> str:
    """Canonical SOIL id for {agent}/sessions/store (matches stop hook write)."""
    sid = (session_id or "unknown")[:8]
    return f"session-{sid}"


def session_composite_lookup_ids(session_id: str = "") -> list[str]:
    """
    Ordered ids to try on session start.
    Primary: session-{session_id[:8]}. Legacy fallbacks: session-YYYYMMDD (pre-PR3).
    """
    ids: list[str] = []
    if session_id:
        primary = session_composite_record_id(session_id)
        ids.append(primary)
    today = datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    for key in (f"session-{today}", f"session-{yesterday}"):
        if key not in ids:
            ids.append(key)
    return ids
