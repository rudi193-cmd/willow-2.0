"""Thin Willow KB access for stone-soup harness (read-only)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

APP_ID = "willow"


def _semantic_allowed(semantic: bool) -> bool:
    if not semantic:
        return False
    # Kart's default sandbox intentionally has no network; localhost Ollama
    # embedding cannot work there. Use keyword search instead of producing
    # repeated connection/circuit-breaker noise.
    if os.environ.get("WILLOW_IN_KART") == "1" and os.environ.get("WILLOW_KART_ALLOW_NET") != "1":
        return False
    return True


def kb_search(
    query: str,
    *,
    app_id: str = APP_ID,
    limit: int = 5,
    semantic: bool = True,
    project: str = "",
) -> list[dict[str, Any]]:
    """Hybrid KB search via Willow MCP, with PgBridge fallback."""
    use_semantic = _semantic_allowed(semantic)
    args: dict[str, Any] = {
        "app_id": app_id,
        "query": query,
        "limit": limit,
        "semantic": use_semantic,
    }
    hits: list[dict[str, Any]] = []
    try:
        from willow.fylgja._mcp import call as mcp_call

        resp = mcp_call("kb_search", args, timeout=45)
        if resp and not resp.get("error"):
            raw = resp.get("knowledge") or resp.get("results") or []
            if isinstance(raw, list):
                hits = raw
    except Exception as exc:
        print(f"[stone_soup] kb_search MCP unavailable: {exc}", file=sys.stderr)

    if not hits:
        hits = _kb_search_pg(query, limit=limit, semantic=use_semantic, project=project)
    elif project:
        filtered = [h for h in hits if h.get("project") == project]
        if filtered:
            hits = filtered
    return hits[:limit]


def _kb_search_pg(
    query: str,
    *,
    limit: int,
    semantic: bool,
    project: str,
) -> list[dict[str, Any]]:
    try:
        from core.pg_bridge import PgBridge

        pg = PgBridge()
        try:
            if semantic:
                rows = pg.knowledge_search_semantic(
                    query, limit=limit, project=project or None
                )
            else:
                rows = pg.knowledge_search(query, limit=limit, project=project or None)
        except Exception as exc:
            from core.pg_bridge import EmbedDegradedError

            if semantic and isinstance(exc, EmbedDegradedError):
                rows = pg.knowledge_search(query, limit=limit, project=project or None)
            else:
                raise
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        print(f"[stone_soup] kb_search PgBridge fallback failed: {exc}", file=sys.stderr)
        return []


def rh_dirty_atom_count() -> int | None:
    """Count non-invalid rh-dirty KB atoms (structure signal only)."""
    try:
        from core.pg_bridge import PgBridge

        pg = PgBridge()
        pg._ensure_conn()
        with pg.conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM knowledge
                WHERE project = %s AND invalid_at IS NULL
                """,
                ("rh-dirty",),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None
    except Exception as exc:
        print(f"[stone_soup] rh-dirty count failed: {exc}", file=sys.stderr)
    return None
