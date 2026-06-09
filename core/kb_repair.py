"""kb_repair.py — safe KB repair operations (dry-run by default)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def find_dangling_edges(conn) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT e.id, e.from_id, e.to_id, e.relation
        FROM edges e
        WHERE NOT EXISTS(
            SELECT 1 FROM knowledge k WHERE k.id = e.from_id AND k.invalid_at IS NULL
        ) OR NOT EXISTS(
            SELECT 1 FROM knowledge k WHERE k.id = e.to_id AND k.invalid_at IS NULL
        )
        """
    )
    return [
        {"id": r[0], "from_id": r[1], "to_id": r[2], "relation": r[3]}
        for r in cur.fetchall()
    ]


def repair_delete_dangling(conn, *, apply: bool = False) -> dict[str, Any]:
    dangling = find_dangling_edges(conn)
    deleted = 0
    if apply and dangling:
        cur = conn.cursor()
        for edge in dangling:
            cur.execute("DELETE FROM edges WHERE id = %s", (edge["id"],))
            deleted += 1
        conn.commit()
    return {"found": len(dangling), "deleted": deleted, "dry_run": not apply, "edges": dangling[:20]}


def find_exact_duplicate_groups(conn) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        WITH sigs AS (
          SELECT project, source_type, lower(title) AS ltitle,
                 coalesce(summary, '') AS summary,
                 coalesce(content::text, '') AS content_text,
                 count(*) AS c,
                 array_agg(id ORDER BY created_at DESC, id) AS ids
          FROM knowledge
          WHERE invalid_at IS NULL AND title IS NOT NULL
          GROUP BY project, source_type, lower(title), coalesce(summary, ''), coalesce(content::text, '')
          HAVING count(*) > 1
        )
        SELECT project, source_type, ltitle, c, ids FROM sigs ORDER BY c DESC
        """
    )
    groups = []
    for project, source_type, ltitle, count, ids in cur.fetchall():
        groups.append(
            {
                "project": project,
                "source_type": source_type,
                "title": ltitle,
                "count": int(count),
                "keeper": ids[0],
                "duplicates": ids[1:],
            }
        )
    return groups


def repair_dedup_exact(conn, pg, *, apply: bool = False, human_consent: bool = False) -> dict[str, Any]:
    groups = find_exact_duplicate_groups(conn)
    invalidated = 0
    merged_edges = 0
    now = _now()

    for group in groups:
        keeper = group["keeper"]
        dupes = group["duplicates"]
        cur = conn.cursor()

        for dup_id in dupes:
            cur.execute(
                """
                SELECT id, from_id, to_id, relation, agent, context
                FROM edges WHERE from_id = %s OR to_id = %s
                """,
                (dup_id, dup_id),
            )
            edges = cur.fetchall()
            internal_only = all(
                e[1] in dupes + [keeper] and e[2] in dupes + [keeper] for e in edges
            )

            if apply and human_consent:
                for eid, f, t, rel, agent, ctx in edges:
                    if f in dupes and t in dupes:
                        continue
                    if f in dupes:
                        nf, nt = keeper, t
                    elif t in dupes:
                        nf, nt = f, keeper
                    else:
                        continue
                    if nf == nt:
                        continue
                    stamp = f"dedup merge from {dup_id}; original_edge={eid}"
                    full_ctx = f"{ctx}; {stamp}" if ctx else stamp
                    result = pg.edge_add(nf, nt, rel, agent=agent or "hanuman", context=full_ctx, human_consent=True)
                    if result.get("status") == "added":
                        merged_edges += 1

                if not internal_only or edges:
                    cur.execute(
                        "DELETE FROM edges WHERE from_id = %s OR to_id = %s",
                        (dup_id, dup_id),
                    )

                cur.execute(
                    """
                    UPDATE knowledge
                    SET invalid_at = %s, updated_at = %s,
                        content = coalesce(content, '{}'::jsonb) || jsonb_build_object(
                          'dedup_invalidated_as_duplicate_of', %s,
                          'dedup_at', %s
                        )
                    WHERE id = %s AND invalid_at IS NULL
                    """,
                    (now, now, keeper, now.isoformat(), dup_id),
                )
                if cur.rowcount:
                    invalidated += 1

                cur.execute("SELECT content FROM knowledge WHERE id = %s", (keeper,))
                row = cur.fetchone()
                content = row[0] if row else {}
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except Exception:
                        content = {}
                dedup = content.setdefault("dedup", {})
                canon = dedup.setdefault("canonical_for", [])
                if dup_id not in canon:
                    canon.append(dup_id)
                dedup["deduped_at"] = now.isoformat()
                cur.execute(
                    "UPDATE knowledge SET content = %s::jsonb WHERE id = %s",
                    (json.dumps(content), keeper),
                )

        if apply and human_consent:
            conn.commit()

    return {
        "groups": len(groups),
        "invalidated": invalidated,
        "merged_edges": merged_edges,
        "dry_run": not apply,
        "requires_consent": apply and not human_consent,
        "sample": groups[:5],
    }


def find_duplicate_title_groups(conn) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT lower(title) AS ltitle, count(*) AS c, array_agg(id ORDER BY created_at, id) AS ids
        FROM knowledge
        WHERE invalid_at IS NULL AND title IS NOT NULL
        GROUP BY lower(title)
        HAVING count(*) > 1
        ORDER BY count(*) DESC
        """
    )
    return [
        {"title": r[0], "count": int(r[1]), "ids": r[2]}
        for r in cur.fetchall()
    ]


def _title_suffix(aid: str, title: str, index: int) -> str:
    lower = title.lower()
    if lower.startswith("dream 2026-05-25"):
        return "zero-tension canonical" if "796D22A0" == aid else "tension synthesis"
    if lower.startswith("community node") and aid.endswith("_test"):
        return "test rebuild"
    if lower.startswith("community node"):
        return "primary"
    if lower.startswith("stash"):
        return "product-lead confirmed" if aid == "754D755B" else "emerging-rule summary"
    if lower.startswith("dead reckoning"):
        return f"heading {index:02d}"
    return f"shard {index:02d}"


def repair_dedup_title(conn, *, apply: bool = False) -> dict[str, Any]:
    groups = find_duplicate_title_groups(conn)
    planned = 0
    applied = 0
    now = _now()

    for group in groups:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title FROM knowledge
            WHERE invalid_at IS NULL AND lower(title) = %s
            ORDER BY created_at, id
            """,
            (group["title"],),
        )
        rows = cur.fetchall()
        for i, (aid, title) in enumerate(rows, 1):
            suffix = _title_suffix(aid, title, i)
            new_title = f"{title} · {suffix}"
            cur.execute(
                """
                SELECT 1 FROM knowledge
                WHERE invalid_at IS NULL AND lower(title) = lower(%s) AND id <> %s
                LIMIT 1
                """,
                (new_title, aid),
            )
            if cur.fetchone():
                new_title = f"{title} · shard {i:02d} · {aid}"
            planned += 1
            if apply:
                cur.execute(
                    """
                    UPDATE knowledge
                    SET title = %s,
                        updated_at = %s,
                        content = coalesce(content, '{}'::jsonb) || jsonb_build_object(
                          'dedup_title_original', coalesce(content->>'dedup_title_original', title),
                          'dedup_title_reason', 'kb_repair dedup-title',
                          'dedup_title_at', %s
                        )
                    WHERE id = %s AND invalid_at IS NULL AND title <> %s
                    """,
                    (new_title, now, now.isoformat(), aid, new_title),
                )
                applied += cur.rowcount

    if apply:
        conn.commit()

    return {
        "groups": len(groups),
        "planned": planned,
        "applied": applied,
        "dry_run": not apply,
        "sample_groups": groups[:5],
    }


def find_low_degree_atoms(conn, max_degree: int = 1, limit: int = 50) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        WITH edge_deg AS (
          SELECT id, count(*) AS d FROM (
            SELECT from_id AS id FROM edges
            UNION ALL
            SELECT to_id AS id FROM edges
          ) u GROUP BY id
        )
        SELECT k.id, k.project, k.title, coalesce(e.d, 0) AS degree
        FROM knowledge k
        LEFT JOIN edge_deg e ON e.id = k.id
        WHERE k.invalid_at IS NULL AND coalesce(e.d, 0) <= %s
        ORDER BY e.d NULLS FIRST, k.project, k.id
        LIMIT %s
        """,
        (max_degree, limit),
    )
    return [
        {"id": r[0], "project": r[1], "title": r[2], "degree": int(r[3])}
        for r in cur.fetchall()
    ]


def repair_anchor_low_degree(
    conn,
    pg,
    *,
    apply: bool = False,
    human_consent: bool = False,
    max_degree: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    atoms = find_low_degree_atoms(conn, max_degree=max_degree, limit=limit)
    proposals: list[dict[str, Any]] = []

    cur = conn.cursor()
    anchor_title = "Low-degree orphan bridge cluster — kb_repair anchor"
    cur.execute(
        "SELECT id FROM knowledge WHERE lower(title) = lower(%s) AND invalid_at IS NULL",
        (anchor_title,),
    )
    row = cur.fetchone()
    anchor_id = row[0] if row else None

    if apply and human_consent and not anchor_id:
        anchor_id = pg.ingest_atom(
            title=anchor_title,
            summary="Anchor for low-degree atoms bridged during kb_repair anchor-low-degree pass.",
            source_type="mcp",
            source_id="kb_repair:anchor-low-degree",
            domain="kb",
            tags=["kb-repair", "orphan-bridge"],
            tier="observed",
        )

    wired = 0
    for atom in atoms:
        proposal = {
            "atom_id": atom["id"],
            "title": atom["title"],
            "project": atom["project"],
            "proposed_anchor": anchor_id or "(create on apply)",
            "relations": ["part_of", "summarizes"],
        }
        proposals.append(proposal)
        if apply and human_consent and anchor_id:
            pg.edge_add(
                atom["id"],
                anchor_id,
                "part_of",
                agent="hanuman",
                context="kb_repair anchor-low-degree",
                human_consent=True,
            )
            pg.edge_add(
                anchor_id,
                atom["id"],
                "summarizes",
                agent="hanuman",
                context="kb_repair anchor-low-degree",
                human_consent=True,
            )
            wired += 2

    return {
        "found": len(atoms),
        "proposals": proposals,
        "anchor_id": anchor_id,
        "edges_wired": wired,
        "dry_run": not apply,
        "requires_consent": apply and not human_consent,
    }
