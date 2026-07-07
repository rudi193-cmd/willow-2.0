#!/usr/bin/env python3
"""
fleet_data_repair.py — Data repair pass from FLEET_MEMORY_AUDIT_2026-06-07.

Subcommands (all support --dry-run):
  report            D1 — fleet intake backlog + routing preview
  promote-canonical D2 — promote canonical-tier intake (hanuman + willow)
  dedupe-locomo     D3 — supersede duplicate LoCoMo community-node titles
  tag-noise         D4 — mark benchmark/revelation atoms search_noise in content JSONB
                      (+ upstream_docs, jeles_citation, civics scrapes — corpus_class)
  mirror-frank      D6 — mirror canonical FRANK decisions into knowledge for retrieval
  backfill-tier     D5 — set NULL tier → frontier for session_promote/hook_stop

Usage:
  python3 scripts/fleet_data_repair.py report
  python3 scripts/fleet_data_repair.py promote-canonical --dry-run
  python3 scripts/fleet_data_repair.py promote-canonical
  python3 scripts/fleet_data_repair.py dedupe-locomo --dry-run
  python3 scripts/fleet_data_repair.py tag-noise
  python3 scripts/fleet_data_repair.py backfill-tier
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.intake import mark_promoted
from core.pg_bridge import PgBridge, normalize_tier
from willow.fylgja.willow_home import willow_home

CANONICAL_TIERS = frozenset({"canonical", "verified", "ratified"})
PROMOTE_AGENTS = ("hanuman", "willow")
_VERIFIED_MIN = 0.95


def _intake_root() -> Path:
    return willow_home() / "intake"


def _read_all_pending(agent: str) -> list[dict]:
    records: list[dict] = []
    agent_dir = _intake_root() / agent
    if not agent_dir.exists():
        return records
    for path in sorted(agent_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not rec.get("promoted"):
                rec["_file"] = path.name
                records.append(rec)
    return records


def _fallback_route(rec: dict) -> str:
    tier = rec.get("tier", "observed")
    confidence = float(rec.get("confidence", 0.0))
    source = rec.get("source", "")
    if tier in CANONICAL_TIERS:
        return "knowledge" if confidence >= _VERIFIED_MIN else "binder_queue"
    if tier == "contested":
        return "knowledge" if confidence >= 0.85 else "binder_queue"
    if tier == "fetched":
        return "jeles_atoms" if confidence >= 0.85 else "binder_queue"
    if tier in ("frontier", "observed"):
        if any(k in source for k in ("opus", "feedback", "reasoning")):
            return "opus" if confidence >= 0.85 else "binder_queue"
        return "knowledge" if confidence >= 0.85 else "binder_queue"
    return "binder_queue"


def cmd_report(_: argparse.Namespace) -> int:
    out: dict = {"agents": {}, "canonical_preview": []}
    for agent_dir in sorted(_intake_root().iterdir()):
        if not agent_dir.is_dir():
            continue
        agent = agent_dir.name
        pending = _read_all_pending(agent)
        canonical = [r for r in pending if r.get("tier") in CANONICAL_TIERS]
        thin = [r for r in pending if len((r.get("content") or "").strip()) < 80]
        routed: dict[str, int] = {}
        for rec in pending:
            dest = _fallback_route(rec)
            routed[dest] = routed.get(dest, 0) + 1
        out["agents"][agent] = {
            "pending": len(pending),
            "canonical_pending": len(canonical),
            "thin_pending": len(thin),
            "route_preview": routed,
        }
        for rec in canonical[:5]:
            out["canonical_preview"].append({
                "agent": agent,
                "id": rec.get("id"),
                "tier": rec.get("tier"),
                "confidence": rec.get("confidence"),
                "route": _fallback_route(rec),
                "title": (rec.get("title") or rec.get("content", "")[:60])[:80],
                "file": rec.get("_file"),
            })
    print(json.dumps(out, indent=2))
    return 0


def _promote_to_knowledge(pg: PgBridge, rec: dict, agent: str, dry_run: bool) -> str | None:
    content = rec.get("content", "")
    title = rec.get("title", "") or content[:80]
    tier = normalize_tier(rec.get("tier", "frontier"))
    confidence = float(rec.get("confidence", 1.0))
    if dry_run:
        return "DRYRUN"
    atom_id = pg.ingest_atom(
        title=title,
        summary=content,
        source_type="intake",
        source_id=rec.get("id", ""),
        category=(rec.get("extra") or {}).get("category", "general"),
        domain=rec.get("namespace") or agent,
        keywords=rec.get("keywords") or None,
        tags=rec.get("tags") or None,
        tier=tier,
        confidence=confidence,
    )
    return atom_id


def _title_key(rec: dict) -> str:
    title = (rec.get("title") or rec.get("content", "")[:80]).strip().lower()
    return title[:120]


def cmd_promote_canonical(args: argparse.Namespace) -> int:
    pg = PgBridge()
    promoted = failed = skipped = dup_skipped = 0
    results: list[dict] = []
    seen_title: dict[str, str] = {}
    for agent in PROMOTE_AGENTS:
        for rec in _read_all_pending(agent):
            if rec.get("tier") not in CANONICAL_TIERS:
                continue
            rec_id = rec.get("id", "?")
            route = _fallback_route(rec)
            if route != "knowledge":
                skipped += 1
                results.append({"agent": agent, "id": rec_id, "status": "skipped", "route": route})
                continue
            tkey = f"{agent}:{_title_key(rec)}"
            if tkey in seen_title:
                dup_skipped += 1
                if not args.dry_run:
                    mark_promoted(agent, rec_id, "skipped_duplicate")
                results.append({
                    "agent": agent, "id": rec_id, "status": "duplicate_skipped",
                    "first_id": seen_title[tkey],
                })
                continue
            atom_id = _promote_to_knowledge(pg, rec, agent, args.dry_run)
            if atom_id:
                seen_title[tkey] = rec_id
                if not args.dry_run:
                    mark_promoted(agent, rec_id, "knowledge")
                promoted += 1
                results.append({
                    "agent": agent, "id": rec_id, "status": "promoted",
                    "atom_id": atom_id, "tier": rec.get("tier"),
                })
            else:
                failed += 1
                err = getattr(pg, "_last_ingest_error", None)
                results.append({"agent": agent, "id": rec_id, "status": "failed", "error": err})
    summary = {
        "dry_run": args.dry_run,
        "promoted": promoted,
        "failed": failed,
        "skipped": skipped,
        "duplicate_skipped": dup_skipped,
        "results": results,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if failed == 0 else 1


def cmd_dedupe_locomo(args: argparse.Namespace) -> int:
    pg = PgBridge()
    pg._ensure_conn()
    pattern = "mycorrhizal — community node — willow/bench/locomo/conv-49"
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, visit_count, created_at, tier
            FROM knowledge
            WHERE invalid_at IS NULL AND lower(title) = lower(%s)
            ORDER BY visit_count DESC NULLS LAST, created_at ASC
            """,
            (pattern,),
        )
        rows = cur.fetchall()
    if len(rows) <= 1:
        print(json.dumps({"kept": rows[0][0] if rows else None, "superseded": 0}))
        return 0
    keep_id = rows[0][0]
    supersede_ids = [r[0] for r in rows[1:]]
    superseded = 0
    for atom_id in supersede_ids:
        if args.dry_run:
            superseded += 1
            continue
        res = pg.promote_knowledge_tier(
            atom_id, "superseded", agent="hanuman",
            reason="fleet_data_repair dedupe-locomo conv-49 cluster",
        )
        if res.get("promoted"):
            superseded += 1
    print(json.dumps({
        "dry_run": args.dry_run,
        "pattern": pattern,
        "total": len(rows),
        "kept": keep_id,
        "superseded": superseded,
    }, indent=2))
    return 0


def cmd_tag_noise(args: argparse.Namespace) -> int:
    """Tag external doc-scrape / benchmark atoms so default retrieval excludes them."""
    pg = PgBridge()
    pg._ensure_conn()
    noise_patch = json.dumps({"search_noise": True, "corpus_class": "external_reference"})
    where = """
        invalid_at IS NULL
        AND NOT COALESCE((content->>'search_noise')::boolean, false)
        AND (
            source_type IN (
                'benchmark', 'revelation', 'mycorrhizal', 'community_detection',
                'upstream_docs', 'jeles_citation'
            )
            OR title ILIKE 'civics source:%%'
        )
    """
    with pg.conn.cursor() as cur:
        if args.dry_run:
            cur.execute(
                f"""
                SELECT source_type, COUNT(*)
                FROM knowledge
                WHERE {where}
                GROUP BY source_type
                ORDER BY 2 DESC
                """
            )
            counts = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(f"SELECT COUNT(*) FROM knowledge WHERE {where}")
            total = cur.fetchone()[0]
            print(json.dumps({"dry_run": True, "would_tag_total": total, "by_source": counts}))
            return 0
        cur.execute(
            f"""
            UPDATE knowledge
            SET content = content || %s::jsonb,
                updated_at = now()
            WHERE {where}
            """,
            (noise_patch,),
        )
        updated = cur.rowcount
        pg.conn.commit()
    print(json.dumps({"dry_run": False, "tagged": updated}))
    return 0


# FRANK ledger decisions that must be kb_search-visible (flag-kb-semantic-retrieval-noise).
_FRANK_MIRROR_IDS = (
    "66526147-20df-4bf1-b6a2-e35188f77a0f",
    "8d0bf0ea-2aa5-4720-a072-7564a45e5a9a",
)


def _frank_summary(content: dict) -> str:
    body = (content.get("content") or content.get("summary") or "").strip()
    if body:
        return body[:1200]
    parts = [content.get("title") or "", content.get("note") or ""]
    return " ".join(p for p in parts if p).strip()[:1200]


def _embed_atom_if_missing(pg: PgBridge, atom_id: str) -> bool:
    """Backfill embedding for a single atom (mirror-frank hot path)."""
    from core.pg_bridge import embed

    with pg.conn.cursor() as cur:
        cur.execute(
            """
            SELECT title, summary, content, embedding IS NOT NULL
            FROM knowledge WHERE id = %s AND invalid_at IS NULL
            """,
            (atom_id,),
        )
        row = cur.fetchone()
    if not row:
        return False
    title, summary, content, has_emb = row
    if has_emb:
        return True
    record = {"title": title, "summary": summary, "content": content or {}}
    vec = embed(pg._knowledge_embedding_text(record))
    if vec is None:
        return False
    with pg.conn.cursor() as cur:
        cur.execute(
            "UPDATE knowledge SET embedding = %s::vector, updated_at = now() WHERE id = %s",
            (str(vec), atom_id),
        )
    pg.conn.commit()
    return True


def cmd_mirror_frank(args: argparse.Namespace) -> int:
    """Upsert canonical KB atoms for key FRANK decisions (retrieval mirror)."""
    pg = PgBridge()
    pg._ensure_conn()
    ledger_ids = list(args.ledger_id) if args.ledger_id else list(_FRANK_MIRROR_IDS)
    results: list[dict] = []
    with pg.conn.cursor() as cur:
        for ledger_id in ledger_ids:
            cur.execute(
                """
                SELECT id, event_type, content
                FROM frank_ledger
                WHERE id::text = %s OR id::text LIKE %s
                LIMIT 1
                """,
                (ledger_id, f"{ledger_id}%"),
            )
            row = cur.fetchone()
            if not row:
                results.append({"ledger_id": ledger_id, "status": "missing"})
                continue
            full_id, event_type, content = row[0], row[1], row[2] or {}
            if not isinstance(content, dict):
                content = {}
            title = (content.get("title") or f"FRANK {event_type}").strip()
            summary = _frank_summary(content)
            if len(summary.split()) < 8:
                summary = (
                    f"{summary} FRANK ledger decision {full_id} "
                    f"({event_type}) mirrored for kb_search governance recall."
                ).strip()
            cur.execute(
                """
                SELECT id FROM knowledge
                WHERE invalid_at IS NULL
                  AND content->>'frank_ledger_id' = %s
                LIMIT 1
                """,
                (str(full_id),),
            )
            existing = cur.fetchone()
            if existing:
                results.append({
                    "ledger_id": str(full_id),
                    "status": "exists",
                    "atom_id": existing[0],
                })
                continue
            if args.dry_run:
                results.append({"ledger_id": str(full_id), "status": "would_create", "title": title})
                continue
            atom_id = pg.ingest_atom(
                title=title,
                summary=summary,
                source_type="frank_decision",
                source_id=str(full_id),
                category="governance",
                domain="global",
                tier="canonical",
                confidence=1.0,
                tags=["frank_mirror", "governance"],
            )
            if not atom_id:
                results.append({
                    "ledger_id": str(full_id),
                    "status": "failed",
                    "error": pg._last_ingest_error,
                })
                continue
            cur.execute(
                """
                UPDATE knowledge
                SET content = content || %s::jsonb, updated_at = now()
                WHERE id = %s
                """,
                (
                    json.dumps({"frank_ledger_id": str(full_id), "event_type": event_type}),
                    atom_id,
                ),
            )
            pg.conn.commit()
            embedded = _embed_atom_if_missing(pg, atom_id)
            results.append({
                "ledger_id": str(full_id),
                "status": "created",
                "atom_id": atom_id,
                "embedded": embedded,
            })
    print(json.dumps({"dry_run": args.dry_run, "results": results}, indent=2))
    return 0


def cmd_backfill_tier(args: argparse.Namespace) -> int:
    pg = PgBridge()
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        if args.dry_run:
            cur.execute(
                """
                SELECT source_type, COUNT(*)
                FROM knowledge
                WHERE invalid_at IS NULL AND tier IS NULL
                GROUP BY source_type ORDER BY 2 DESC
                """
            )
            print(json.dumps({"dry_run": True, "null_tier_by_source": dict(cur.fetchall())}))
            return 0
        cur.execute(
            """
            UPDATE knowledge
            SET tier = 'frontier', updated_at = now()
            WHERE invalid_at IS NULL
              AND tier IS NULL
              AND source_type IN ('session_promote', 'hook_stop')
            """
        )
        updated = cur.rowcount
        pg.conn.commit()
    print(json.dumps({"dry_run": False, "tier_set_frontier": updated}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fleet memory data repair")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("report")
    p = sub.add_parser("promote-canonical")
    p.set_defaults(dry_run=False)
    p.add_argument("--dry-run", action="store_true")
    for name in ("dedupe-locomo", "tag-noise", "backfill-tier"):
        sp = sub.add_parser(name)
        sp.add_argument("--dry-run", action="store_true")
    sp = sub.add_parser("mirror-frank")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument(
        "--ledger-id",
        action="append",
        default=[],
        help="FRANK ledger UUID (prefix ok); default: syscall + hub doctrine",
    )

    args = parser.parse_args()
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "promote-canonical":
        return cmd_promote_canonical(args)
    if args.cmd == "dedupe-locomo":
        return cmd_dedupe_locomo(args)
    if args.cmd == "tag-noise":
        return cmd_tag_noise(args)
    if args.cmd == "mirror-frank":
        return cmd_mirror_frank(args)
    if args.cmd == "backfill-tier":
        return cmd_backfill_tier(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
