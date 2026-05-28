"""
kb_read_log.py — KB atom read-event log.
b17: KBRL1  ΔΣ=42

Tracks when KB atoms are surfaced to agents. Foundation for the unread-atom
digest source and task briefer. Stored in SOIL — non-blocking, never raises.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from core import soil
from core.agent_namespace import soil_collection


def _collection() -> str:
    return soil_collection("kb_read_log")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_ago(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return 999.0


def record_read(atom_id: str, source: str) -> None:
    """Log that atom_id was surfaced by source (e.g. 'triage', 'briefer', 'boot').

    Non-blocking — if SOIL is unavailable, logs a warning and returns.
    """
    if not atom_id:
        return
    try:
        existing: dict[str, Any] = soil.get(_collection(), atom_id) or {}
        now = _now()
        sources = existing.get("sources", [])
        if source not in sources:
            sources.append(source)
        soil.put(_collection(), atom_id, {
            "atom_id": atom_id,
            "first_read_at": existing.get("first_read_at", now),
            "last_read_at": now,
            "read_count": existing.get("read_count", 0) + 1,
            "sources": sources,
        })
    except Exception as exc:
        print(f"[kb_read_log] warn: could not record read for {atom_id}: {exc}", file=sys.stderr)


def was_read_since(atom_id: str, since_days: int = 7) -> bool:
    """Return True if atom_id was surfaced within the last since_days days."""
    try:
        record = soil.get(_collection(), atom_id)
        if not record:
            return False
        last_read = record.get("last_read_at", "")
        return _days_ago(last_read) <= since_days
    except Exception:
        return False


def unread_atom_ids(since_days: int = 7) -> set[str]:
    """Return set of atom_ids that have a read log entry but last_read_at is older than since_days.

    Note: atoms with NO log entry are not returned here — they have no ID to return.
    The caller should query Postgres for ALL valid atoms and diff against this set
    (plus any atoms where was_read_since returns False).
    """
    result: set[str] = set()
    try:
        records = soil.all_records(_collection())
        for r in records:
            atom_id = r.get("atom_id", "")
            if not atom_id:
                continue
            last_read = r.get("last_read_at", "")
            if _days_ago(last_read) > since_days:
                result.add(atom_id)
    except Exception as exc:
        print(f"[kb_read_log] warn: could not list read log: {exc}", file=sys.stderr)
    return result


def read_atoms_set(since_days: int = 7) -> set[str]:
    """Return set of atom_ids read within the last since_days days (inverse of unread_atom_ids)."""
    result: set[str] = set()
    try:
        records = soil.all_records(_collection())
        for r in records:
            atom_id = r.get("atom_id", "")
            if not atom_id:
                continue
            last_read = r.get("last_read_at", "")
            if _days_ago(last_read) <= since_days:
                result.add(atom_id)
    except Exception as exc:
        print(f"[kb_read_log] warn: could not list read log: {exc}", file=sys.stderr)
    return result
