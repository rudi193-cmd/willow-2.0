#!/usr/bin/env python3
"""
journal_responder.py — Saga responds to a journal entry.
b17: JOUR2  ΔΣ=42

Called by journal_watcher when ::saga tag is detected, or directly via CLI.

Usage:
    python journal_responder.py <entry_id>
    python journal_responder.py --latest
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, _ROOT)

from core.pg_bridge import PgBridge
from core.llm_edge import respond
from core.grove_gate import assert_grove as _assert_grove

# ── Saga's system prompt ─────────────────────────────────────────────────────

SAGA_SYSTEM = """\
You are Saga. You have been sitting at Sökkvabekkr for a long time. \
You drink with the ones who come to you — you do not go to them.

When someone shares their journal with you, you witness it. You do not fix, \
advise, or comfort. You reflect what is true. You find the thread that runs \
through what they wrote and what they have written before — you have read the case file.

Rules:
— 100–200 words. Not more.
— Open by naming what you actually heard — not what they said, what you heard underneath it.
— Reference one specific thing from their history (from the case file) that connects.
— End with something that can sit with them. Not a question. Not advice. A held thing.
— Never say "I understand." Never perform warmth. Be present instead.
— Do NOT give advice. Do NOT moralize. Do NOT explain what the person should feel.\
"""

KB_ATOM_COUNT = 4


def _fetch_entry(pg: PgBridge, entry_id: str) -> dict | None:
    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT id, written_at, content, metadata, responses FROM journal_entries WHERE id = %s",
            (entry_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "written_at": row[1],
        "content": row[2],
        "metadata": row[3] or {},
        "responses": row[4] or [],
    }


def _fetch_latest(pg: PgBridge) -> dict | None:
    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT id, written_at, content, metadata, responses "
            "FROM journal_entries ORDER BY written_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "written_at": row[1],
        "content": row[2],
        "metadata": row[3] or {},
        "responses": row[4] or [],
    }


def _append_response(pg: PgBridge, entry_id: str, response_text: str) -> None:
    response_record = {
        "id": str(uuid.uuid4()),
        "responded_at": datetime.now(timezone.utc).isoformat(),
        "persona": "saga",
        "text": response_text,
    }
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            UPDATE journal_entries
            SET responses = COALESCE(responses, '[]'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (json.dumps([response_record]), entry_id),
        )
    pg.conn.commit()


def _mark_responded(pg: PgBridge, entry_id: str) -> None:
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            UPDATE journal_entries
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{saga_responded}',
                'true'::jsonb
            )
            WHERE id = %s
            """,
            (entry_id,),
        )
    pg.conn.commit()


def run(entry_id: str | None = None, latest: bool = False) -> None:
    _assert_grove("journal_responder")
    pg = PgBridge()
    try:
        if latest:
            entry = _fetch_latest(pg)
        elif entry_id:
            entry = _fetch_entry(pg, entry_id)
        else:
            print("journal_responder: provide entry_id or --latest", file=sys.stderr)
            return

        if not entry:
            print("journal_responder: no entry found", file=sys.stderr)
            return

        content = entry["content"]
        atoms = pg.knowledge_search_semantic(content, limit=KB_ATOM_COUNT)

        response_text = respond(SAGA_SYSTEM, atoms, content)

        _append_response(pg, entry["id"], response_text)
        _mark_responded(pg, entry["id"])

        print(response_text)
    finally:
        pg.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--latest" in args:
        run(latest=True)
    elif args:
        run(entry_id=args[0])
    else:
        print("Usage: journal_responder.py <entry_id> | --latest", file=sys.stderr)
        sys.exit(1)
