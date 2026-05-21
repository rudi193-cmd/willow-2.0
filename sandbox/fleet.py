"""
sandbox/fleet.py — Fleet binding for WLGSM.
b17: GSFLX · ΔΣ=42

Wraps create_issue() and advance() with live Willow side-effects.
All side-effects are best-effort — a Postgres failure does not block the
state transition; it logs to stderr and continues.

State → Willow action:
  issue      → soil_put  (hanuman/gitshaped_changes)
  → draft    → fork  row in Postgres forks table; fork_id written to record
  → open     → KB seed atom; kb_seed_hint written to record + Grove post
  → checks   → soil_update only (Kart task wiring: future)
  → review   → Grove post
  → merged   → fork row marked merged in Postgres
  → release  → FRANK ledger_write
  → archived → KB atom (domain=archived) + SOIL soft-delete
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox.model import ChangeRecord, ShapeState, create_issue
from sandbox.engine import GitShapedError, advance as _advance

AGENT = os.environ.get("WILLOW_AGENT_NAME", "hanuman")
COLLECTION = f"{AGENT}/gitshaped_changes"


_GROVE_FALLBACK_CHANNEL = "fleet"


# ── Grove helper ──────────────────────────────────────────────────────────────

def _grove_post(change, state_label: str) -> None:
    """Post a structured state-change message to the change's Grove channel."""
    channel = change.grove_channel or _GROVE_FALLBACK_CHANNEL
    lines = [
        f"[wlgsm] {change.id} {state_label}",
        f"Title: {change.title}",
    ]
    if change.subject:
        lines.append(f"Subject: {change.subject}")
    if change.fork_id:
        lines.append(f"Fork: {change.fork_id}")
    content = "\n".join(lines)

    try:
        from core.grove_db import get_connection, release_connection, list_channels, create_channel, send_message
        conn = get_connection()
        try:
            channels = list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel), None)
            if not ch:
                ch = create_channel(conn, name=channel, channel_type="group")
            send_message(conn, channel_id=ch["id"], sender=AGENT, content=content)
        finally:
            release_connection(conn)
    except Exception as e:
        sys.stderr.write(f"[fleet] grove_post failed (channel={channel}): {e}\n")


# ── SOIL helpers ──────────────────────────────────────────────────────────────

def _soil_put(record_id: str, data: dict) -> None:
    from core.soil import put
    put(COLLECTION, record_id, data)


def _soil_soft_delete(record_id: str) -> None:
    """Mark a SOIL record deleted=1 without erasing it."""
    from core.soil import _db, _conn
    db = _db(COLLECTION)
    if not db.exists():
        return
    conn = _conn(db)
    conn.execute(
        "UPDATE records SET deleted=1, updated_at=datetime('now') WHERE id=?",
        (record_id,),
    )
    conn.commit()
    conn.close()


def fleet_list() -> list[dict]:
    """Return all non-deleted change records from SOIL."""
    from core.soil import all_records
    return all_records(COLLECTION)


def fleet_get(change_id: str) -> dict | None:
    from core.soil import get
    return get(COLLECTION, change_id)


# ── Public API ────────────────────────────────────────────────────────────────

def fleet_create(
    title: str,
    *,
    subject: str = "",
    grove_channel: str = "",
    kb_seed_hint: str = "",
    flag_id: str = "",
) -> ChangeRecord:
    """Create a change at state *issue* and persist to SOIL."""
    change = create_issue(
        title,
        subject=subject,
        grove_channel=grove_channel,
        kb_seed_hint=kb_seed_hint,
        flag_id=flag_id,
    )
    _soil_put(change.id, change.to_json())
    return change


def fleet_advance(
    change: ChangeRecord,
    to_state: ShapeState,
    *,
    actor: str,
    note: str = "",
) -> ChangeRecord:
    """Advance state machine + trigger Willow side-effects. Raises GitShapedError on bad transition."""
    change = _advance(change, to_state, actor=actor, note=note)

    # Per-state side-effects (best-effort)
    try:
        if to_state == ShapeState.draft:
            _on_draft(change, actor)
        elif to_state == ShapeState.open:
            _on_open(change)
        elif to_state == ShapeState.review:
            _on_review(change)
        elif to_state == ShapeState.merged:
            _on_merged(change, actor, note)
        elif to_state == ShapeState.release:
            _on_release(change)
        elif to_state == ShapeState.archived:
            _on_archived(change)
    except Exception as e:
        sys.stderr.write(f"[fleet] side-effect error ({to_state.value}): {e}\n")

    _soil_put(change.id, change.to_json())
    return change


# ── State handlers ────────────────────────────────────────────────────────────

def _on_draft(change: ChangeRecord, actor: str) -> None:
    if change.fork_id:
        return
    from core.pg_bridge import PgBridge
    pg = PgBridge()
    fork_id = f"fork-{uuid.uuid4().hex[:8]}"
    with pg.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO forks (id, title, created_by, topic, status) "
            "VALUES (%s, %s, %s, %s, 'open')",
            (fork_id, change.title, actor, change.subject or change.id),
        )
    pg.conn.commit()
    change.fork_id = fork_id
    sys.stderr.write(f"[fleet] fork created: {fork_id}\n")


def _on_open(change: ChangeRecord) -> None:
    if not change.kb_seed_hint:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
        atom_id = pg.ingest_atom(
            title=f"[wlgsm:{change.id}] {change.title}",
            summary=f"Open change — subject: {change.subject or 'n/a'}. Grove: {change.grove_channel or 'n/a'}.",
            source_type="wlgsm",
            source_id=change.id,
            category="change/open",
        )
        if atom_id:
            change.kb_seed_hint = atom_id
            sys.stderr.write(f"[fleet] KB seed atom: {atom_id}\n")
    _grove_post(change, "opened")


def _on_review(change: ChangeRecord) -> None:
    _grove_post(change, "review")


def _on_merged(change: ChangeRecord, actor: str, note: str) -> None:
    if not change.fork_id:
        return
    from core.pg_bridge import PgBridge
    pg = PgBridge()
    with pg.conn.cursor() as cur:
        cur.execute(
            "UPDATE forks SET status='merged', merged_at=now(), outcome_note=%s WHERE id=%s",
            (note or f"merged by {actor}", change.fork_id),
        )
    pg.conn.commit()
    sys.stderr.write(f"[fleet] fork merged: {change.fork_id}\n")


def _on_release(change: ChangeRecord) -> None:
    from core.pg_bridge import PgBridge
    pg = PgBridge()
    pg.ledger_append(
        project="wlgsm",
        event_type="change_released",
        content={
            "change_id": change.id,
            "title": change.title,
            "subject": change.subject,
            "fork_id": change.fork_id,
            "kb_seed": change.kb_seed_hint,
            "agent": AGENT,
        },
    )
    sys.stderr.write(f"[fleet] ledger entry written for {change.id}\n")


def _on_archived(change: ChangeRecord) -> None:
    from core.pg_bridge import PgBridge
    pg = PgBridge()
    pg.ingest_atom(
        title=f"[archived:{change.id}] {change.title}",
        summary=f"Archived WLGSM change. Subject: {change.subject or 'n/a'}.",
        source_type="wlgsm",
        source_id=change.id,
        category="change/archived",
        domain="archived",
    )
    _soil_soft_delete(change.id)
    sys.stderr.write(f"[fleet] change archived: {change.id}\n")
