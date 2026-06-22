"""python -m sandbox.nest_seed — portable Nest seed CLI.

Examples:
    # Ingest a dump into a Nest DB
    python -m sandbox.nest_seed --folder ~/life-dump --owner "Sean" -v

    # Ingest, then refine semantic fragments with self-learning centroids
    python -m sandbox.nest_seed --folder ~/life-dump --owner "Sean" --learn -v

    # Run the centroid pass on an existing DB (no re-ingest)
    python -m sandbox.nest_seed --db ~/Desktop/Nest/seed.db --learn-only -v

    # Surface candidate new categories by clustering documents
    python -m sandbox.nest_seed --db ~/Desktop/Nest/seed.db --discover 6
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sandbox.nest_seed.ingest import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed a portable Nest SQLite DB from a folder of personal files."
    )
    parser.add_argument("--folder",
                        help="Path to the dump folder to ingest "
                             "(omit with --learn-only / --discover)")
    parser.add_argument("--db", default="~/Desktop/Nest/seed.db",
                        help="Path to Nest SQLite DB (default: ~/Desktop/Nest/seed.db)")
    parser.add_argument("--owner", default="",
                        help="Your name — stored in nest_meta")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print fragments only, do not write DB")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-file progress")
    # Self-learning centroid pass
    parser.add_argument("--learn", action="store_true",
                        help="After ingest, refine semantic fragments via centroids")
    parser.add_argument("--learn-only", action="store_true",
                        help="Skip ingest; run the centroid pass on --db")
    parser.add_argument("--sim-threshold", type=float, default=0.62,
                        help="Min cosine similarity to reassign a fragment")
    parser.add_argument("--margin", type=float, default=0.08,
                        help="Min lead over the runner-up centroid to reassign")
    parser.add_argument("--discover", type=int, metavar="K", default=0,
                        help="Cluster documents into K groups (report only)")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    do_ingest = not args.learn_only and args.discover == 0 or args.folder is not None
    # --learn-only / --discover can run without a folder; plain ingest needs one.
    if args.learn_only or (args.discover and not args.folder):
        do_ingest = False

    if do_ingest:
        if not args.folder:
            sys.exit("ERROR: --folder is required for ingest "
                     "(or use --learn-only / --discover)")
        folder = Path(args.folder).expanduser().resolve()
        if not folder.is_dir():
            sys.exit(f"ERROR: {folder} is not a directory")
        if not args.dry_run:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        owner = args.owner or folder.parent.name

        print(f"[nest-seed] folder : {folder}", file=sys.stderr)
        if not args.dry_run:
            print(f"[nest-seed] db     : {db_path}", file=sys.stderr)
        print(f"[nest-seed] owner  : {owner}", file=sys.stderr)
        print(f"[nest-seed] mode   : {'dry-run' if args.dry_run else 'live'}", file=sys.stderr)
        print("", file=sys.stderr)

        counts = run(folder, db_path, owner=owner,
                     dry_run=args.dry_run, verbose=args.verbose)

        print("", file=sys.stderr)
        for k in ("files", "extracted", "failed", "skipped", "fragments"):
            print(f"[nest-seed] {k:9}: {counts[k]}", file=sys.stderr)
        if "db_stats" in counts:
            print(f"[nest-seed] db stats : {json.dumps(counts['db_stats'])}", file=sys.stderr)

    # --- centroid learning pass ---
    if args.learn or args.learn_only:
        if args.dry_run:
            sys.exit("ERROR: --learn requires a written DB (not --dry-run)")
        from sandbox.nest_seed import centroids as _cent
        import sqlite3
        if not db_path.exists():
            sys.exit(f"ERROR: {db_path} does not exist — ingest first")
        conn = sqlite3.connect(str(db_path))
        print("", file=sys.stderr)
        print("[nest-seed] centroid learning pass …", file=sys.stderr)
        result = _cent.learn(conn, sim_threshold=args.sim_threshold,
                             margin=args.margin, verbose=args.verbose)
        conn.close()
        print(f"[nest-seed] learn    : {json.dumps(result)}", file=sys.stderr)

    # --- clustering discovery ---
    if args.discover:
        from sandbox.nest_seed import centroids as _cent
        import sqlite3
        if not db_path.exists():
            sys.exit(f"ERROR: {db_path} does not exist")
        conn = sqlite3.connect(str(db_path))
        print("", file=sys.stderr)
        print(f"[nest-seed] discovery: clustering into {args.discover} groups …",
              file=sys.stderr)
        result = _cent.discover(conn, n_clusters=args.discover)
        conn.close()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
