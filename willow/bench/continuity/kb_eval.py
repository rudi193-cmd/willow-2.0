"""KB-backed WCE helpers — superseded atoms and ledger boot surfacing."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2.extras

from core.pg_bridge import PgBridge

_ATOM_ID_LEN = 8


def _parse_ts(raw: object) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        ts = raw
    elif isinstance(raw, (int, float)):
        ts = datetime.fromtimestamp(float(raw), tz=timezone.utc)
    elif isinstance(raw, str):
        if not raw.strip():
            return None
        try:
            from dateutil import parser as _dp  # type: ignore

            ts = _dp.parse(raw)
        except Exception:
            return None
    else:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def superseded_between(
    pg: PgBridge,
    *,
    valid_at: datetime,
    invalid_before: datetime,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Atoms invalidated or tier-superseded between session N and N+1."""
    pg._ensure_conn()
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, title, summary, tier, valid_at, invalid_at, updated_at
            FROM knowledge
            WHERE valid_at <= %s
              AND (
                (invalid_at IS NOT NULL AND invalid_at > %s AND invalid_at <= %s)
                OR (tier = 'superseded' AND updated_at > %s AND updated_at <= %s)
              )
            ORDER BY COALESCE(invalid_at, updated_at) DESC
            LIMIT %s
            """,
            (valid_at, valid_at, invalid_before, valid_at, invalid_before, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def ledger_atoms_written(
    pg: PgBridge,
    *,
    project: str,
    before: datetime,
    limit: int = 3,
) -> list[str]:
    """Top atom IDs from FRANK `atoms_written` entries before a handoff timestamp."""
    pg._ensure_conn()
    ids: list[str] = []
    with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT content, created_at
            FROM frank_ledger
            WHERE project = %s AND created_at <= %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (project, before),
        )
        for row in cur.fetchall():
            content = row.get("content")
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = {}
            if not isinstance(content, dict):
                continue
            written = content.get("atoms_written") or []
            if isinstance(written, str):
                try:
                    written = json.loads(written)
                except json.JSONDecodeError:
                    written = []
            if not isinstance(written, list):
                continue
            for atom_id in written:
                aid = str(atom_id).strip().upper()
                if len(aid) == _ATOM_ID_LEN and aid not in ids:
                    ids.append(aid)
                if len(ids) >= limit:
                    return ids
    return ids[:limit]


def pair_time_bounds(n: dict[str, Any], n1: dict[str, Any]) -> tuple[datetime, datetime]:
    """Approximate session N end → N+1 start from handoff metadata."""
    now = datetime.now(timezone.utc)
    t_n = _parse_ts(n.get("mtime")) or _parse_ts(n.get("date")) or now
    t_n1 = _parse_ts(n1.get("mtime")) or _parse_ts(n1.get("date")) or now
    if t_n1 < t_n:
        t_n, t_n1 = t_n1, t_n
    return t_n, t_n1
