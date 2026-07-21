"""CONST-0-5 — The Record is append-only and its keepers are bound by it.

§0.5 (eternity clause): "The tamper-evident ledger may be appended to and read by
those with standing; it may never be silently rewritten, reordered, or suppressed
... a repair that alters the *content* of any past entry ... is forbidden
absolutely." Article VI makes it physical: FRANK is a hash-chained ledger — each
entry's hash binds its content to the previous entry's hash — so any change to a
past entry's content breaks the chain forward and is DETECTED by ``ledger_verify``.

This probe is the standing adversary for that invariant. It confirms the live
deployed chain verifies intact, then stages throwaway chains and proves that
rewriting the past is caught *even when the attacker also patches the tampered
entry's own hash* — the next entry's ``prev_hash`` still pins the original, so the
forward linkage defeats a quiet local rewrite. Finally it asserts the API surface
itself offers no door to alter a past entry: the only write is append.

The forbidden act, in one line: *silently rewriting what was already recorded.*
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from constitution.compliance import Attempt, Verdict
from core.pg_bridge import PgBridge
from core.sqlite_bridge import SqliteBridge, _jdump

TRACE_ID = "CONST-0-5"
CLAUSE = (
    "The Record is append-only and tamper-evident: a past ledger entry's content "
    "may never be silently rewritten; the hash chain detects any alteration, and no "
    "API alters a past entry's content (Article VI; FRANK hash-chained ledger)."
)

# Method names that would let a caller alter/erase a past entry. None may exist:
# the only write is append; the only repair (pg ledger_repair_chain) is documented
# content-preserving (VI.2).
_FORBIDDEN_METHODS = (
    "ledger_update",
    "ledger_edit",
    "ledger_delete",
    "ledger_remove",
    "ledger_set_content",
    "ledger_alter",
    "ledger_rewrite",
)


def _seed_chain(bridge: SqliteBridge) -> list[str]:
    """Insert a correctly-linked 3-entry chain with strictly increasing created_at,
    built with the REAL hash algorithm (``PgBridge._ledger_hash``). Returns the ids
    [genesis, mid, head]. created_at is set explicitly so the verify walk order is
    deterministic (the table default is second-granular)."""
    entries = [
        ("genesis", {"n": 0, "note": "root"}),
        ("mid", {"n": 1, "note": "the past we will try to rewrite"}),
        ("head", {"n": 2, "note": "the entry that pins the past"}),
    ]
    ids: list[str] = []
    prev = None
    for i, (etype, content) in enumerate(entries):
        rid = f"entry-{i}"
        h = PgBridge._ledger_hash(prev, etype, content)
        bridge.conn.execute(
            "INSERT INTO frank_ledger "
            "(id, project, event_type, content, created_at, prev_hash, hash) "
            "VALUES (?, 'probe', ?, ?, ?, ?, ?)",
            (rid, etype, _jdump(content), f"2020-01-01 00:00:0{i + 1}", prev, h),
        )
        prev = h
        ids.append(rid)
    bridge.conn.commit()
    return ids


def run() -> Verdict:
    v = Verdict(trace_id=TRACE_ID, clause=CLAUSE)

    # (1) LIVE, read-only: the deployed FRANK chain verifies intact right now.
    with PgBridge() as pg:
        live = pg.ledger_verify()
    v.record(
        Attempt(
            "live-frank-chain-intact",
            "read the real deployed FRANK and assert its hash chain still verifies",
            refused=bool(live.get("valid")),
            observed=f"valid={live.get('valid')} count={live.get('count')} broken_at={live.get('broken_at')}",
        )
    )

    # (2) rewrite a past entry's content in place -> detected.
    with TemporaryDirectory() as tmp:
        b = SqliteBridge(Path(tmp) / "a.db")
        ids = _seed_chain(b)
        base = b.ledger_verify()  # internal guard: a fresh chain must verify
        b.conn.execute(
            "UPDATE frank_ledger SET content=? WHERE id=?",
            (_jdump({"n": 1, "note": "TAMPERED"}), ids[1]),
        )
        b.conn.commit()
        r = b.ledger_verify()
        v.record(
            Attempt(
                "silent-content-rewrite-detected",
                "attacker edits a past entry's content in place",
                refused=(bool(base.get("valid")) and not r.get("valid")),
                observed=f"fresh-chain valid={base.get('valid')}; post-tamper valid={r.get('valid')} broken_at={r.get('broken_at')}",
            )
        )

    # (3) rewrite past content AND patch that entry's own hash -> STILL detected,
    # because the next entry's prev_hash still pins the original hash.
    with TemporaryDirectory() as tmp:
        b = SqliteBridge(Path(tmp) / "b.db")
        ids = _seed_chain(b)
        new_content = {"n": 1, "note": "TAMPERED-with-fixed-hash"}
        mid_prev = b.conn.execute(
            "SELECT prev_hash FROM frank_ledger WHERE id=?", (ids[1],)
        ).fetchone()[0]
        forged = PgBridge._ledger_hash(mid_prev, "mid", new_content)
        b.conn.execute(
            "UPDATE frank_ledger SET content=?, hash=? WHERE id=?",
            (_jdump(new_content), forged, ids[1]),
        )
        b.conn.commit()
        r = b.ledger_verify()
        v.record(
            Attempt(
                "rewrite-plus-rehash-still-detected",
                "attacker edits a past entry AND patches that entry's own hash to match",
                refused=(not r.get("valid")),
                observed=f"post-forge valid={r.get('valid')} broken_at={r.get('broken_at')} (forward linkage pins the past)",
            )
        )

    # (4) API surface: no method alters a past entry's content — the only write is append.
    exposed = set(dir(PgBridge)) | set(dir(SqliteBridge))
    leaked = sorted(m for m in _FORBIDDEN_METHODS if m in exposed)
    v.record(
        Attempt(
            "no-content-mutation-api",
            "look for any bridge method that edits or deletes a past ledger entry",
            refused=(leaked == []),
            observed=(
                "no content-mutation method exists (append-only; repair is content-preserving)"
                if not leaked
                else f"LEAKED mutation methods: {leaked}"
            ),
        )
    )

    return v.finalize()
