#!/usr/bin/env python3
"""
scripts/ratify_edges.py — Promote proposed binder_edges to active (or reject dead ones).

Validation rule: both source_atom and target_atom must exist in knowledge
with invalid_at IS NULL. Edges referencing missing or expired atoms are
marked 'rejected'. All others are promoted to 'active'.

Usage:
    python3 scripts/ratify_edges.py [--dry-run] [--batch-size N]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge


def load_proposed(pg: PgBridge) -> list[dict]:
    with pg.conn.cursor() as cur:
        cur.execute("""
            SELECT id, source_atom, target_atom, edge_type
            FROM binder_edges
            WHERE status = 'proposed'
            ORDER BY created_at
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def load_live_atom_ids(pg: PgBridge) -> set[str]:
    with pg.conn.cursor() as cur:
        cur.execute("SELECT id FROM knowledge WHERE invalid_at IS NULL")
        return {r[0] for r in cur.fetchall()}


def apply_batch(pg: PgBridge, promote_ids: list[str], reject_ids: list[str], dry_run: bool) -> dict:
    if dry_run:
        return {"promoted": len(promote_ids), "rejected": len(reject_ids), "dry_run": True}

    t0 = time.monotonic()
    with pg.conn.cursor() as cur:
        if promote_ids:
            cur.execute(
                "UPDATE binder_edges SET status = 'active' WHERE id = ANY(%s)",
                (promote_ids,),
            )
        if reject_ids:
            cur.execute(
                "UPDATE binder_edges SET status = 'rejected' WHERE id = ANY(%s)",
                (reject_ids,),
            )
    pg.conn.commit()
    elapsed = round(time.monotonic() - t0, 2)

    pg.ledger_append("binder_edges", "ratify_edges", {
        "promoted": len(promote_ids),
        "rejected": len(reject_ids),
        "elapsed_s": elapsed,
    })

    return {"promoted": len(promote_ids), "rejected": len(reject_ids), "elapsed_s": elapsed}


def main():
    ap = argparse.ArgumentParser(description="Ratify proposed binder_edges.")
    ap.add_argument("--dry-run", action="store_true", help="Report without writing")
    ap.add_argument("--batch-size", type=int, default=500,
                    help="Rows per UPDATE (default 500)")
    args = ap.parse_args()

    pg = PgBridge()
    pg._ensure_conn()

    print("Loading proposed edges…", file=sys.stderr)
    edges = load_proposed(pg)
    print(f"  {len(edges)} proposed edges", file=sys.stderr)

    print("Loading live atom IDs…", file=sys.stderr)
    live = load_live_atom_ids(pg)
    print(f"  {len(live)} live atoms", file=sys.stderr)

    promote_ids, deferred = [], []
    for e in edges:
        if e["source_atom"] in live and e["target_atom"] in live:
            promote_ids.append(e["id"])
        else:
            deferred.append(e["id"])

    print(f"\nValidation summary:")
    print(f"  → promote (both atoms live):  {len(promote_ids)}")
    print(f"  → deferred (atom not in PG):  {len(deferred)}  (left as 'proposed')")

    if not edges:
        print("Nothing to do.")
        return

    if args.dry_run:
        print("\n[DRY RUN] — no changes written.")
        if deferred:
            print("\nSample deferred edges (source atom not yet in Postgres KB):")
            for e in [x for x in edges if x["id"] in set(deferred[:5])]:
                src_ok = "✓" if e["source_atom"] in live else "✗"
                tgt_ok = "✓" if e["target_atom"] in live else "✗"
                print(f"  [{e['edge_type']}] src={src_ok}{e['source_atom'][:8]} tgt={tgt_ok}{e['target_atom'][:8]}")
        return

    # Batch promote-only; deferred edges stay 'proposed' untouched
    total_promoted = 0
    bs = args.batch_size
    for i in range(0, max(len(promote_ids), 1), bs):
        p_batch = promote_ids[i:i + bs]
        if not p_batch:
            break
        r = apply_batch(pg, p_batch, [], dry_run=False)
        total_promoted += r["promoted"]
        print(f"  batch {i // bs + 1}: +{r['promoted']} active", file=sys.stderr)

    pg.ledger_append("binder_edges", "ratify_edges_complete", {
        "total_promoted": total_promoted,
        "total_deferred": len(deferred),
    })

    print(f"\nDone — {total_promoted} promoted to active, {len(deferred)} deferred (still proposed).")


if __name__ == "__main__":
    main()
