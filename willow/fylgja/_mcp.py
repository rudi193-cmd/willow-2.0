"""
_mcp.py — Willow MCP direct client.
b17: FYGJ1  ΔΣ=42

Dispatches hook→MCP calls directly to Python implementations.
No subprocess. No stale binary. No init handshake. No auth gap.

Tool groups:
  store_*                → core.store_port.StorePort (WillowStoreAdapter)
  grove_*                → core.grove_client
  soil_*                 → core.store_port.StorePort (WillowStoreAdapter)
  kb_search              → core.pg_bridge.PgBridge (lane-scope + taint parity with sap_mcp.kb_search)
  everything else        → subprocess fallback (willow-mcp binary — currently
                            unreachable; see issue #628/#629, not yet migrated)
"""
import json
import os
import subprocess
import threading
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent  # willow-2.0/
_WILLOW_MCP = Path(os.environ.get(
    "WILLOW_MCP_BIN",
    str(Path.home() / ".local" / "bin" / "willow-mcp")
))

# ---------------------------------------------------------------------------
# Direct store dispatch
# ---------------------------------------------------------------------------

_store = None


def _get_store():
    global _store
    if _store is None:
        import sys
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from core.store_port import get_store_port
        _store = get_store_port()
    return _store


# ---------------------------------------------------------------------------
# Direct KB dispatch — mirrors sap/sap_mcp.py's kb_search (lane-scope security +
# taint tagging + relevance-gated promotion), called synchronously and without
# importing sap_mcp's whole FastMCP module graph. Fixes #628/#629: kb_search
# used to fall through to the subprocess fallback below, which shells to a
# willow-mcp binary that doesn't exist — every caller silently degraded (or,
# for rh_harness with no fallback of its own, silently returned nothing).
# ---------------------------------------------------------------------------

_pg = None
_pg_failed = False


def _get_pg():
    global _pg, _pg_failed
    if _pg is None and not _pg_failed:
        import sys
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        try:
            from core.pg_bridge import PgBridge
            _pg = PgBridge()
        except Exception:
            _pg_failed = True
    return _pg


def _dispatch_kb(tool_name: str, arguments: dict):
    pg = _get_pg()
    if pg is None:
        return {"error": "pg_unavailable", "tool": tool_name}

    if tool_name != "kb_search":
        return {"error": f"unknown kb tool: {tool_name}"}

    from core.canonical_lanes import atoms_taint, resolve_lane_read_scope
    from core.promotion_policy import select_promotion_ids

    query = arguments.get("query", "")
    limit = arguments.get("limit", 20)
    semantic = arguments.get("semantic", True)
    include_embedding = arguments.get("include_embedding", False)
    fields = arguments.get("fields")
    tier_filter = arguments.get("tier") or None
    expand_neighbors = arguments.get("expand_neighbors", True)
    continuity = arguments.get("continuity", False)
    scope = arguments.get("scope", "")
    project = arguments.get("project", "")
    app_id = arguments.get("app_id", "")

    lane_scope = resolve_lane_read_scope(app_id, scope=scope, project=project or None)
    explicit_project = (project or "").strip() or None
    # Sidecar veto (ADR-20260702 step 2): sensitive jeles/opus rows are excluded
    # unless the caller asked for god-view — mirrors sap_mcp.kb_search exactly.
    god_view = (scope or "").strip() == "*" and lane_scope.projects is None and not lane_scope.exclude

    if semantic:
        try:
            knowledge = pg.knowledge_search_semantic(
                query, limit=limit, include_embedding=include_embedding,
                fields=fields, tier=tier_filter, continuity=continuity,
                project=explicit_project, lane_scope=lane_scope,
            )
            jeles = pg.search_jeles_semantic(query, limit=limit // 2, include_sensitive=god_view)
            opus = pg.search_opus_semantic(query, limit=limit // 2, include_sensitive=god_view)
            mode = "hybrid" if any("_rrf_score" in row for row in knowledge[:3]) else "semantic"
        except Exception:
            knowledge = pg.knowledge_search(
                query, limit=limit, include_embedding=include_embedding,
                fields=fields, tier=tier_filter,
                project=explicit_project, lane_scope=lane_scope,
            )
            jeles = pg.jeles_keyword_search(query, limit=limit // 2, include_sensitive=god_view)
            opus = pg.search_opus(query, limit=limit // 2, include_sensitive=god_view)
            mode = "degraded"
    else:
        knowledge = pg.knowledge_search(
            query, limit=limit, include_embedding=include_embedding,
            fields=fields, tier=tier_filter,
            project=explicit_project, lane_scope=lane_scope,
        )
        jeles = pg.jeles_keyword_search(query, limit=limit // 2, include_sensitive=god_view)
        opus = pg.search_opus(query, limit=limit // 2, include_sensitive=god_view)
        mode = "keyword"

    neighbors: list = []
    if expand_neighbors and knowledge:
        seed_ids = [a["id"] for a in knowledge[:10] if a.get("id")]
        try:
            neighbors = pg.knowledge_expand_neighbors(seed_ids, limit=max(5, limit // 3), lane_scope=lane_scope)
        except Exception:
            neighbors = []
        seen = {a["id"] for a in knowledge if a.get("id")}
        knowledge = knowledge + [n for n in neighbors if n.get("id") not in seen]

    for atom_id in select_promotion_ids(knowledge):
        try:
            pg.promote(atom_id)
        except Exception:
            pass
    for row in jeles:
        row["_table"] = "jeles_atoms"
    for row in opus:
        row["_table"] = "opus_atoms"

    taint = atoms_taint(knowledge + jeles + opus)
    return {
        "knowledge": knowledge,
        "jeles_atoms": jeles,
        "opus_atoms": opus,
        "neighbors": neighbors,
        "total": len(knowledge) + len(jeles) + len(opus),
        "taint": taint,
        "mode": mode,
        "lane_scope": {
            "projects": list(lane_scope.projects) if lane_scope.projects is not None else None,
            "exclude": list(lane_scope.exclude),
        },
    }


def _dispatch_store(tool_name: str, arguments: dict):
    store = _get_store()
    col = arguments.get("collection", "")

    if tool_name == "store_put":
        record = arguments.get("record", {})
        record_id = arguments.get("record_id") or record.get("id")
        result = store.put(col, record, record_id=record_id)
        if isinstance(result, tuple):
            rid, action = result[0], result[1]
            return {"id": rid, "action": action}
        return {"id": record_id or "", "action": "written"}

    if tool_name == "store_get":
        record_id = arguments.get("record_id") or arguments.get("id", "")
        result = store.get(col, record_id)
        return result if result is not None else {"error": "not_found"}

    if tool_name == "store_list":
        return store.all(col) or []

    if tool_name == "store_search":
        query = arguments.get("query", "")
        after = arguments.get("after")
        return store.search(col, query, after=after) or []

    if tool_name == "store_search_all":
        return store.search_all(arguments.get("query", "")) or []

    if tool_name == "store_delete":
        record_id = arguments.get("record_id", "")
        return store.delete(col, record_id)

    if tool_name == "store_update":
        record_id = arguments.get("record_id", "")
        record = arguments.get("record", {})
        result = store.update(col, record_id, record)
        if isinstance(result, tuple):
            return {"id": result[0], "action": result[1]}
        return {"id": record_id, "action": "updated"}

    if tool_name == "store_add_edge":
        return store.add_edge(
            arguments.get("from_collection", ""),
            arguments.get("from_id", ""),
            arguments.get("to_collection", ""),
            arguments.get("to_id", ""),
            arguments.get("label", ""),
        )

    if tool_name == "store_edges_for":
        return store.edges_for(col, arguments.get("record_id", "")) or []

    if tool_name == "store_stats":
        return store.stats() or {}

    if tool_name == "store_audit":
        return store.audit() or {}

    return {"error": f"unknown store tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Direct soil dispatch — same StorePort backend as the MCP server's soil_ tools
# (sap/sap_mcp.py: soil_ → store → WillowStore). Mirrors that module's
# semantics so a hook write lands exactly where soil_get/soil_list will read it,
# without the subprocess willow-mcp spawn + init handshake the fallback requires.
# ---------------------------------------------------------------------------

def _qualifies_as_flag(record: dict, deviation: float) -> bool:
    # Mirror of sap.sap_mcp._qualifies_as_flag — keep in sync.
    return (
        record.get("type") in ("failure-log",) or
        record.get("domain") == "governance" or
        deviation > 0.6 or
        (record.get("type") == "gap" and record.get("severity") in ("high", "critical"))
    )


def _dispatch_soil(tool_name: str, arguments: dict):
    store = _get_store()
    col = arguments.get("collection", "")

    if tool_name == "soil_put":
        record = arguments.get("record", {})
        record_id = arguments.get("record_id") or record.get("id")
        deviation = arguments.get("deviation", 0.0) or 0.0
        result = store.put(col, record, record_id=record_id or None, deviation=deviation)
        # StorePort.put returns (id, action) or (id, action, proposals)
        if isinstance(result, tuple):
            rid = result[0]
            action = result[1] if len(result) > 1 else "written"
            proposals = result[2] if len(result) > 2 else None
        else:
            rid, action, proposals = (record_id or ""), "written", None
        out: dict = {"id": rid, "action": action}
        if proposals:
            out["proposals"] = [p.to_dict() for p in proposals]
        # Auto-flag qualifying records into {namespace}/flags — mirrors soil_put
        if not col.endswith("/flags") and _qualifies_as_flag(record, deviation):
            from datetime import datetime, timezone
            namespace = col.split("/")[0]
            store.put(f"{namespace}/flags", {
                "atom_id": rid,
                "collection": col,
                "deviation": deviation,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        return out

    if tool_name == "soil_get":
        record_id = arguments.get("record_id") or arguments.get("id", "")
        result = store.get(col, record_id)
        return result if result is not None else {"error": "not_found"}

    if tool_name == "soil_list":
        return store.all(col) or []

    if tool_name == "soil_search":
        query = arguments.get("query", "")
        after = arguments.get("after") or None
        if arguments.get("semantic"):
            return store.search_semantic(col, query) or []
        return store.search(col, query, after=after) or []

    if tool_name == "soil_search_all":
        return store.search_all(arguments.get("query", "")) or []

    if tool_name == "soil_delete":
        return store.delete(col, arguments.get("record_id", ""))

    if tool_name == "soil_update":
        record_id = arguments.get("record_id", "")
        record = arguments.get("record", {})
        result = store.update(col, record_id, record)
        if isinstance(result, tuple):
            return {"id": result[0], "action": result[1]}
        return {"id": record_id, "action": "updated"}

    if tool_name == "soil_edges_for":
        return store.edges_for(arguments.get("record_id", "")) or []

    if tool_name == "soil_stats":
        return store.stats() or {}

    return {"error": f"unknown soil tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Direct grove dispatch — raw psycopg2 to grove.* schema
# ---------------------------------------------------------------------------

def _grove_connect():
    import psycopg2
    db = os.environ.get("WILLOW_PG_DB", "willow_20")
    user = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
    conn = psycopg2.connect(dbname=db, user=user)
    conn.autocommit = True
    return conn


def _dispatch_grove(tool_name: str, arguments: dict):
    try:
        conn = _grove_connect()
        cur = conn.cursor()

        if tool_name == "grove_send_message":
            channel = arguments.get("channel_name", arguments.get("channel", ""))
            cur.execute("SELECT id FROM grove.channels WHERE name=%s LIMIT 1", (channel,))
            row = cur.fetchone()
            if not row:
                return {"error": f"channel not found: {channel}"}
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content) VALUES (%s, %s, %s) RETURNING id",
                (row[0], arguments.get("sender", ""), arguments.get("content", "")),
            )
            msg_id = cur.fetchone()[0]
            conn.close()
            return {"id": msg_id, "ok": True}

        if tool_name == "grove_reply":
            cur.execute("SELECT channel_id FROM grove.messages WHERE id=%s LIMIT 1",
                        (arguments.get("parent_id", 0),))
            row = cur.fetchone()
            if not row:
                return {"error": "parent message not found"}
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content, parent_id) VALUES (%s, %s, %s, %s) RETURNING id",
                (row[0], arguments.get("sender", ""), arguments.get("content", ""), arguments.get("parent_id")),
            )
            msg_id = cur.fetchone()[0]
            conn.close()
            return {"id": msg_id, "ok": True}

        if tool_name == "grove_get_history":
            channel = arguments.get("channel_name", arguments.get("channel", ""))
            cur.execute("SELECT id FROM grove.channels WHERE name=%s LIMIT 1", (channel,))
            row = cur.fetchone()
            if not row:
                return {"result": []}
            since_id = arguments.get("since_id", 0)
            limit = min(arguments.get("limit", 50), 200)
            cur.execute(
                "SELECT id, sender, content, created_at FROM grove.messages "
                "WHERE channel_id=%s AND id>%s AND is_deleted=0 ORDER BY id ASC LIMIT %s",
                (row[0], since_id, limit),
            )
            rows = cur.fetchall()
            conn.close()
            return {"result": [{"id": r[0], "sender": r[1], "content": r[2],
                                 "created_at": str(r[3])} for r in rows]}

        if tool_name == "grove_heartbeat":
            cur.execute("SELECT id FROM grove.channels WHERE name='heartbeat' LIMIT 1")
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO grove.messages (channel_id, sender, content) VALUES (%s, %s, %s)",
                    (row[0], arguments.get("sender", ""), "♥"),
                )
            conn.close()
            return {"ok": True}

        conn.close()
    except Exception as e:
        return {"error": f"grove dispatch error: {e}"}
    return {"error": f"unknown grove tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Subprocess fallback (for tools not covered by direct dispatch)
# Sends proper MCP initialize handshake.
# ---------------------------------------------------------------------------

def _unwrap_tool_response(data: dict) -> dict:
    """Unwrap MCP content envelope → plain dict."""
    inner = data.get("result", data)
    if isinstance(inner, dict) and "content" in inner:
        for block in inner["content"]:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except Exception:
                    return {"text": block["text"]}
    return inner


def _subprocess_call(tool_name: str, arguments: dict, timeout: int) -> dict:
    init_msg = json.dumps({
        "jsonrpc": "2.0", "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "willow-hook", "version": "1"},
        },
    })
    initialized_notif = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    })
    tool_msg = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    })

    env = os.environ.copy()
    env.setdefault("WILLOW_SAFE_ROOT", str(Path.home() / "github" / "SAFE" / "Applications"))
    env.setdefault("WILLOW_PG_DB", "willow_20")
    env.setdefault("WILLOW_PG_USER", os.environ.get("USER", ""))


    def _read_line(stream, wait_secs) -> str | None:
        """Read one non-empty line from stream with a wall-clock timeout."""
        box: list = []
        def _worker():
            while True:
                line = stream.readline()
                if line.strip():
                    box.append(line.strip())
                    return
                if not line:   # EOF
                    return
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(wait_secs)
        return box[0] if box else None

    try:
        proc = subprocess.Popen(
            [str(_WILLOW_MCP)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except Exception as e:
        return {"error": str(e), "tool": tool_name}

    try:
        # Step 1 — send initialize, wait for init response
        proc.stdin.write(init_msg + "\n")
        proc.stdin.flush()
        init_line = _read_line(proc.stdout, wait_secs=min(timeout, 8))
        if not init_line:
            return {"error": "timeout_on_init", "tool": tool_name}

        # Step 2 — send initialized notification + tool call; keep stdin open until
        # the response arrives, then close. Closing stdin early triggers FastMCP's
        # stdio transport shutdown which cancels the in-flight tool handler.
        proc.stdin.write(initialized_notif + "\n" + tool_msg + "\n")
        proc.stdin.flush()
        tool_line = _read_line(proc.stdout, wait_secs=timeout)
        proc.stdin.close()
        if not tool_line:
            return {"error": "no_tool_response", "tool": tool_name}

        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    except Exception as e:
        return {"error": str(e), "tool": tool_name}
    finally:
        try:
            proc.kill()
        except Exception:
            pass

    try:
        data = json.loads(tool_line)
        if data.get("id") == 1:
            return _unwrap_tool_response(data)
        return {"error": "unexpected_response_id", "raw": tool_line[:200], "tool": tool_name}
    except Exception as e:
        return {"error": f"parse_error: {e}", "tool": tool_name}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def call(tool_name: str, arguments: dict, timeout: int = 10) -> dict:
    """Dispatch a tool call. Direct path for store/grove; subprocess fallback for all else."""
    if tool_name.startswith("store_"):
        try:
            return _dispatch_store(tool_name, arguments)
        except Exception as e:
            return {"error": f"store dispatch error: {e}", "tool": tool_name}

    if tool_name.startswith("grove_"):
        try:
            return _dispatch_grove(tool_name, arguments)
        except Exception as e:
            return {"error": f"grove dispatch error: {e}", "tool": tool_name}

    if tool_name.startswith("soil_"):
        try:
            return _dispatch_soil(tool_name, arguments)
        except Exception as e:
            return {"error": f"soil dispatch error: {e}", "tool": tool_name}

    if tool_name == "kb_search":
        try:
            return _dispatch_kb(tool_name, arguments)
        except Exception as e:
            return {"error": f"kb dispatch error: {e}", "tool": tool_name}

    return _subprocess_call(tool_name, timeout=timeout, arguments=arguments)
