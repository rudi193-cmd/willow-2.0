#!/usr/bin/env python3
"""
sleep_consolidation.py — Nightly KB consolidation (NREM phase).
b17: SCM01

Runs after midnight. Two passes:
1. NREM: find near-identical KB atoms (same project, similar title+summary),
   flag older duplicates with invalid_at so search skips them.
2. Flag contradictions: find atoms with 'same title prefix, different summary'
   in recent vs old — log to frank_ledger for Hanuman to resolve.

Usage:
    python3 scripts/sleep_consolidation.py [--dry-run]

Safe to run repeatedly — idempotent. Skips already-invalidated atoms.
"""
import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge

SIMILARITY_THRESHOLD = 0.85   # title overlap ratio for dedup
RECENCY_DAYS = 14              # atoms newer than this are "recent"


def title_similarity(a: str, b: str) -> float:
    """Jaccard similarity on word sets of two titles."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def nrem_dedup(pg, dry_run: bool) -> dict:
    """Find and invalidate exact-title duplicate atoms using SQL GROUP BY."""
    stats = {"scanned": 0, "deduped": 0}
    now = datetime.now(timezone.utc)

    with pg.conn.cursor() as cur:
        # Count active atoms (excludes sessions/archived — too many unique entries)
        cur.execute("""
            SELECT COUNT(*) FROM public.knowledge
            WHERE invalid_at IS NULL AND title IS NOT NULL
              AND project NOT IN ('sessions', 'archived', 'global', 'revelation', 'ttrpg', 'utety', 'grove_tonight', 'history', 'dark_matter', 'grove_architecture', 'die-namic', 'grove_general')
        """)
        stats["scanned"] = cur.fetchone()[0]

        # Find exact title duplicates within the same project — SQL does the heavy lifting
        cur.execute("""
            SELECT project, LOWER(title) AS ltitle, COUNT(*) AS cnt,
                   MIN(created_at) AS oldest
            FROM public.knowledge
            WHERE invalid_at IS NULL AND title IS NOT NULL
              AND project NOT IN ('sessions', 'archived', 'global', 'revelation', 'ttrpg', 'utety', 'grove_tonight', 'history', 'dark_matter', 'grove_architecture', 'die-namic', 'grove_general')
            GROUP BY project, LOWER(title)
            HAVING COUNT(*) > 1
        """)
        dup_groups = cur.fetchall()

    if not dup_groups:
        print("[NREM] No exact-title duplicates found.")
        return stats

    print(f"[NREM] Found {len(dup_groups)} duplicate title groups.")
    to_invalidate = []

    with pg.conn.cursor() as cur:
        for project, ltitle, cnt, oldest in dup_groups:
            # Keep the newest atom; invalidate all older ones with the same title
            cur.execute("""
                SELECT id, title, created_at FROM public.knowledge
                WHERE invalid_at IS NULL
                  AND project = %s AND LOWER(title) = %s
                ORDER BY created_at DESC
            """, (project, ltitle))
            dupes = cur.fetchall()
            # First row = newest = keep; rest = invalidate
            for dup_id, dup_title, dup_at in dupes[1:]:
                to_invalidate.append((dup_id, project, dup_title))

    if to_invalidate:
        print(f"[NREM] Will invalidate {len(to_invalidate)} older duplicates:")
        for atom_id, proj, title in to_invalidate[:10]:
            print(f"  {proj}/{atom_id[:8]} '{(title or '')[:60]}'")
        if len(to_invalidate) > 10:
            print(f"  ... and {len(to_invalidate) - 10} more")

    if not dry_run and to_invalidate:
        with pg.conn.cursor() as cur:
            for atom_id, proj, title in to_invalidate:
                cur.execute(
                    "UPDATE public.knowledge SET invalid_at = %s WHERE id = %s",
                    (now, atom_id)
                )
        pg.conn.commit()
        print(f"[NREM] Invalidated {len(to_invalidate)} duplicate atoms.")

    stats["deduped"] = len(to_invalidate)
    return stats


def flag_contradictions(pg, dry_run: bool) -> list:
    """Find atoms where the same title prefix has conflicting summaries in recent vs old."""
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=RECENCY_DAYS)
    contradictions = []

    with pg.conn.cursor() as cur:
        # Find projects with atoms spanning recent + old windows
        cur.execute("""
            SELECT id, project, title, summary, created_at
            FROM public.knowledge
            WHERE invalid_at IS NULL
              AND title IS NOT NULL
              AND project NOT IN ('sessions', 'archived', 'global', 'revelation', 'ttrpg', 'utety', 'grove_tonight', 'history', 'dark_matter', 'grove_architecture', 'die-namic', 'grove_general')
              AND created_at >= %s
            ORDER BY project, title
        """, (recent_cutoff,))
        recent_atoms = {(r[1], r[2]): r for r in cur.fetchall()}

        cur.execute("""
            SELECT id, project, title, summary, created_at
            FROM public.knowledge
            WHERE invalid_at IS NULL
              AND title IS NOT NULL
              AND project NOT IN ('sessions', 'archived', 'global', 'revelation', 'ttrpg', 'utety', 'grove_tonight', 'history', 'dark_matter', 'grove_architecture', 'die-namic', 'grove_general')
              AND created_at < %s
            ORDER BY project, title
        """, (recent_cutoff,))
        old_atoms = {(r[1], r[2]): r for r in cur.fetchall()}

    # Find exact title matches between recent and old with different summaries
    for key, recent in recent_atoms.items():
        if key in old_atoms:
            old = old_atoms[key]
            old_summary = (old[3] or "")[:200]
            new_summary = (recent[3] or "")[:200]
            if old_summary != new_summary:
                contradictions.append({
                    "project": key[0],
                    "title": key[1],
                    "old_id": old[0],
                    "new_id": recent[0],
                    "old_summary_preview": old_summary[:100],
                    "new_summary_preview": new_summary[:100],
                })

    if contradictions:
        print(f"[Contradiction] Found {len(contradictions)} title conflicts (old vs recent):")
        for c in contradictions[:5]:
            print(f"  {c['project']}/{c['title'][:50]}")
            print(f"    old: {c['old_summary_preview'][:80]}")
            print(f"    new: {c['new_summary_preview'][:80]}")
        if len(contradictions) > 5:
            print(f"  ... and {len(contradictions) - 5} more")

        if not dry_run:
            # Log to frank_ledger
            try:
                pg.ledger_append(
                    project="fleet",
                    event_type="contradiction_report",
                    content={
                        "summary": f"Sleep consolidation found {len(contradictions)} KB contradictions",
                        "count": len(contradictions),
                        "sample": contradictions[:3],
                        "run_at": now.isoformat(),
                    }
                )
                print("[Contradiction] Logged to frank_ledger for resolution.")
            except Exception as e:
                print(f"[Contradiction] frank_ledger write failed: {e}")
    else:
        print("[Contradiction] No contradictions found.")

    return contradictions


def update_decay(pg, dry_run: bool) -> int:
    """Apply daily decay to indexed_confidence in session_index (if column exists)."""
    with pg.conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='session_index' AND column_name='indexed_confidence'
        """)
        if not cur.fetchone():
            print("[Decay] indexed_confidence column not yet added — skipping.")
            return 0

        if dry_run:
            cur.execute("SELECT COUNT(*) FROM public.session_index WHERE indexed_confidence > 0.01")
            count = cur.fetchone()[0]
            print(f"[Decay] Would decay {count} session rows by 0.01.")
            return count

        cur.execute("""
            UPDATE public.session_index
            SET indexed_confidence = GREATEST(0.0, indexed_confidence - 0.01)
            WHERE indexed_confidence > 0.0
        """)
        updated = cur.rowcount
    pg.conn.commit()
    print(f"[Decay] Decayed {updated} session rows.")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Nightly KB consolidation (NREM phase)")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"[sleep_consolidation] Starting NREM consolidation — {mode}")
    print(f"[sleep_consolidation] {datetime.now(timezone.utc).isoformat()}")

    pg = PgBridge()
    pg._ensure_conn()

    nrem_stats = nrem_dedup(pg, args.dry_run)
    contradictions = flag_contradictions(pg, args.dry_run)
    decayed = update_decay(pg, args.dry_run)

    print("\n[sleep_consolidation] Done.")
    print(f"  Scanned: {nrem_stats['scanned']} atoms")
    print(f"  Deduped: {nrem_stats['deduped']} duplicates invalidated")
    print(f"  Contradictions: {len(contradictions)} flagged")
    print(f"  Decay: {decayed} session rows updated")

    if not args.dry_run and (nrem_stats["deduped"] > 0 or len(contradictions) > 0):
        pg.ledger_append(
            project="fleet",
            event_type="consolidation_run",
            content={
                "summary": f"NREM: {nrem_stats['deduped']} deduped, {len(contradictions)} contradictions",
                "deduped": nrem_stats["deduped"],
                "contradictions": len(contradictions),
                "decayed": decayed,
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
        )


if __name__ == "__main__":
    main()
