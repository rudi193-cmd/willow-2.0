#!/usr/bin/env python3
"""kb_ship_log.py — write a maintenance voyage summary atom to the KB."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

import core.embedder as emb  # noqa: E402
import core.pg_bridge as pb  # noqa: E402
from core.kb_health import run_preflight  # noqa: E402
from core.pg_bridge import PgBridge, run_migrations  # noqa: E402

emb.embed = lambda text: None  # noqa: E731
pb.embed = emb.embed


def _human_blockers(conn) -> list[dict]:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "human_required_report_mod", ROOT / "scripts" / "human_required_report.py"
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            report = mod.build_report(conn, status="open", limit=20)
            return [
                {
                    "id": item.get("id"),
                    "kind": item.get("kind"),
                    "title": item.get("title"),
                    "priority": item.get("priority"),
                    "kb_atom": (item.get("kb_atom") or {}).get("id"),
                }
                for item in report.get("items", [])
            ]
    except Exception:
        pass
    from core.human_required import list_items

    return list_items(conn, status="open", limit=20)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write KB ship-log maintenance atom")
    parser.add_argument("--repairs", default="", help="Comma-separated repairs run this voyage")
    parser.add_argument("--notes", default="", help="Additional operator notes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    preflight = run_preflight()
    pg = PgBridge()
    run_migrations(pg.conn)
    try:
        blockers = _human_blockers(pg.conn)
        now = datetime.now(timezone.utc)
        voyage_id = now.strftime("%Y%m%d-%H%M")
        title = f"KB ship log — maintenance voyage {voyage_id}"
        summary = (
            f"KB preflight {preflight['summary']['status']}: "
            f"{preflight['graph']['atoms']} atoms, {preflight['graph']['edges']} edges, "
            f"density {preflight['graph']['density']}, "
            f"{len(blockers)} human-required blockers open."
        )
        content = {
            "voyage_id": voyage_id,
            "preflight_status": preflight["summary"]["status"],
            "graph": preflight["graph"],
            "embedding": preflight["embedding"],
            "consolidation": {
                "proposed_dedup": preflight["consolidation"].get("proposed_dedup"),
                "pass": preflight["consolidation"].get("pass"),
            },
            "repairs_run": [r.strip() for r in args.repairs.split(",") if r.strip()],
            "human_required_blockers": blockers,
            "warnings": preflight["summary"].get("warnings", []),
            "failures": preflight["summary"].get("failures", []),
            "notes": args.notes,
            "intentional_exceptions": [
                "benchmark shards retained for evaluation granularity",
                "search_noise atoms excluded from default edge proposal",
            ],
        }

        payload = {"title": title, "summary": summary, "content": content}
        if args.dry_run:
            print(json.dumps(payload, indent=2, default=str))
            return 0

        atom_id = pg.ingest_atom(
            title=title,
            summary=summary,
            source_type="mcp",
            source_id=f"kb_ship_log:{voyage_id}",
            domain="willow/kb",
            tags=["kb-ship-log", "maintenance", "preflight"],
            tier="observed",
            confidence=1.0,
        )
        if not atom_id:
            print(json.dumps({"error": pg._last_ingest_error}, indent=2), file=sys.stderr)
            return 1

        pg.edge_add(
            atom_id,
            "mirror_202606",
            "documents",
            agent="hanuman",
            context="ship log documents KB self-model state",
            human_consent=True,
        )
        pg.edge_add(
            "mirror_202606",
            atom_id,
            "references",
            agent="hanuman",
            context="KB self-model references latest ship log",
            human_consent=True,
        )

        print(json.dumps({"atom_id": atom_id, **payload}, indent=2, default=str))
        return 0
    finally:
        pg.close()


if __name__ == "__main__":
    raise SystemExit(main())
