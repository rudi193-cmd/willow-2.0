#!/usr/bin/env python3
"""
sigmap_index.py — Index a directory into jeles_atoms via SigMap extractor.
b17: SMAP1  ΔΣ=42

Usage:
    python3 scripts/sigmap_index.py [path] [--dry-run] [--limit N]

Defaults path to CWD if not given. Uses core.pg_bridge.PgBridge for DB writes.
Embedding backfill is handled separately — this script never calls the embedder.
"""
import argparse
import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path when invoked directly
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sigmap")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index a directory into jeles_atoms via SigMap extractor.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to index (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be indexed without writing to DB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Cap at N files (useful for smoke-testing)",
    )
    parser.add_argument(
        "--agent",
        default="sigmap",
        help="Agent name written to jeles_atoms.agent (default: sigmap)",
    )
    parser.add_argument(
        "--ext",
        nargs="*",
        default=None,
        metavar="EXT",
        help="File extensions to include, e.g. --ext .py .ts (default: .py .js .ts .go .rs .rb)",
    )
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        log.error("Path is not a directory: %s", root)
        return 1

    log.info("SigMap indexer — root=%s dry_run=%s limit=%s", root, args.dry_run, args.limit)

    from willow.sigmap.indexer import index_directory

    pg = None
    if not args.dry_run:
        try:
            from core.pg_bridge import PgBridge
            pg = PgBridge()
            log.info("Connected to Postgres via PgBridge")
        except Exception as e:
            log.error("PgBridge connection failed: %s", e)
            return 1

    result = index_directory(
        root=root,
        agent=args.agent,
        pg=pg,
        dry_run=args.dry_run,
        extensions=args.ext,
        limit=args.limit,
    )

    if pg:
        try:
            pg.close()
        except Exception:
            pass

    log.info(
        "Done — indexed=%d  skipped=%d  errors=%d",
        result["indexed"], result["skipped"], result["errors"],
    )
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
