#!/usr/bin/env python3
"""
kb_briefer.py — Task-time KB briefing.
b17: KBBR1  ΔΣ=42

Reads pending agent tasks from Postgres, runs kb_search on each task
description, and stores the top-3 relevant atoms in SOIL as a briefing
record. Agents picking up a task check soil_get("hanuman/kb_brief/<task_id>")
before acting to get pre-fetched KB context.

Called automatically from ratification_triage.py after digest generation.
Also runnable standalone:

    python3 agents/hanuman/bin/kb_briefer.py [--dry-run]
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import soil
from core.grove_gate import assert_grove as _assert_grove
from core.kb_read_log import record_read

_BRIEF_COLLECTION = "hanuman/kb_brief"
_TOP_ATOMS = 3
_MAX_TASKS = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kb_search_local(query: str, limit: int = 5) -> list[dict]:
    """Run kb_search via the MCP call shim. Returns list of atom dicts."""
    try:
        from willow.fylgja._mcp import call
        result = call("kb_search", {
            "app_id": "hanuman",
            "query": query,
            "limit": limit,
            "semantic": True,
        }, timeout=30)
        atoms = []
        if isinstance(result, dict):
            for tier in ("knowledge", "jeles_atoms", "opus_atoms"):
                atoms.extend(result.get(tier, []))
        return atoms[:limit]
    except Exception as exc:
        print(f"  [warn] kb_search failed: {exc}", file=sys.stderr)
        return []


def _brief_one(task_id: str, task_text: str, dry_run: bool = False) -> list[dict]:
    """Run kb_search on task_text, store top-N in SOIL, write read log."""
    query = task_text[:300].strip()
    atoms = _kb_search_local(query, limit=_TOP_ATOMS + 2)

    top = []
    for atom in atoms[:_TOP_ATOMS]:
        atom_id = str(atom.get("id", ""))
        entry = {
            "id": atom_id,
            "title": atom.get("title", "")[:100],
            "summary": (atom.get("summary") or "")[:300],
            "tier": atom.get("tier", ""),
        }
        top.append(entry)
        if not dry_run and atom_id:
            record_read(atom_id, source="briefer")

    if not dry_run and top:
        soil.put(_BRIEF_COLLECTION, task_id, {
            "task_id": task_id,
            "task_text": task_text[:200],
            "briefed_at": _now(),
            "atoms": top,
        })

    return top


def brief_pending_tasks(pg=None, dry_run: bool = False) -> int:
    """Brief pending tasks that lack a SOIL kb_brief record.

    Args:
        pg: Optional PgBridge instance (reused from triage). If None, creates one.
        dry_run: If True, searches KB but does not write SOIL.

    Returns:
        Count of tasks briefed.
    """
    close_pg = False
    if pg is None:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
        close_pg = True

    try:
        import psycopg2.extras
        pg._ensure_conn()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, task, submitted_by, agent
                FROM tasks
                WHERE status IS NULL OR status = 'pending'
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (_MAX_TASKS,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        # Try without status filter — older schema may not have status column
        try:
            with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, task, submitted_by, agent FROM tasks ORDER BY created_at ASC LIMIT %s",
                    (_MAX_TASKS,),
                )
                rows = cur.fetchall()
        except Exception as exc2:
            print(f"[kb_briefer] warn: could not read tasks: {exc2}", file=sys.stderr)
            rows = []
    finally:
        if close_pg:
            pg.close()

    briefed = 0
    for row in rows:
        task_id = str(row["id"])
        task_text = row.get("task", "").strip()
        if not task_text or len(task_text) < 10:
            continue

        # Skip if already briefed
        existing = soil.get(_BRIEF_COLLECTION, task_id)
        if existing:
            continue

        atoms = _brief_one(task_id, task_text, dry_run=dry_run)
        if dry_run:
            print(f"  [dry-run] {task_id}: {len(atoms)} atom(s) found for: {task_text[:60]!r}")
        elif atoms:
            print(f"  briefed {task_id}: {len(atoms)} atom(s)  ({task_text[:50]!r})")
        briefed += 1

    return briefed


if __name__ == "__main__":
    _assert_grove("kb_briefer")
    dry = "--dry-run" in sys.argv
    count = brief_pending_tasks(dry_run=dry)
    print(f"\nkb_briefer: {'would brief' if dry else 'briefed'} {count} task(s)")
