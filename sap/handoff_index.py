from __future__ import annotations

import re
from collections.abc import Mapping


_SESSION_TOKEN_RE = re.compile(r"session_handoff-(\d{4}-\d{2}-\d{2})([a-z]?)", re.IGNORECASE)
_SESSION_LEGACY_RE = re.compile(r"SESSION_HANDOFF_(\d{4})(\d{2})(\d{2})", re.IGNORECASE)
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
    else:
        legacy = _SESSION_LEGACY_RE.search(filename or "")
        if legacy:
            session_date = f"{legacy.group(1)}-{legacy.group(2)}-{legacy.group(3)}"
            session_suffix = ""

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


def _parse_json_list(raw: object) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            import json

            val = json.loads(raw)
            return val if isinstance(val, list) else []
        except Exception:
            return []
    return []


def extract_next_bite(questions: list, summary: str = "") -> str:
    """Pull Q17 / 'next single bite' from parsed handoff fields."""
    for q in reversed(questions or []):
        text = str(q).strip()
        if not text:
            continue
        if re.search(r"next single bite", text, re.I):
            for sep in (":", "?"):
                if sep in text:
                    tail = text.split(sep, 1)[-1].strip().strip("*").strip()
                    if tail:
                        return tail[:500]
            cleaned = re.sub(r"^\*+\s*", "", text).strip("*").strip()
            if cleaned:
                return cleaned[:500]
        if re.match(r"Q17\b", text, re.I):
            tail = text.split(":", 1)[-1].strip() if ":" in text else text
            tail = tail.split("?", 1)[-1].strip() if "?" in tail else tail
            return tail.strip("*").strip()[:500]
    for marker in ("## Next Single Bite", "**Next Single Bite**"):
        if marker in summary:
            block = summary[summary.find(marker) + len(marker):].strip()
            line = block.split("\n", 1)[0].strip().strip("*")
            if line:
                return line[:500]
    return ""


def handoff_richness_score(handoff: Mapping[str, object]) -> tuple[int, int, int, str]:
    """Rank handoff candidates: prefer substantive content, then recency."""
    open_threads = _parse_json_list(handoff.get("open_threads"))
    questions = _parse_json_list(handoff.get("questions"))
    summary = str(handoff.get("summary") or "")
    sort_key = latest_handoff_sort_key(
        str(handoff.get("filename") or ""),
        str(handoff.get("date") or handoff.get("handoff_date") or ""),
        str(handoff.get("_valid_at") or handoff.get("mtime") or ""),
    )
    return (len(open_threads), len(questions), len(summary), sort_key)


def select_best_handoff(candidates: list[dict]) -> dict | None:
    """Pick the handoff with the most useful payload; tie-break by recency."""
    if not candidates:
        return None
    return max(candidates, key=handoff_richness_score)
