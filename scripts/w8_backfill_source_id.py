#!/usr/bin/env python3
"""Backfill empty content.source_id on W8-unsupported canonical atoms.

Dry-run by default. Use --apply to write via PgBridge.knowledge_put.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

from core.pg_bridge import PgBridge
from sandbox.stone_soup.run import _PROVENANCE_RELATIONS, canonical_reconstruction_census

PR_RE = re.compile(r"#?(\d+)")
PATH_RE = re.compile(r"^([\w./-]+\.(?:py|md|json|sh))\b")
AUTHOR_YEAR_RE = re.compile(r"^([A-Z][A-Za-z&\s.]+?)\s+(\d{4})\b")
TITLE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _unsupported_ids(pg: PgBridge) -> list[str]:
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM knowledge
            WHERE invalid_at IS NULL AND tier = 'canonical'
              AND COALESCE(source_type, '') <> 'benchmark'
            """
        )
        canonical = {str(r[0]) for r in cur.fetchall()}

        ledger_ids: set[str] = set()
        cur.execute("SELECT content FROM frank_ledger")
        for (content,) in cur.fetchall():
            payload = content if isinstance(content, dict) else json.loads(content)
            written = payload.get("atoms_written")
            if isinstance(written, list):
                ledger_ids.update(str(x) for x in written)

        source_id_ids: set[str] = set()
        cur.execute(
            """
            SELECT id, content FROM knowledge
            WHERE invalid_at IS NULL AND tier = 'canonical'
              AND COALESCE(source_type, '') <> 'benchmark'
            """
        )
        for aid, content in cur.fetchall():
            payload = content if isinstance(content, dict) else (json.loads(content) if content else {})
            if isinstance(payload, dict) and payload.get("source_id"):
                source_id_ids.add(str(aid))

        edge_ids: set[str] = set()
        cur.execute(
            "SELECT from_id, to_id FROM edges "
            "WHERE invalid_at IS NULL AND relation = ANY(%s)",
            (list(_PROVENANCE_RELATIONS),),
        )
        for from_id, to_id in cur.fetchall():
            edge_ids.add(str(from_id))
            edge_ids.add(str(to_id))

    supported = (canonical & ledger_ids) | (canonical & source_id_ids) | (canonical & edge_ids)
    return sorted(canonical - supported)


def _slug(text: str, limit: int = 48) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:limit].strip("-")


def infer_source_id(row: tuple) -> tuple[str | None, str]:
    aid, title, summary, content, source_type, category, created_at = row
    payload = content if isinstance(content, dict) else (json.loads(content) if content else {})
    if not isinstance(payload, dict):
        payload = {}
    if payload.get("source_id"):
        return None, "already"

    signals = payload.get("signals") or {}
    if isinstance(signals, dict) and signals.get("doc_path"):
        return str(signals["doc_path"]), "signals.doc_path"

    pr = payload.get("pr")
    if pr:
        match = PR_RE.search(str(pr))
        if match:
            return f"willow-2.0#{match.group(1)}", "content.pr"

    match = PATH_RE.match(title or "")
    if match:
        return match.group(1), "title.path"

    if source_type == "literature" or category == "depth-atom":
        match = AUTHOR_YEAR_RE.match(title or "")
        if match:
            author = re.sub(r"\s+", "-", match.group(1).strip().split()[0])
            return f"{author}-{match.group(2)}", "literature.author_year"
        keywords = payload.get("keywords") or []
        year = next((str(k) for k in keywords if re.fullmatch(r"\d{4}", str(k))), None)
        if not year:
            years = TITLE_YEAR_RE.findall(title or "") or TITLE_YEAR_RE.findall(summary or "")
            year = years[0] if years else None
        if year:
            words = re.findall(r"[A-Za-z]+", title or "")
            head = words[0] if words else "literature"
            return f"{head}-{year}", "literature.fallback"
        if category == "depth-atom":
            return f"depth-atom:{_slug(title or aid)}", "depth-atom.slug"

    if payload.get("source_context"):
        day = str(created_at)[:10] if created_at else "unknown"
        return f"conversation:willow:{day}", "source_context"

    if category == "handoff" or "handoff" in (title or "").lower():
        day = str(created_at)[:10] if created_at else "unknown"
        return f"handoff:{day}", "handoff.date"

    if "PR #" in (title or "") or "PR #" in (summary or ""):
        match = PR_RE.search(title or "") or PR_RE.search(summary or "")
        if match:
            return f"willow-2.0#{match.group(1)}", "title.pr"

    day = str(created_at)[:10] if created_at else "unknown"
    if source_type == "mcp":
        return f"mcp:willow:{day}:{_slug(title or aid)}", "mcp.session_slug"
    if source_type == "session":
        return f"session:willow:{day}", "session.date"
    if source_type in ("design", "conversation", "discovered_pattern"):
        return f"{source_type}:willow:{day}", f"{source_type}.date"

    return None, "unresolved"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write inferred source_id values")
    parser.add_argument("--json", action="store_true", help="Emit full plan as JSON")
    args = parser.parse_args()

    before = canonical_reconstruction_census()
    pg = PgBridge()
    plans: list[dict] = []

    with pg.conn.cursor() as cur:
        for aid in _unsupported_ids(pg):
            cur.execute(
                """
                SELECT id, title, summary, content, source_type, category, created_at
                FROM knowledge WHERE id = %s
                """,
                (aid,),
            )
            row = cur.fetchone()
            if not row:
                continue
            proposed, reason = infer_source_id(row)
            plans.append(
                {
                    "id": str(row[0]),
                    "title": row[1],
                    "proposed_source_id": proposed,
                    "reason": reason,
                }
            )

    resolved = [p for p in plans if p["proposed_source_id"]]
    unresolved = [p for p in plans if not p["proposed_source_id"]]

    if args.json:
        print(json.dumps({"before": before, "plans": plans}, indent=2))
        return 0

    print(f"before: unsupported={before['unsupported']} cost={before['unsupported']/max(before['canonical_total'],1):.3f}")
    print(f"plan: {len(resolved)} resolvable, {len(unresolved)} unresolved")
    print("by_reason:", dict(Counter(p["reason"] for p in resolved)))
    for item in unresolved:
        print(f"UNRESOLVED {item['id']}: {item['title']}")

    if not args.apply:
        for item in resolved[:20]:
            print(f"  {item['id']} -> {item['proposed_source_id']} ({item['reason']})")
        if len(resolved) > 20:
            print(f"  ... +{len(resolved) - 20} more")
        return 0

    applied = 0
    for item in resolved:
        atom_id = item["id"]
        with pg.conn.cursor() as cur:
            cur.execute("SELECT * FROM knowledge WHERE id = %s AND invalid_at IS NULL", (atom_id,))
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            if not row:
                continue
            record = dict(zip(cols, row))
        content = record.get("content") or {}
        if isinstance(content, str):
            content = json.loads(content)
        content = dict(content)
        content["source_id"] = item["proposed_source_id"]
        content["provenance_backfill"] = {
            "reason": item["reason"],
            "script": "scripts/w8_backfill_source_id.py",
        }
        record["content"] = content
        pg.knowledge_put(record)
        applied += 1

    after = canonical_reconstruction_census()
    print(f"applied: {applied}")
    print(
        f"after: unsupported={after['unsupported']} "
        f"supported={after['supported']} "
        f"cost={after['unsupported']/max(after['canonical_total'],1):.3f}"
    )
    return 0 if not unresolved else 1


if __name__ == "__main__":
    sys.exit(main())
