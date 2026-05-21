from __future__ import annotations

import re
from collections.abc import Mapping


_SESSION_TOKEN_RE = re.compile(r"session_handoff-(\d{4}-\d{2}-\d{2})([a-z]?)", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def latest_handoff_sort_key(
    filename: str,
    handoff_date: str | None = None,
    mtime: str | None = None,
) -> tuple[str, str, str, str]:
    """Sort by semantic handoff recency before falling back to file metadata."""
    session_date = ""
    session_suffix = ""

    match = _SESSION_TOKEN_RE.search(filename or "")
    if match:
        session_date = match.group(1)
        session_suffix = (match.group(2) or "").lower()

    if not session_date and handoff_date:
        date_match = _DATE_RE.search(handoff_date)
        if date_match:
            session_date = date_match.group(1)

    if not session_date and mtime:
        session_date = str(mtime)[:10]

    return (
        session_date,
        session_suffix,
        filename or "",
        mtime or "",
    )


def handoff_select_sql(conn) -> str:
    """Build SELECT for handoff_latest — tolerates pre-v2 schemas without agreements/capabilities."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(handoffs)")
    cols = {row[1] for row in cur.fetchall()}
    agreements = "h.agreements" if "agreements" in cols else "NULL AS agreements"
    capabilities = "h.capabilities" if "capabilities" in cols else "NULL AS capabilities"
    return (
        "SELECT f.filename, f.mtime, h.handoff_date, h.summary,"
        f" h.open_threads, h.questions, {agreements}, {capabilities}"
        " FROM handoffs h JOIN files f ON h.file_id = f.id"
    )


def select_latest_handoff(rows: list[Mapping[str, object]]) -> Mapping[str, object] | None:
    """Return the most recent handoff row from SQLite-style mapping rows."""
    if not rows:
        return None

    def _value(row: Mapping[str, object], key: str) -> object:
        if hasattr(row, "keys") and key in row.keys():
            return row[key]
        return ""

    return max(
        rows,
        key=lambda row: latest_handoff_sort_key(
            str(_value(row, "filename")),
            str(_value(row, "handoff_date") or ""),
            str(_value(row, "mtime") or ""),
        ),
    )
