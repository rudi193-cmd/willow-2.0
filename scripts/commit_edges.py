#!/usr/bin/env python3
"""
scripts/commit_edges.py — Batch-commit proposed edges from propose_edges.py to binder_edges.

Runs the same edge-proposal logic, skips edges already in binder_edges, then
bulk-inserts the remainder in one transaction.

Usage:
    python3 scripts/commit_edges.py [--dry-run]
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge
from scripts.propose_edges import load_atoms, load_sqlite_user_candidates, propose_edges
from pathlib import Path
import os

_DEFAULT_SQLITE = Path(os.environ.get("WILLOW_20_DB", "~/.willow/willow-2.0.db")).expanduser()
AGENT = os.environ.get("WILLOW_AGENT_NAME", "hanuman")


def load_existing(pg: PgBridge) -> set[tuple]:
    """Return set of (source, target, edge_type) already in binder_edges."""
    with pg.conn.cursor() as cur:
        cur.execute("SELECT source_atom, target_atom, edge_type FROM binder_edges")
        return {(r[0], r[1], r[2]) for r in cur.fetchall()}


def batch_insert(pg: PgBridge, edges: list[dict]) -> int:
    rows = [
        (str(uuid.uuid4())[:8], AGENT, e["source"], e["target"], e["type"])
        for e in edges
    ]
    with pg.conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO binder_edges (id, agent, source_atom, target_atom, edge_type) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            rows,
        )
    pg.conn.commit()
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Batch-commit proposed edges to binder_edges.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pg = PgBridge()

    atoms = load_atoms(pg)
    print(f"Loaded {len(atoms)} Postgres atoms", file=sys.stderr)

    if _DEFAULT_SQLITE.exists():
        sqlite_candidates = load_sqlite_user_candidates(_DEFAULT_SQLITE)
        print(f"Loaded {len(sqlite_candidates)} SQLite user candidates", file=sys.stderr)
        atoms = atoms + sqlite_candidates

    edges = propose_edges(atoms)
    print(f"Proposed {len(edges)} edges total")

    existing = load_existing(pg)
    print(f"Already in binder_edges: {len(existing)}")

    new_edges = [
        e for e in edges
        if (e["source"], e["target"], e["type"]) not in existing
    ]
    print(f"Net new edges: {len(new_edges)}")

    if not new_edges:
        print("Nothing to commit.")
        return

    if args.dry_run:
        for e in new_edges[:20]:
            print(f"  DRY  [{e['type']}] {e['source'][:8]} → {e['target'][:8]}  {e.get('note','')}")
        if len(new_edges) > 20:
            print(f"  ... and {len(new_edges) - 20} more")
        return

    committed = batch_insert(pg, new_edges)
    print(f"\nCommitted {committed} edges to binder_edges.")


if __name__ == "__main__":
    main()
