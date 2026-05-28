#!/usr/bin/env python3
"""
CLI mirror of MCP willow_knowledge_ingest — same memory_gate + PgBridge.ingest_atom path.
b17: KBCLI1  ΔΣ=42

Usage (from willow-2.0 repo root):
  python3 scripts/kb_ingest_cli.py --domain hanuman --title "..." --summary "..."
  python3 scripts/kb_ingest_cli.py ... --force   # bypass REDUNDANT/CONTRADICTION block
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="KB ingest via memory_gate + Postgres")
    ap.add_argument("--title", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--domain", required=True, help="Agent namespace (e.g. heimdallr, hanuman)")
    ap.add_argument("--source-type", default="cli_kb_ingest")
    ap.add_argument("--source-id", default="")
    ap.add_argument("--category", default="fleet_process")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _core = ROOT / "core"
    if str(_core) not in sys.path:
        sys.path.insert(1, str(_core))

    from core.pg_bridge import PgBridge
    from sap.core.memory_gate import check_candidate
    from willow_store import WillowStore

    store_root = os.environ.get("WILLOW_STORE_ROOT", str(ROOT / "store"))
    store = WillowStore(store_root)
    pg = PgBridge()

    title = args.title.strip()
    summary = args.summary.strip()
    domain = args.domain.strip() or None
    force = args.force

    if not force:
        try:
            gate = check_candidate(
                title=title,
                summary=summary,
                domain=domain,
                store=store,
                pg=pg,
                collection=f"{domain}/atoms" if domain else None,
            )
            hard = {"REDUNDANT", "CONTRADICTION"} & set(gate.get("flags", []))
            if hard:
                print(json.dumps({"blocked": True, **gate}, indent=2))
                print("Re-run with --force to write anyway.", file=sys.stderr)
                return 2
        except Exception as e:
            print(f"[memory_gate] WARNING: {e}", file=sys.stderr)

    atom_id = pg.ingest_atom(
        title=title,
        summary=summary,
        source_type=args.source_type,
        source_id=args.source_id,
        category=args.category,
        domain=domain,
    )
    if not atom_id:
        err = getattr(pg, "_last_ingest_error", None)
        print(f"ingest failed: {err}", file=sys.stderr)
        return 1
    print(atom_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
