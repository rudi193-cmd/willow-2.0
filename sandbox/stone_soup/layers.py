"""Read-only Willow layer probes for the stone-soup harness."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sandbox.stone_soup.willow_shim import kb_search


def _truncate(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _mcp(tool: str, args: dict[str, Any], timeout: int = 12) -> dict[str, Any]:
    try:
        from willow.fylgja._mcp import call

        result = call(tool, args, timeout=timeout)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        return {"error": str(exc)}


def _pg_count(table: str, where: str = "", params: tuple[Any, ...] = ()) -> int | None:
    try:
        from core.pg_bridge import PgBridge

        pg = PgBridge()
        pg._ensure_conn()
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        with pg.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row else None
    except Exception:
        return None


def _pg_rows(sql: str, params: tuple[Any, ...] = (), limit: int = 5) -> list[dict[str, Any]]:
    try:
        import psycopg2.extras
        from core.pg_bridge import PgBridge

        pg = PgBridge()
        pg._ensure_conn()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchmany(limit)]
    except Exception:
        return []


def _willow_home() -> Path:
    try:
        from willow.fylgja.willow_home import willow_home

        return willow_home(_REPO)
    except Exception:
        return Path.home() / "github" / ".willow"


def _layer_kb(limit: int) -> dict[str, Any]:
    projects = _pg_rows(
        """
        SELECT project, COUNT(*) AS atoms
        FROM knowledge
        WHERE invalid_at IS NULL
        GROUP BY project
        ORDER BY atoms DESC
        """,
        limit=limit,
    )
    return {
        "status": "present" if projects else "missing",
        "signals": {
            "live_atoms": _pg_count("knowledge", "invalid_at IS NULL"),
            "top_projects": projects,
        },
    }


def _layer_soil(limit: int) -> dict[str, Any]:
    stats = _mcp("store_stats", {}, timeout=8)
    collections = stats.get("collections")
    records = stats.get("records")
    if isinstance(stats.get("result"), dict):
        collections = stats["result"].get("collections", collections)
        records = stats["result"].get("records", records)
    if collections is None and stats and not stats.get("error"):
        collections = len(stats)
        records = sum(
            int(value.get("count", 0))
            for value in stats.values()
            if isinstance(value, dict)
        )
    return {
        "status": "present" if collections is not None else "unknown",
        "signals": {
            "collections": collections,
            "records": records,
            "sample_collections": sorted(stats)[:limit] if isinstance(stats, dict) else [],
        },
    }


def _layer_jeles(limit: int) -> dict[str, Any]:
    rows = _pg_rows(
        """
        SELECT id, title, domain, confidence
        FROM jeles_atoms
        WHERE invalid_at IS NULL
        ORDER BY created_at DESC
        """,
        limit=limit,
    )
    return {
        "status": "present" if rows else "missing",
        "signals": {
            "live_atoms": _pg_count("jeles_atoms", "invalid_at IS NULL"),
            "recent": rows,
        },
    }


def _layer_grove(limit: int) -> dict[str, Any]:
    channels: dict[str, Any] = {}
    for name in ("willow", "oakenscroll", "handoffs"):
        history = _mcp("grove_get_history", {"channel_name": name, "limit": limit}, timeout=8)
        rows = history.get("result") or history.get("messages") or []
        if not isinstance(rows, list):
            rows = []
        channels[name] = [
            {
                "id": row.get("id"),
                "sender": row.get("sender"),
                "content": _truncate(row.get("content"), 120),
            }
            for row in rows[-limit:]
            if isinstance(row, dict)
        ]
    return {"status": "present", "signals": {"channels": channels}}


def _layer_ledger(limit: int) -> dict[str, Any]:
    rows = _pg_rows(
        """
        SELECT id, project, event_type, created_at
        FROM frank_ledger
        ORDER BY created_at DESC
        """,
        limit=limit,
    )
    return {
        "status": "present" if rows else "missing",
        "signals": {
            "entries": _pg_count("frank_ledger"),
            "recent": rows,
        },
    }


def _layer_handoff(limit: int) -> dict[str, Any]:
    home = _willow_home()
    roots = [home / "handoffs" / "willow", home / "handoffs"]
    candidates: list[Path] = []
    for root in roots:
        if root.is_dir():
            candidates.extend(root.glob("session_handoff-*_willow.md"))
    candidates = sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)
    latest = []
    for path in candidates[:limit]:
        text = path.read_text(encoding="utf-8", errors="replace")
        title = next((line.strip("# ").strip() for line in text.splitlines() if line.startswith("# ")), "")
        latest.append({"file": path.name, "title": _truncate(title, 120)})
    return {
        "status": "present" if latest else "missing",
        "signals": {"handoff_root": "$WILLOW_HOME/handoffs", "latest": latest},
    }


def _layer_benchmarks(limit: int) -> dict[str, Any]:
    catalog = _REPO / "benchmarks" / "catalog.json"
    if not catalog.is_file():
        return {"status": "missing", "signals": {}}
    data = json.loads(catalog.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    selected = [
        {
            "id": entry.get("id"),
            "kind": entry.get("kind"),
            "status": entry.get("status"),
            "visibility": entry.get("visibility"),
        }
        for entry in entries
        if entry.get("id") in {"rh_apo_discernment_harness", "stone_soup_alignment", "fleet_retrieval_gold", "nest_session_corpus"}
    ]
    return {
        "status": "present",
        "signals": {"entry_count": len(entries), "relevant_entries": selected[:limit]},
    }


def _layer_kart(limit: int) -> dict[str, Any]:
    rows = _pg_rows(
        """
        SELECT status, COUNT(*) AS tasks
        FROM tasks
        GROUP BY status
        ORDER BY tasks DESC
        """,
        limit=limit,
    )
    return {"status": "present" if rows else "unknown", "signals": {"task_statuses": rows}}


def _layer_governance(limit: int) -> dict[str, Any]:
    policies = _pg_count("policy_rules", "active = true")
    human_open = _pg_count("human_required_queue", "status = 'open'")
    return {
        "status": "present" if policies is not None or human_open is not None else "unknown",
        "signals": {
            "active_policy_rules": policies,
            "open_human_required": human_open,
            "limit": limit,
        },
    }


def _layer_code(limit: int) -> dict[str, Any]:
    files = sorted(str(p.relative_to(_REPO)) for p in (_REPO / "sandbox" / "stone_soup").glob("*"))
    return {
        "status": "present",
        "signals": {
            "stone_soup_files": files[:limit],
            "tracked_reference": "sandbox/rh_harness",
        },
    }


def _layer_persona(limit: int) -> dict[str, Any]:
    paths = [
        _REPO / "willow" / "fylgja" / "skills" / "oakenscroll-boot.md",
        _REPO / "willow" / "fylgja" / "personas" / "oakenscroll.md",
    ]
    signals = []
    for path in paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            signals.append(
                {
                    "file": str(path.relative_to(_REPO)),
                    "line_count": text.count("\n") + 1,
                    "has_posole": "posole" in text.lower(),
                    "has_gaps": "ΔΣ=42" in text or "zero gaps" in text.lower(),
                }
            )
    return {"status": "present" if signals else "missing", "signals": {"files": signals[:limit]}}


def _layer_existing_synthesis(limit: int) -> dict[str, Any]:
    queries = [
        "MASTER SYNTHESIS Jeles corpus domain survey attractor topology",
        "Session handoff afternoon carry-forward atlas drive sibling overlap",
        "rh-research Permanent Storage Layout Rendereason",
        "corpus full Sean signal system architecture human context",
    ]
    anchors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in queries:
        for hit in kb_search(query, limit=limit):
            atom_id = hit.get("id")
            if not atom_id or atom_id in seen:
                continue
            seen.add(atom_id)
            anchors.append(
                {
                    "id": atom_id,
                    "title": hit.get("title"),
                    "project": hit.get("project"),
                    "category": hit.get("category"),
                    "tier": hit.get("tier"),
                    "summary": _truncate(hit.get("summary"), 180),
                }
            )
            break
    return {
        "status": "present" if anchors else "missing",
        "signals": {
            "anchor_count": len(anchors),
            "anchors": anchors[:limit],
        },
    }


PROBES = {
    "kb": _layer_kb,
    "soil": _layer_soil,
    "jeles": _layer_jeles,
    "grove": _layer_grove,
    "ledger": _layer_ledger,
    "handoff": _layer_handoff,
    "benchmarks": _layer_benchmarks,
    "kart": _layer_kart,
    "governance": _layer_governance,
    "code": _layer_code,
    "persona": _layer_persona,
    "existing_synthesis": _layer_existing_synthesis,
}


def collect_layers(layers: list[dict[str, Any]], *, limit: int) -> dict[str, Any]:
    """Collect read-only layer signals. Unknown layers are reported, not fatal."""
    collected = []
    for layer in layers:
        probe = PROBES.get(layer["id"])
        if not probe:
            collected.append({**layer, "status": "unknown", "signals": {}})
            continue
        result = probe(limit)
        collected.append({**layer, **result})
    return {"stage": "willow_layers", "layers": collected}
