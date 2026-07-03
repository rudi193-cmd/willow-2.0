#!/usr/bin/env python3
"""
sap/sap_mcp.py — SAP MCP Server 2.0
willow-2.0 / SAP MCP 2.0
b20: SAPMCP2 · ΔΣ=42

FastMCP rebuild of sap_mcp.py.

Tool prefixes (14 domains):
  kb_        knowledge base
  soil_      store (StorePort → WillowStore)
  fleet_     server status, health, reload, restart
  agent_     dispatch, route, task submission
  fork_      session forks
  skill_     skill registry
  mem_       jeles / binder / ratify
  index_     opus search and feedback
  ledger_    frank ledger read/write
  task_      task queue
  handoff_   handoff search
  soul_      tension_scan, dream_check, dream_run (Soul mechanics)
  nest_      nest scan / queue
  infer_     chat, imagine, speak

Entry points:
  stdio (default):    python3 sap/sap_mcp.py
  HTTP:               python3 sap/sap_mcp.py --http [--host 127.0.0.1] [--port 6274]
                        Set WILLOW_MCP_API_KEY when binding beyond loopback.

  .mcp.json stdio:    {"command": "python3", "args": ["sap/sap_mcp.py"]}
  .mcp.json HTTP:     {"url": "http://127.0.0.1:6274/mcp"}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from sap.handoff_index import (
    extract_live_handoff_notes,
    extract_next_bite,
    filter_handoff_candidates,
    handoff_select_sql,
    scan_markdown_handoffs,
    select_best_handoff,
)
from sap.handoff_paths import discover_handoff_dirs, handoff_db_path, handoffs_roots
from typing import AsyncIterator

# ── Path setup ────────────────────────────────────────────────────────────────
_SAP_ROOT    = Path(__file__).parent.parent   # willow-2.0/
_WILLOW_CORE = _SAP_ROOT / "core"

_sap_str = str(_SAP_ROOT)
if _sap_str in sys.path:
    sys.path.remove(_sap_str)
sys.path.insert(0, _sap_str)

_core_str = str(_WILLOW_CORE)
if _core_str not in sys.path:
    sys.path.insert(1, _core_str)


def _fleet_home() -> Path:
    from willow.fylgja.willow_home import willow_home

    return willow_home(_SAP_ROOT)


def _store_root() -> Path:
    from willow.fylgja.willow_home import resolve_store_root

    return resolve_store_root(_SAP_ROOT)


# ── Version ───────────────────────────────────────────────────────────────────
from core.version import VERSION
from core.code_version import boot_sha as _boot_sha, staleness as _code_staleness

# Stamp the commit this process started on, at import time, before any PR merged
# after startup can advance HEAD under the running server. fleet_status compares
# this to the live HEAD so a server running stale code is visible without anyone
# having to remember a restart (the trap behind dream_state/SOIL/ledger drift).
_boot_sha()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [w2] %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("sap.server")

# ── FastMCP ───────────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("FastMCP not installed. Run: pip install 'mcp>=1.6'", file=sys.stderr)
    sys.exit(1)

# ── Middleware ────────────────────────────────────────────────────────────────
from sap.middleware import _executor, sap_gate  # noqa: F401 — re-exported for tool modules

# ── Domain imports ────────────────────────────────────────────────────────────
from core.agent_identity import require_agent_name

try:
    from core.run_ledger import log_event as _rl_log_event
except Exception:
    def _rl_log_event(event_type: str, ref: str = "", **_kw) -> None:  # type: ignore[misc]
        pass

import sap.core.inference as _inf
import sap.core.blast as _blast

try:
    from core.pg_bridge import PgBridge, init_schema
except Exception as _pg_import_err:
    PgBridge    = None  # type: ignore[assignment,misc]
    init_schema = None  # type: ignore[assignment]
    logger.warning("pg_bridge import failed: %s", _pg_import_err)

from core.store_port import StorePort, get_store_port

try:
    from willow.grove_coordination import node_announce as _node_announce
except Exception as _gc_import_err:
    _node_announce = None  # type: ignore[assignment]
    logger.warning("grove_coordination import failed: %s", _gc_import_err)

# ── Config ────────────────────────────────────────────────────────────────────
_MCP_AGENT = require_agent_name()
STORE_ROOT = os.environ.get("WILLOW_STORE_ROOT", str(_SAP_ROOT / "store"))
HANDOFF_DB = os.environ.get(
    "WILLOW_HANDOFF_DB",
    str(handoff_db_path(_MCP_AGENT)),
)
HANDOFF_DIRS = os.environ.get(
    "WILLOW_HANDOFF_DIRS",
    discover_handoff_dirs(_MCP_AGENT),
)

_MCP_INSTRUCTIONS = (Path(__file__).parent / "MCP_INSTRUCTIONS.md").read_text(encoding="utf-8")

# ── Global state (initialized in lifespan) ────────────────────────────────────
pg:    "PgBridge | None" = None  # type: ignore[type-arg]
store: StorePort = None  # type: ignore[assignment]

# ── Module-level constants ────────────────────────────────────────────────────
_ENV_SNAPSHOT_PREFIXES = ("WILLOW_", "GROVE_", "HOME", "USER", "PATH", "PGUSER", "PGHOST", "PGPORT")


# ── Startup helpers ───────────────────────────────────────────────────────────

def _kill_stale_instances() -> None:
    """Terminate other sap_mcp.py processes FROM THIS REPO and their idle Postgres connections."""
    import psutil  # type: ignore[import]

    my_pid = os.getpid()
    my_root = str(_SAP_ROOT)  # Only kill instances from the same repo root
    stale_pids: list[int] = []

    try:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            if proc.info["pid"] == my_pid:
                continue
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if ("sap_mcp" in cmdline or "sap.server" in cmdline) and my_root in cmdline:
                stale_pids.append(proc.info["pid"])
    except Exception as err:
        logger.warning("[w2] stale instance scan failed: %s", err)
        return

    for pid in stale_pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()  # SIGTERM on POSIX, TerminateProcess on Windows
            logger.info("[w2] sent SIGTERM to stale sap_mcp pid=%d", pid)
            try:
                proc.wait(timeout=1)
            except psutil.TimeoutExpired:
                proc.kill()  # SIGKILL on POSIX, TerminateProcess on Windows
        except psutil.NoSuchProcess:
            pass
        except Exception as err:
            logger.warning("[w2] could not kill pid=%d: %s", pid, err)

        # Terminate any Postgres connections left behind by the stale processes.
        try:
            import psycopg2
            pg_db = os.environ.get("WILLOW_PG_DB", "willow_20")
            gc = psycopg2.connect(dbname=pg_db)
            gc.autocommit = True
            with gc.cursor() as c:
                # Scope to our own database: pg_stat_activity is cluster-wide,
                # and an unfiltered kill terminates idle-in-transaction sessions
                # in EVERY database — production willow_20 included (observed
                # 2026-07-03: test-suite sap_mcp spawns killing live fleet
                # connections). Stale-instance leftovers only ever live in the
                # database this instance connects to.
                c.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')"
                    "   AND datname = current_database()"
                    "   AND pid != pg_backend_pid()"
                )
            gc.close()
            logger.info("[w2] terminated stale Postgres connections from old instances")
        except Exception as err:
            logger.warning("[w2] pg cleanup after stale kill failed: %s", err)


def _init_pg():
    """Return PgBridge, or SqliteBridge if Postgres is unavailable, or None on total failure."""
    if PgBridge is None:
        # pg_bridge import failed — fall directly to SQLite
        try:
            from core.sqlite_bridge import SqliteBridge
            logger.warning("[w2] pg_bridge unavailable — using SQLite fallback")
            return SqliteBridge()
        except Exception:
            return None
    try:
        _pg = PgBridge()
        return _pg
    except Exception as err:
        logger.error("[w2] pg init failed: %s — falling back to SQLite", err)
        try:
            flag = _fleet_home() / "pg_failure.flag"
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text(str(err))
        except Exception:
            pass
        try:
            import psycopg2
            gc = psycopg2.connect(dbname=os.environ.get("WILLOW_PG_DB", "willow_20"))
            with gc.cursor() as c:
                c.execute("SELECT id FROM grove.channels WHERE name='general' LIMIT 1")
                ch = c.fetchone()
                if ch:
                    c.execute(
                        "INSERT INTO grove.messages (channel_id, sender, content) VALUES (%s, %s, %s)",
                        (ch[0], "willow-mcp", f"[ALERT] pg=None at MCP startup. {err}"),
                    )
            gc.commit()
            gc.close()
        except Exception:
            pass
        # SQLite fallback
        try:
            from core.sqlite_bridge import SqliteBridge
            logger.warning("[w2] Postgres down — using SQLite fallback")
            return SqliteBridge()
        except Exception:
            return None


def _startup_node_announce(s: StorePort) -> None:
    """Register this node in the grove registry with live hardware + Ollama models."""
    if _node_announce is None:
        return
    import socket as _socket
    addr = f"{_MCP_AGENT}@{_socket.gethostname()}"
    try:
        _node_announce(s, addr=addr, name=_MCP_AGENT, willow_version=VERSION)
        logger.info("[w2] node_announce: %s registered", addr)
    except Exception as err:
        logger.warning("[w2] node_announce failed: %s", err)


def _startup_backfill_check() -> None:
    """Queue willow_embed_backfill task if NULL embeddings exist."""
    try:
        if PgBridge is None:
            return
        pb = PgBridge()
        with pb.conn.cursor() as cur:
            cur.execute("""
                SELECT
                  (SELECT COUNT(*) FROM knowledge      WHERE embedding IS NULL) +
                  (SELECT COUNT(*) FROM opus_atoms     WHERE embedding IS NULL) +
                  (SELECT COUNT(*) FROM jeles_atoms    WHERE embedding IS NULL)
                AS total_null
            """)
            total_null = cur.fetchone()[0]
        if total_null == 0:
            return
        with pb.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM public.tasks WHERE task LIKE '%willow_embed_backfill%'"
                " AND status IN ('pending','running') LIMIT 1"
            )
            existing = cur.fetchone()
        if not existing:
            script = _SAP_ROOT / "scripts" / "willow_embed_backfill.py"
            pb.submit_task(f'"${{WILLOW_PYTHON:-python3}}" {script}', submitted_by="sap_startup", agent="kart")
            logger.info("[w2] %d rows with NULL embedding — backfill queued", total_null)
        else:
            logger.info("[w2] %d rows with NULL embedding — backfill already queued", total_null)
    except Exception as err:
        logger.warning("[w2] backfill check failed: %s", err)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    global pg, store

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _kill_stale_instances)
    pg    = await loop.run_in_executor(_executor, _init_pg)
    store = get_store_port(STORE_ROOT)

    await loop.run_in_executor(_executor, _startup_node_announce, store)
    await loop.run_in_executor(_executor, _startup_backfill_check)

    logger.info("b20: SAPMCP2 ΔΣ=42  version=%s  pg=%s  store=%s",
                VERSION, "ok" if pg else "UNAVAILABLE", STORE_ROOT)
    yield

    # Cleanup
    _executor.shutdown(wait=False)
    if pg:
        try:
            pg.conn.close()
        except Exception:
            pass


# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "willow2",
    instructions=_MCP_INSTRUCTIONS,
    lifespan=_lifespan,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_TOOL_TIMEOUT           = float(os.environ.get("WILLOW_TOOL_TIMEOUT",           "45"))
_TOOL_TIMEOUT_INFERENCE = float(os.environ.get("WILLOW_INFERENCE_TIMEOUT",      "300"))


def _check_ollama() -> dict:
    try:
        import urllib.request
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/tags"
        with urllib.request.urlopen(url, timeout=2) as resp:
            import json as _json
            data = _json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            return {"running": True, "models": models}
    except Exception:
        return {"running": False}


def _check_host() -> dict:
    try:
        from core.host_profile import load_host_profile
        return load_host_profile()
    except Exception as e:
        return {"error": str(e)}


def _check_metabolic() -> dict:
    from core.metabolic_status import check_metabolic_status
    return check_metabolic_status()


def _normalize_local_paths(text: str) -> str:
    """Reduce PII leakage from local filesystem paths in written content."""
    try:
        if not isinstance(text, str) or not text:
            return text
        home = str(Path.home())
        if home and home in text:
            text = text.replace(home, "~")
        import re
        text = re.sub(r"(?<!\w)/home/[^/\s]+", "~", text)
        text = re.sub(r"(?<!\w)/Users/[^/\s]+", "~", text)
        return text
    except Exception:
        return text


def _qualifies_as_flag(record: dict, deviation: float) -> bool:
    return (
        record.get("type") in ("failure-log",) or
        record.get("domain") == "governance" or
        deviation > 0.6 or
        (record.get("type") == "gap" and record.get("severity") in ("high", "critical"))
    )


def _kart_tasks_running() -> int:
    """Best-effort count of in-flight (claimed/running) kart tasks."""
    try:
        if pg and hasattr(pg, "kart_queue_stats"):
            stale_s = int(os.environ.get("KART_STALE_SECONDS", "3600"))
            stats = pg.kart_queue_stats("kart", stale_s)
            return int(stats.get("running", 0) or 0)
    except Exception:
        pass
    return 0


def _restart_kart_worker(only_if_idle: bool = True) -> dict:
    """Restart the kart-worker systemd user service so merged Kart code goes live.

    The Kart daemon (core/kart_worker.py → core/kart_execute.py / kart_sandbox.py)
    runs as a separate `kart-worker.service`; neither fleet_reload's in-process
    hot-swap nor fleet_restart's process exit reaches it, so merged Kart code runs
    stale until the unit is bounced. The MCP server runs host-side (not in bwrap),
    so it can drive `systemctl --user` directly.

    only_if_idle: when a kart task is in-flight, skip the bounce — restarting would
    SIGKILL the running task (the reaper later requeues it). Caller-chosen default.
    """
    running = _kart_tasks_running()
    if only_if_idle and running:
        return {
            "status": "skipped",
            "reason": f"{running} kart task(s) in-flight — not interrupting",
            "running": running,
            "hint": "re-run with force, or `systemctl --user restart kart-worker` on the host when idle",
        }
    import shutil
    import subprocess
    if not shutil.which("systemctl"):
        return {
            "status": "unavailable",
            "reason": "systemctl not found",
            "hint": "restart the Kart consumer manually on this node",
        }
    try:
        r = subprocess.run(
            ["systemctl", "--user", "restart", "kart-worker"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return {"status": "restarted", "unit": "kart-worker"}
        return {
            "status": "error",
            "returncode": r.returncode,
            "stderr": (r.stderr or "").strip()[:300],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _hot_reload(target: str = "all") -> dict:
    global pg, store, _inf, _blast
    import importlib
    reloaded: list[str] = []
    errors:   list[str] = []
    kart_result: dict | None = None

    if target in ("all", "blast"):
        try:
            sys.modules.pop("sap.core.blast", None)
            import sap.core.blast as _blast_new
            importlib.reload(_blast_new)
            _blast = _blast_new
            reloaded.append("blast: reloaded")
        except Exception as e:
            errors.append(f"blast: {e}")

    if target in ("all", "inference"):
        try:
            sys.modules.pop("sap.core.inference", None)
            import sap.core.inference as _inf_new
            importlib.reload(_inf_new)
            _inf = _inf_new
            reloaded.append("inference: reloaded")
        except Exception as e:
            errors.append(f"inference: {e}")

    if target in ("all", "postgres"):
        try:
            sys.modules.pop("core.pg_bridge", None)
            import core.pg_bridge as _pgmod
            importlib.reload(_pgmod)
            pg = _pgmod.PgBridge()
            reloaded.append("postgres: reconnected")
        except Exception as e:
            errors.append(f"postgres: {e}")

    if target in ("all", "store"):
        try:
            store = get_store_port(STORE_ROOT)
            reloaded.append(f"store: reloaded ({STORE_ROOT})")
        except Exception as e:
            errors.append(f"store: {e}")

    if target in ("all", "gate"):
        try:
            sys.modules.pop("sap.core.gate", None)
            import sap.core.gate as _gate_new
            importlib.reload(_gate_new)
            # Patch middleware's name-bound references so permitted() sees new PERMISSION_GROUPS
            import sap.middleware as _mw
            _mw.sap_authorized = _gate_new.authorized
            _mw.sap_permitted  = _gate_new.permitted
            reloaded.append("gate: reloaded")
        except Exception as e:
            errors.append(f"gate: {e}")
        try:
            sys.modules.pop("core.safe_agents", None)
            import core.safe_agents as _sa_new
            importlib.reload(_sa_new)
            reloaded.append("safe_agents: reloaded")
        except Exception as e:
            errors.append(f"safe_agents: {e}")

    # The Kart worker is a separate systemd service — it cannot be hot-swapped
    # in this process, so bring it current by bouncing the unit (idle-only, so an
    # in-flight task is not interrupted). This is the only out-of-process step.
    if target in ("all", "kart"):
        kart_result = _restart_kart_worker(only_if_idle=True)
        reloaded.append(f"kart-worker: {kart_result.get('status')}")

    # Honesty: hot reload only re-imports the whitelist above. Core modules
    # (dream_state, run_ledger, …) and the facade tool bodies in this file are
    # NOT swapped — only a full process restart loads them. Surface that plus the
    # live staleness so the caller is not misled into thinking a merged fix to
    # one of those is now live.
    stale = _code_staleness()
    out = {
        "status":   "reloaded" if not errors else "partial",
        "reloaded": reloaded,
        "errors":   errors if errors else None,
        "kart": kart_result,
        "code_version": stale,
        "not_hot_swappable": (
            "core.* modules (dream_state, run_ledger, …) and the sap_mcp facade "
            "tool bodies are NOT reloaded here — only fleet_restart (full process "
            "exit) loads them. The Kart worker IS handled, via systemctl restart."
        ),
    }
    if stale.get("stale"):
        out["warning"] = (
            "on-disk code is ahead of the running process — fleet_reload cannot "
            "activate changes outside its module whitelist; run fleet_restart."
        )
    return out


# ── Tools — fleet_ domain ─────────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_status(app_id: str) -> dict:
    """Call this first. Confirms Postgres, SOIL, and Ollama are up.
    If degraded or down, surface it and stop — everything else depends on this."""
    logger.info("[w2] fleet_status app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    local_stats  = await loop.run_in_executor(_executor, store.stats)
    local_count  = sum(s["count"] for s in local_stats.values()) if local_stats else 0
    pg_stats     = await loop.run_in_executor(_executor, pg.stats) if pg and hasattr(pg, "stats") else {}
    ollama       = await loop.run_in_executor(_executor, _check_ollama)
    host         = await loop.run_in_executor(_executor, _check_host)

    try:
        from sap.core.gate import SAFE_ROOT, PROFESSOR_ROOT, _verify_pgp
        _pass, _fail = 0, []
        for mp in list(SAFE_ROOT.glob("*/safe-app-manifest.json")) + \
                  list(PROFESSOR_ROOT.glob("*/safe-app-manifest.json")):
            ok, _ = await loop.run_in_executor(_executor, _verify_pgp, mp)
            if ok:
                _pass += 1
            else:
                _fail.append(mp.parent.name)
        manifests: dict = {"pass": _pass, "fail": len(_fail)}
        if _fail:
            manifests["failed"] = _fail
    except Exception as e:
        manifests = {"error": str(e)}

    metabolic = await loop.run_in_executor(_executor, _check_metabolic)

    kart_stats: dict = {}
    if pg and hasattr(pg, "kart_queue_stats"):
        try:
            stale_s = int(os.environ.get("KART_STALE_SECONDS", "3600"))
            kart_stats = await loop.run_in_executor(
                _executor, pg.kart_queue_stats, "kart", stale_s
            )
        except Exception as e:
            kart_stats = {"error": str(e)}

    human_required: dict = {}
    if pg and hasattr(pg, "human_required_stats"):
        try:
            human_required = await loop.run_in_executor(_executor, pg.human_required_stats)
        except Exception as e:
            human_required = {"error": str(e)}

    frank_ledger: dict = {}
    if pg and hasattr(pg, "ledger_verify"):
        try:
            frank_ledger = await loop.run_in_executor(_executor, pg.ledger_verify)
        except Exception as e:
            frank_ledger = {"error": str(e)}

    try:
        from sap.core.gate import gate_mode as _gate_mode, gate_hostname_detail as _gate_hostname_detail
        _gm = _gate_mode()
        _ghd = _gate_hostname_detail()
    except Exception:
        _gm = "unknown"
        _ghd = "unknown"

    return {
        "local_store": {"collections": len(local_stats), "records": local_count},
        "postgres":    pg_stats if pg_stats else ("not_connected" if pg is None else "connected"),
        "host":        host,
        "ollama":      ollama,
        "manifests":   manifests,
        "metabolic":   metabolic,
        "kart":        kart_stats,
        "human_required": human_required,
        "frank_ledger": frank_ledger,
        "gate_mode":   _gm,
        "gate_hostname_check": _ghd,
        "code_version": _code_staleness(),
        "mode":        "portless",
    }


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_identity_status(app_id: str) -> dict:
    """Return the identity matrix: active-agent, MCP env, Cursor MCP symlink, hooks, Grove sender, drift."""
    logger.info("[w2] fleet_identity_status app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _collect():
        from willow.fylgja.identity_bind import collect_identity_matrix, check_app_id

        matrix = collect_identity_matrix()
        action, msg = check_app_id(app_id)
        matrix["mcp_caller_app_id"] = app_id
        matrix["caller_bind"] = {"action": action, "message": msg}
        return matrix

    return await loop.run_in_executor(_executor, _collect)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_health(app_id: str) -> dict:
    """Fast (<200ms) MCP server health check: circuit breaker state, pool usage,
    tool executor threads, uptime. Use to diagnose hangs without touching Postgres."""
    logger.info("[w2] fleet_health app_id=%s", app_id)
    try:
        from core.pg_bridge import cb_state as _cb_state, _pool as _pg_pool, _pool_maxconn as _pmx
        cb        = _cb_state()
        pool_used = len(_pg_pool._used) if _pg_pool else 0
        pool_info: dict = {"used": pool_used, "max": _pmx, "pct": round(pool_used / _pmx * 100)}
    except Exception as he:
        cb        = {"error": str(he)}
        pool_info = {}

    import threading
    executor_threads = len([t for t in threading.enumerate() if "willow-tool" in t.name])

    return {
        "status":                 "ok",
        "circuit_breaker":        cb,
        "pool":                   pool_info,
        "tool_executor_threads":  executor_threads,
        "tool_timeout_s":         _TOOL_TIMEOUT,
        "pg_connect_timeout_s":   int(os.environ.get("WILLOW_PG_CONNECT_TIMEOUT", "5")),
        "pg_statement_timeout_ms": int(os.environ.get("WILLOW_PG_STATEMENT_TIMEOUT", "30000")),
    }


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_system_status(app_id: str) -> dict:
    """Full system status: store stats, Postgres stats, connectivity, gate manifests."""
    logger.info("[w2] fleet_system_status app_id=%s", app_id)
    return await fleet_status(app_id=app_id)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_agents(app_id: str) -> dict:
    """List registered Willow agents and their trust levels. Queries the agents DB table first; falls back to the built-in static list."""
    logger.info("[w2] fleet_agents app_id=%s", app_id)

    # Static fallback — canonical registry in core.safe_agents.FLEET_AGENTS
    try:
        from core.safe_agents import FLEET_AGENTS as _fleet_registry
        _static_agents = [
            {"name": k, "trust": v["trust"], "role": v.get("role", "")}
            for k, v in sorted(_fleet_registry.items())
        ]
    except Exception:
        _static_agents = []

    agents = []
    source = "static"

    # Query DB first
    if pg:
        try:
            loop = asyncio.get_running_loop()
            db_agents = await loop.run_in_executor(_executor, pg.agents_list_from_db)
            if db_agents:
                agents = db_agents
                source = "db"
        except Exception:
            pass

    if not agents:
        agents = list(_static_agents)

    # Merge locally registered agents from $WILLOW_HOME/agents.json
    try:
        import json as _json
        override = _fleet_home() / "agents.json"
        if override.exists():
            existing = {a["name"] for a in agents}
            for entry in _json.loads(override.read_text()):
                if entry.get("name") and entry["name"] not in existing:
                    agents.append(entry)
    except Exception:
        pass
    return {"agents": agents, "count": len(agents), "source": source}


@mcp.tool(annotations={"destructiveHint": True})
@sap_gate()
async def fleet_reload(app_id: str, target: str = "all") -> dict:
    """Hot-reload Willow modules without restarting the MCP server.
    target: all | blast | inference | postgres | store | gate | kart
    target 'all' (and 'kart') also bounces the kart-worker systemd unit so merged
    Kart code goes live — skipped automatically while a Kart task is in-flight."""
    logger.info("[w2] fleet_reload app_id=%s target=%s", app_id, target)
    loop = asyncio.get_running_loop()
    timeout_s = float(os.environ.get("WILLOW_FLEET_RELOAD_TIMEOUT", "30"))
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_executor, _hot_reload, target),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        logger.error("[w2] fleet_reload timed out after %.0fs target=%s", timeout_s, target)
        return {
            "error": "reload_timeout",
            "target": target,
            "timeout_s": timeout_s,
            "message": (
                f"Hot reload did not finish within {timeout_s:.0f}s. "
                "Try target='gate' for permission groups only, or fleet_restart + /mcp."
            ),
        }


@mcp.tool(annotations={"destructiveHint": True})
@sap_gate()
async def fleet_restart(app_id: str, include_kart: bool = True) -> dict:
    """Restart the SAP MCP server process. Run /mcp in Claude Code to reconnect.
    include_kart (default True): also bounce the kart-worker systemd unit so the
    full restart brings both the MCP server and the Kart daemon current in one
    call. Skipped automatically while a Kart task is in-flight."""
    logger.info("[w2] fleet_restart app_id=%s include_kart=%s — process exiting", app_id, include_kart)

    kart_result = _restart_kart_worker(only_if_idle=True) if include_kart else {"status": "skipped", "reason": "include_kart=False"}

    import threading
    def _delayed_exit():
        import time

        time.sleep(0.2)
        os._exit(0)
    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {
        "status": "restarting",
        "note": "SAP MCP process exiting. Run /mcp in Claude Code to reconnect.",
        "kart": kart_result,
    }


# ── Tools — soil_ domain (SOIL store reads + writes) ─────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_get(app_id: str, collection: str, record_id: str) -> dict:
    """Read a single record by ID from a SOIL collection.
    Returns the record object or {error: not_found}."""
    logger.info("[w2] soil_get app_id=%s col=%s id=%s", app_id, collection, record_id)
    loop   = asyncio.get_running_loop()
    result = await loop.run_in_executor(_executor, store.get, collection, record_id)
    if result is None:
        return {"error": "not_found"}
    return result


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_search(
    app_id:     str,
    collection: str,
    query:      str,
    after:      str  = "",
    semantic:   bool = False,
) -> list:
    """Full-text search within a single SOIL collection. Multi-keyword queries are ANDed.
    Prefer kb_search for the Postgres knowledge base."""
    logger.info("[w2] soil_search app_id=%s col=%s q=%r", app_id, collection, query)
    loop = asyncio.get_running_loop()
    if semantic:
        result = await loop.run_in_executor(_executor, store.search_semantic, collection, query)
    else:
        result = await loop.run_in_executor(
            _executor, store.search, collection, query, after or None
        )
    return result


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_search_all(app_id: str, query: str) -> dict:
    """Search across ALL SOIL collections simultaneously.
    Use when you don't know which collection holds the answer."""
    logger.info("[w2] soil_search_all app_id=%s q=%r", app_id, query)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, store.search_all, query)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_list(app_id: str, collection: str, filter: dict = None) -> list:
    """Return records in a SOIL collection.
    filter: optional dict of {field: value} to match — e.g. {"flag_state": "open"}.
    Use soil_search for large collections — soil_list returns everything unless filtered."""
    logger.info("[w2] soil_list app_id=%s col=%s filter=%s", app_id, collection, filter)
    loop = asyncio.get_running_loop()
    records = await loop.run_in_executor(_executor, store.all, collection)
    if filter:
        records = [r for r in records if all(r.get(k) == v for k, v in filter.items())]
    return records


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_edges_for(app_id: str, record_id: str) -> list:
    """Return all graph edges where the given SOIL record is either source or target."""
    logger.info("[w2] soil_edges_for app_id=%s id=%s", app_id, record_id)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, store.edges_for, record_id)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_stats(app_id: str) -> dict:
    """Return record counts and trajectory scores for every SOIL collection."""
    logger.info("[w2] soil_stats app_id=%s", app_id)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, store.stats)


@mcp.tool()
@sap_gate(write=True)
async def soil_put(
    app_id:     str,
    collection: str,
    record:     dict,
    record_id:  str  = "",
    deviation:  float = 0.0,
) -> dict:
    """Write a record to a SOIL collection. Append-only.
    Returns {id, action} where action is work_quiet/flag/stop from the angular deviation rubric."""
    logger.info("[w2] soil_put app_id=%s col=%s dev=%.3f", app_id, collection, deviation)
    loop = asyncio.get_running_loop()

    def _put():
        rid, action, proposals = store.put(
            collection, record,
            record_id=record_id or None,
            deviation=deviation,
        )
        out: dict = {"id": rid, "action": action}
        if proposals:
            out["proposals"] = [p.to_dict() for p in proposals]
        # Auto-flag qualifying records into {namespace}/flags
        namespace = collection.split("/")[0]
        if not collection.endswith("/flags") and _qualifies_as_flag(record, deviation):
            store.put(f"{namespace}/flags", {
                "atom_id":    rid,
                "collection": collection,
                "deviation":  deviation,
                "ts":         __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            })
        return out

    return await loop.run_in_executor(_executor, _put)


@mcp.tool()
@sap_gate(write=True)
async def soil_update(
    app_id:     str,
    collection: str,
    record_id:  str,
    record:     dict,
    deviation:  float = 0.0,
) -> dict:
    """Update an existing SOIL record in-place. Every update is audit-trailed."""
    logger.info("[w2] soil_update app_id=%s col=%s id=%s", app_id, collection, record_id)
    loop = asyncio.get_running_loop()

    def _update():
        rid, action, proposals = store.update(collection, record_id, record, deviation=deviation)
        out: dict = {"id": rid, "action": action}
        if proposals:
            out["proposals"] = [p.to_dict() for p in proposals]
        return out

    return await loop.run_in_executor(_executor, _update)


@mcp.tool(annotations={"destructiveHint": True})
@sap_gate()
async def soil_delete(app_id: str, collection: str, record_id: str) -> dict:
    """Soft-delete a SOIL record — invisible to search/get but retained in the audit trail."""
    logger.info("[w2] soil_delete app_id=%s col=%s id=%s", app_id, collection, record_id)
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(_executor, store.delete, collection, record_id)
    return {"deleted": ok}


@mcp.tool()
@sap_gate(write=True)
async def soil_add_edge(
    app_id:   str,
    from_id:  str,
    to_id:    str,
    relation: str,
    context:  str = "",
) -> dict:
    """Add a directed edge between two SOIL records in the knowledge graph."""
    logger.info("[w2] soil_add_edge app_id=%s %s→%s rel=%s", app_id, from_id, to_id, relation)
    loop = asyncio.get_running_loop()

    def _add():
        rid, action, proposals = store.add_edge(from_id, to_id, relation, context=context)
        out: dict = {"id": rid, "action": action}
        if proposals:
            out["proposals"] = [p.to_dict() for p in proposals]
        return out

    return await loop.run_in_executor(_executor, _add)


@mcp.tool()
@sap_gate(write=True)
async def pg_edge_add(
    app_id:   str,
    from_id:  str,
    to_id:    str,
    relation: str,
    context:  str = "",
    human_consent: bool = False,
) -> dict:
    """Add a directed edge to the Postgres edges table (durable KB graph).
    Distinct from SOIL graph — use soil_add_edge for in-session working graph."""
    logger.info("[w2] pg_edge_add app_id=%s %s→%s rel=%s", app_id, from_id, to_id, relation)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: pg.edge_add(
            from_id, to_id, relation, app_id, context or None, human_consent=human_consent
        ),
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def pg_edge_list(
    app_id:  str,
    from_id: str = "",
    to_id:   str = "",
    limit:   int = 50,
) -> dict:
    """List edges from the Postgres edges table. Filter by from_id or to_id (or both)."""
    logger.info("[w2] pg_edge_list app_id=%s from=%s to=%s", app_id, from_id, to_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    edges = await loop.run_in_executor(
        _executor, pg.edge_list, from_id or None, to_id or None, limit,
    )
    return {"edges": edges, "count": len(edges)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def soil_audit(app_id: str, collection: str, limit: int = 20) -> list:
    """Read the recent audit log for a SOIL collection — creates, updates, soft-deletes."""
    logger.info("[w2] soil_audit app_id=%s col=%s", app_id, collection)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, store.audit_log, collection, limit)


# ── Tools — kb_ domain (Postgres knowledge base) ─────────────────────────────

def _no_pg() -> dict:
    return {"error": "not_available", "reason": "Postgres not connected"}


def _resolve_kb_lane_scope(app_id: str, scope: str = "", project: str = ""):
    from core.canonical_lanes import resolve_lane_read_scope
    return resolve_lane_read_scope(
        app_id,
        scope=scope,
        project=project or None,
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def kb_search(
    app_id:            str,
    query:             str,
    limit:             int  = 20,
    semantic:          bool = True,
    include_embedding: bool = False,
    fields:            list = None,
    tier:              str  = "",
    expand_neighbors:  bool = True,
    continuity:        bool = False,
    scope:             str  = "",
    project:           str  = "",
) -> dict:
    """Search Willow's Postgres knowledge graph before building anything.
    Returns atoms by title and summary. Search first — another agent may have already
    solved or decided this. Use kb_get to fetch the full atom.
    tier: filter to frontier|contested|canonical|superseded (omit for all tiers).
    expand_neighbors: one-hop graph expansion via public.edges (default on).
    continuity=True uses the curated B2-minus-intake retrieval pool (boot/cold-recovery).
    semantic=True uses the hybrid pgvector+BM25 RRF hot path when available.
    scope: default caller lane; willow may pass '*' for full god-view (incl. personal).
    project: explicit lane filter (must be permitted for caller)."""
    logger.info(
        "[w2] kb_search app_id=%s q=%r semantic=%s tier=%r continuity=%s scope=%r project=%r",
        app_id, query, semantic, tier, continuity, scope, project,
    )
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _search():
        tier_filter = tier or None
        lane_scope = _resolve_kb_lane_scope(app_id, scope=scope, project=project)
        explicit_project = (project or "").strip() or None
        # Sidecar veto (ADR-20260702 step 2): sensitive jeles/opus rows are
        # excluded unless the orchestrator asked for god-view — mirrors the
        # personal-lane exclusion semantics on knowledge.
        god_view = (scope or "").strip() == "*" and lane_scope.projects is None and not lane_scope.exclude
        if semantic:
            try:
                knowledge = pg.knowledge_search_semantic(
                    query, limit=limit, include_embedding=include_embedding,
                    fields=fields, tier=tier_filter, continuity=continuity,
                    project=explicit_project, lane_scope=lane_scope,
                )
                jeles    = pg.search_jeles_semantic(query, limit=limit // 2,
                                                    include_sensitive=god_view)
                opus     = pg.search_opus_semantic(query, limit=limit // 2,
                                                   include_sensitive=god_view)
                mode = "hybrid" if any("_rrf_score" in row for row in knowledge[:3]) else "semantic"
            except Exception:
                knowledge = pg.knowledge_search(
                    query, limit=limit, include_embedding=include_embedding,
                    fields=fields, tier=tier_filter,
                    project=explicit_project, lane_scope=lane_scope,
                )
                jeles = pg.jeles_keyword_search(query, limit=limit // 2,
                                                include_sensitive=god_view)
                opus  = pg.search_opus(query, limit=limit // 2,
                                       include_sensitive=god_view)
                mode = "degraded"
        else:
            knowledge = pg.knowledge_search(
                query, limit=limit, include_embedding=include_embedding,
                fields=fields, tier=tier_filter,
                project=explicit_project, lane_scope=lane_scope,
            )
            jeles = pg.jeles_keyword_search(query, limit=limit // 2,
                                            include_sensitive=god_view)
            opus  = pg.search_opus(query, limit=limit // 2,
                                   include_sensitive=god_view)
            mode = "keyword"

        neighbors: list = []
        if expand_neighbors and knowledge:
            seed_ids = [a["id"] for a in knowledge[:10] if a.get("id")]
            try:
                neighbors = pg.knowledge_expand_neighbors(
                    seed_ids, limit=max(5, limit // 3),
                    lane_scope=lane_scope,
                )
            except Exception:
                neighbors = []
            seen = {a["id"] for a in knowledge if a.get("id")}
            knowledge = knowledge + [n for n in neighbors if n.get("id") not in seen]

        # Relevance-gated promotion (KB 43AB3F89): warm hits whose cosine clears
        # the floor regardless of rank, not a fixed top-3. Falls back to top-N on
        # the keyword/degraded path (no _cosine_sim). Revert via
        # WILLOW_PROMOTE_MODE=topn. select_promotion_ids is pure; we promote here.
        from core.promotion_policy import select_promotion_ids
        for atom_id in select_promotion_ids(knowledge):
            try:
                pg.promote(atom_id)
            except Exception:
                pass
        for row in jeles:
            row["_table"] = "jeles_atoms"
        for row in opus:
            row["_table"] = "opus_atoms"
        # Taint rule (ADR-20260702): max sensitivity over everything returned.
        # Sidecar rows now carry their own sensitivity (step 2); rows without a
        # project resolve through atoms_taint fail-closed, so an untagged row
        # still taints the set. Advisory metadata — enforcement is the gateway.
        from core.canonical_lanes import atoms_taint
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

    return await loop.run_in_executor(_executor, _search)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def kb_startup_continuity(
    app_id: str,
    limit: int = 0,
) -> dict:
    """Run boot/cold-recovery KB continuity searches from startup_continuity.json.

    Each query uses continuity=True (curated B2-minus-intake pool) unless an entry
    sets continuity=false. Skim titles/summaries; kb_get only when tied to a gap.
    limit>0 caps every entry; default uses per-entry limits from the config."""
    from willow.fylgja.startup_continuity import iter_kb_searches, load_config

    logger.info("[w2] kb_startup_continuity app_id=%s limit=%s", app_id, limit)
    try:
        cfg = load_config()
        entries = iter_kb_searches(cfg)
    except Exception as exc:
        return {"error": "config_load_failed", "reason": str(exc)[:200]}

    async def _one(entry: dict) -> dict:
        q = entry["query"]
        entry_limit = int(entry.get("limit") or 6)
        use_limit = limit if limit > 0 else entry_limit
        semantic = bool(entry.get("semantic", True))
        continuity = bool(entry.get("continuity", True))
        tier = str(entry.get("tier") or "")
        result = await kb_search(
            app_id=app_id,
            query=q,
            limit=use_limit,
            semantic=semantic,
            tier=tier,
            expand_neighbors=True,
            continuity=continuity,
        )
        hits = result.get("knowledge") or []
        return {
            "query": q,
            "limit": use_limit,
            "semantic": semantic,
            "continuity": continuity,
            "total": result.get("total", len(hits)),
            "mode": result.get("mode"),
            "top": [
                {
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "summary": (a.get("summary") or "")[:240],
                }
                for a in hits[:use_limit]
            ],
        }

    batches = await asyncio.gather(*[_one(e) for e in entries])
    return {
        "continuity_pool": "curated",
        "queries_run": len(batches),
        "config_b17": cfg.get("b17"),
        "results": batches,
    }


@mcp.tool()
@sap_gate(write=True)
async def kb_promote(
    app_id:  str,
    atom_id: str,
    tier:    str,
    reason:  str = "",
    human_attestation: bool = False,
) -> dict:
    """Promote or demote a knowledge atom to a new lifecycle tier.
    tier: frontier → contested → canonical → superseded
    Records the transition in FRANK. Accepts legacy values (hypothesis/observed/validated) — auto-mapped."""
    logger.info("[w2] kb_promote app_id=%s atom=%s tier=%s", app_id, atom_id, tier)
    if not pg:
        return _no_pg()
    from core.pg_bridge import KNOWLEDGE_TIERS, normalize_tier
    canonical = normalize_tier(tier)
    if canonical not in KNOWLEDGE_TIERS:
        return {"error": f"invalid tier {tier!r} — valid: {KNOWLEDGE_TIERS}"}
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        _executor,
        lambda: pg.promote_knowledge_tier(
            atom_id, tier, app_id, reason, human_attestation=human_attestation
        ),
    )
    if result.get("promoted"):
        try:
            pg.ledger_append("willow", "kb_tier_promotion", {
                "atom_id": atom_id, "tier": canonical, "agent": app_id, "reason": reason,
            })
        except Exception:
            pass
    return result


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def kb_query(
    app_id:            str,
    query:             str,
    limit:             int  = 20,
    include_embedding: bool = False,
    fields:            list = None,
    scope:             str  = "",
    project:           str  = "",
) -> dict:
    """General search across the knowledge graph. Alias for kb_search (keyword mode)."""
    logger.info("[w2] kb_query app_id=%s q=%r", app_id, query)
    return await kb_search(
        app_id=app_id, query=query, limit=limit,
        semantic=False, include_embedding=include_embedding, fields=fields,
        scope=scope, project=project,
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def kb_get(
    app_id:            str,
    id:                str,
    include_embedding: bool = False,
    include_invalid:   bool = False,
    fields:            list = None,
    scope:             str  = "",
    project:           str  = "",
) -> dict:
    """Fetch a single knowledge atom by id. Omits embedding by default to keep payloads small."""
    logger.info("[w2] kb_get app_id=%s id=%s", app_id, id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    lane_scope = _resolve_kb_lane_scope(app_id, scope=scope, project=project)
    atom = await loop.run_in_executor(
        _executor, pg.knowledge_get, id, include_invalid, include_embedding, fields,
        lane_scope,
    )
    return {"atom": atom, "found": bool(atom)}


@mcp.tool()
@sap_gate(write=True)
async def kb_ingest(
    app_id:         str,
    title:          str,
    summary:        str,
    source_type:    str = "mcp",
    source_id:      str = "",
    category:       str = "general",
    domain:         str = "",
    force:          bool = False,
    keywords:       list = None,
    tags:           list = None,
    tier:           str  = "observed",
    confidence:     float = 1.0,
    quality_gate:   bool = False,
    quality_rubric: str  = "",
    sensitivity:    str  = "",
) -> dict:
    """Add a knowledge atom to Willow's Postgres KB.
    Gates on REDUNDANT/CONTRADICTION — returns {blocked:true} if a duplicate or conflict
    is detected. Pass force=true to override the gate and write anyway.
    keywords/tags are stored in content JSONB for retrieval.
    tier: frontier|contested|canonical|superseded (legacy: hypothesis|observed|validated — auto-mapped).
    quality_gate=true: runs summary through the Groq rubric evaluator before ingestion.
      Rewrites content to meet the rubric if it fails (up to 2 iterations).
      quality_rubric: custom rubric; omit to use the default KB quality rubric.
    sensitivity: explicit veto-axis override, open|sensitive (ADR-20260702).
      Omit to inherit the lane default; unknown lanes fail closed to sensitive."""
    logger.info("[w2] kb_ingest app_id=%s title=%r force=%s quality_gate=%s",
                app_id, title, force, quality_gate)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    clean_summary   = _normalize_local_paths(summary)
    clean_source_id = _normalize_local_paths(source_id)
    effective_domain = domain or _MCP_AGENT

    explicit_sensitivity = ""
    if sensitivity:
        from core.canonical_lanes import normalize_sensitivity
        try:
            explicit_sensitivity = normalize_sensitivity(sensitivity) or ""
        except ValueError as se:
            return {"error": str(se)}

    # ── Quality gate: evaluate + refine before touching the KB ────────────────
    quality_result: dict = {}
    if quality_gate:
        try:
            import core.outcomes as _outcomes
            qr = await loop.run_in_executor(
                _executor,
                lambda: _outcomes.refine_content(clean_summary, quality_rubric),
            )
            quality_result = {
                "satisfied":   qr["satisfied"],
                "iterations":  qr["iterations"],
                "explanation": qr["explanation"],
                "refined":     qr["refined"],
            }
            if not qr["satisfied"]:
                return {
                    "blocked":        True,
                    "reason":         "quality_gate",
                    "quality":        quality_result,
                    "hint":           "Content failed the quality rubric after rewriting. "
                                      "Revise manually or pass quality_gate=false to bypass.",
                }
            clean_summary = qr["content"]  # use refined version if rewritten
        except Exception as qe:
            logger.warning("[w2] kb_ingest quality_gate failed: %s", qe)
            quality_result = {"error": str(qe)}

    from core.pg_bridge import normalize_tier

    normalized_tier = normalize_tier(tier)
    content_for_quality = {"source_id": clean_source_id}
    if keywords:
        content_for_quality["keywords"] = keywords
    if tags:
        content_for_quality["tags"] = tags
    if normalized_tier == "canonical":
        try:
            from core.kb_quality import canonical_quality_check

            canonical_quality = canonical_quality_check(
                title=title,
                summary=clean_summary,
                content=content_for_quality,
                source_type=source_type,
                source_id=clean_source_id,
                confidence=confidence,
            )
            quality_result["canonical"] = canonical_quality
            if not canonical_quality["satisfied"]:
                return {
                    "blocked": True,
                    "reason": "canonical_quality_gate",
                    "quality": quality_result,
                    "hint": "Canonical atoms require specific summary, provenance, and sufficient confidence.",
                }
        except Exception as qe:
            logger.warning("[w2] canonical quality gate failed: %s", qe)
            quality_result["canonical"] = {"error": str(qe)}

    def _ingest():
        retired: list[str] = []
        if not force:
            try:
                from sap.core.memory_gate import check_candidate
                from datetime import datetime, timezone
                gate = check_candidate(
                    title=title, summary=clean_summary,
                    domain=effective_domain, store=store, pg=pg,
                    collection=f"{effective_domain}/atoms",
                )
                flags = set(gate.get("flags", []))

                # REDUNDANT: exact duplicate — block.
                if "REDUNDANT" in flags:
                    return {
                        "blocked":        True,
                        "flags":          gate["flags"],
                        "recommendation": gate["recommendation"],
                        "evidence":       gate["evidence"],
                        "hint":           "Pass force=true to override and write anyway.",
                    }

                # CONTRADICTION: new atom supersedes old — retire old, proceed.
                if "CONTRADICTION" in flags:
                    now = datetime.now(timezone.utc)
                    for old_id in gate.get("evidence", {}).get("contradiction_ids", []):
                        try:
                            pg.knowledge_close(old_id, now)
                            retired.append(old_id)
                        except Exception as retire_err:
                            logger.warning("[w2] kb_ingest retire %s failed: %s", old_id, retire_err)

            except Exception as gate_err:
                logger.warning("[w2] memory_gate check failed: %s", gate_err)

        atom_id = pg.ingest_atom(
            title=title, summary=clean_summary,
            source_type=source_type, source_id=clean_source_id,
            category=category, domain=effective_domain or None,
            keywords=keywords or [],
            tags=tags or [],
            tier=normalized_tier,
            confidence=confidence,
            sensitivity=explicit_sensitivity,
        )
        out: dict = {"id": atom_id, "status": "ingested" if atom_id else "failed"}
        if not atom_id:
            out["error"] = getattr(pg, "_last_ingest_error", None)
        if force:
            out["forced"] = True
        if retired:
            out["retired"] = retired
        if quality_result:
            out["quality"] = quality_result
        return out

    result = await loop.run_in_executor(_executor, _ingest)
    if quality_result and "quality" not in result:
        result["quality"] = quality_result
    return result


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def kb_at(
    app_id:  str,
    query:   str,
    at_time: str,
    project: str = "",
    limit:   int = 20,
    scope:   str = "",
) -> dict:
    """Temporal replay: what did Willow know about query at a specific point in time?
    Uses bi-temporal edges — returns atoms valid at that moment.
    at_time: ISO 8601, e.g. '2025-01-15T12:00:00Z'"""
    logger.info("[w2] kb_at app_id=%s q=%r at=%s", app_id, query, at_time)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _at():
        from datetime import datetime as _dt
        at = _dt.fromisoformat(at_time.replace("Z", "+00:00"))
        lane_scope = _resolve_kb_lane_scope(app_id, scope=scope, project=project)
        explicit_project = (project or "").strip() or None
        results = pg.knowledge_at(
            query, at_time=at, project=explicit_project, limit=limit,
            lane_scope=lane_scope,
        )
        return {"results": results, "count": len(results), "at_time": at_time}

    return await loop.run_in_executor(_executor, _at)


# ── Tools — agent_ domain (dispatch + task queue) ────────────────────────────

@mcp.tool()
@sap_gate()
async def agent_route(
    app_id: str,
    message: str,
    session_id: str = "",
    auto_dispatch: bool = False,
) -> dict:
    """Route a message to the most appropriate Willow agent based on content analysis.

    When auto_dispatch=True and oracle confidence >= INTENT_CONFIDENCE_THRESHOLD,
    automatically calls agent_dispatch to the recommended agent.
    Default is advisory-only (auto_dispatch=False).
    """
    logger.info("[w2] agent_route app_id=%s sid=%s auto_dispatch=%s", app_id, session_id, auto_dispatch)
    loop = asyncio.get_running_loop()

    def _route():
        import json as _j
        oracle_ok = False
        try:
            from willow.routing.oracle import route as _routing_oracle, INTENT_CONFIDENCE_THRESHOLD
            result = _routing_oracle(message, session_id=session_id) if message else {
                "routed_to": "willow", "rule_matched": "no-message", "confidence": 0.5, "latency_ms": 0,
            }
            oracle_ok = bool(message)
        except Exception as re:
            result = {
                "routed_to": "willow", "rule_matched": "oracle-unavailable",
                "confidence": 0.5, "latency_ms": 0, "error": str(re),
            }
            INTENT_CONFIDENCE_THRESHOLD = 0.35
        if pg:
            try:
                import hashlib
                import uuid as _u
                with pg.conn.cursor() as cur:
                    if message:
                        ph  = hashlib.sha256(message.encode()).hexdigest()[:16]
                        rid = _u.uuid4().hex[:12]
                        cur.execute(
                            "INSERT INTO routing_decisions (id, prompt_hash, session_id, decision)"
                            " VALUES (%s,%s,%s,%s)",
                            (rid, ph, session_id, _j.dumps(result)),
                        )
                    if not oracle_ok:
                        cur.execute(
                            "INSERT INTO willow.routing_decisions"
                            " (session_id, prompt_snippet, routed_to, rule_matched, confidence, latency_ms)"
                            " VALUES (%s,%s,%s,%s,%s,%s)",
                            (session_id or "", (message or "")[:500],
                             result.get("routed_to") or "willow",
                             result.get("rule_matched") or "—",
                             float(result.get("confidence") or 0.0),
                             int(result.get("latency_ms") or 0)),
                        )
                pg.conn.commit()
            except Exception as pe:
                logger.warning("[w2] agent_route: routing_decisions persist failed: %s", pe)

        # Auto-dispatch if requested and confidence is sufficient
        if auto_dispatch and message and result.get("confidence", 0) >= INTENT_CONFIDENCE_THRESHOLD:
            to = result.get("routed_to", "willow")
            try:
                import uuid as _u2
                did = _u2.uuid4().hex[:8].upper()
                from willow.constants import CHANNEL_DISPATCH
                with PgBridge() as b:
                    b.conn.cursor().execute(
                        "INSERT INTO dispatch_tasks"
                        " (id,to_agent,from_agent,prompt,context_id,card_id,reply_to,depth,status)"
                        " VALUES (%s,%s,%s,%s,'','','',0,'pending')",
                        (did, to, app_id, message),
                    )
                    b.conn.commit()
                try:
                    from sap.core.deliver import grove_send
                    grove_send(CHANNEL_DISPATCH,
                        f"[{did}] {app_id} →auto→ {to}: {message[:120]}", sender=app_id)
                except Exception:
                    pass
                result["auto_dispatched"] = True
                result["dispatch_id"] = did
            except Exception as de:
                logger.warning("[w2] agent_route: auto_dispatch failed: %s", de)
                result["auto_dispatched"] = False

        return result

    return await loop.run_in_executor(_executor, _route)


@mcp.tool()
@sap_gate()
async def agent_dispatch(
    app_id:     str,
    to:         str,
    prompt:     str,
    context_id: str = "",
    card_id:    str = "",
    priority:   str = "normal",
    reply_to:   str = "",
    depth:      int = 0,
) -> dict:
    """Dispatch a task to a target agent. Posts to #dispatch, creates dispatch_tasks record.

    Consumer model — passive queue (intentional):
      Named agents (hanuman, heimdallr, loki, willow) are session-scoped, not daemons.
      They consume dispatch_tasks at session start via inbox polling or Grove notification.
      This means cross-agent dispatch requires human session initiation for named agents.

      For work that must run without human initiation, use agent_task_submit → Kart instead.
      Kart is the autonomous execution plane; named agents are the reasoning plane.
    """
    logger.info("[w2] agent_dispatch app_id=%s to=%s depth=%d", app_id, to, depth)
    loop = asyncio.get_running_loop()

    def _dispatch():
        import uuid
        from willow.constants import DISPATCH_MAX_DEPTH, CHANNEL_DISPATCH, CHANNEL_DISPATCH_VIOLATIONS
        did = uuid.uuid4().hex[:8].upper()
        if depth > DISPATCH_MAX_DEPTH:
            try:
                from sap.core.deliver import grove_send
                grove_send(CHANNEL_DISPATCH_VIOLATIONS,
                    f"HARD STOP: depth {depth} > {DISPATCH_MAX_DEPTH}. dispatch_id={did} from={app_id} to={to}",
                    sender=app_id)
            except Exception:
                pass
            return {"error": "dispatch_depth_exceeded", "dispatch_id": did, "depth": depth}
        try:
            with PgBridge() as b:
                b.conn.cursor().execute(
                    "INSERT INTO dispatch_tasks"
                    " (id,to_agent,from_agent,prompt,context_id,card_id,reply_to,depth,status)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending')",
                    (did, to, app_id, prompt, context_id, card_id, reply_to, depth),
                )
                b.conn.commit()
        except Exception:
            pass
        try:
            from sap.core.deliver import grove_send
            grove_send(CHANNEL_DISPATCH,
                f"[{did}] {app_id} → {to} (depth={depth}): {prompt[:120]}", sender=app_id)
        except Exception:
            pass
        return {"dispatch_id": did, "to": to, "from": app_id, "depth": depth, "status": "dispatched"}

    return await loop.run_in_executor(_executor, _dispatch)


@mcp.tool()
@sap_gate()
async def agent_dispatch_result(
    app_id:      str,
    dispatch_id: str,
    result:      str,
    card_id:     str = "",
    role:        str = "close",
    evidence:    dict = None,
) -> dict:
    """Record the result of a completed dispatch task. Writes LOAM atom, closes dispatch record.

    Evidence-gated completion (slices 2–3, see core/completion_verify.py). The gate
    is default-off (WILLOW_COMPLETION_REQUIRE_EVIDENCE); when off this behaves
    exactly as before, and any `evidence` is recorded advisory-only. When enforcing,
    only SUPERVISED tasks (from_agent != to_agent) are gated:
      - role='report' lets a supervised worker submit evidence without closing
        (status → 'reported'); it does not require VERIFIED.
      - role='close' (default) enforces separation of duties (a worker cannot
        self-close, self_close_rejection) and requires VERIFIED evidence; an
        UNVERIFIED close is rejected 409 and the task is left open.
    Self-managed closes (the common willow self-dispatch path) are never gated.
    Every close/report that carries a verdict is written to the FRANK ledger.
    """
    logger.info("[w2] agent_dispatch_result app_id=%s did=%s role=%s", app_id, dispatch_id, role)
    loop = asyncio.get_running_loop()

    def _result():
        from core import completion_verify as cv

        gate = cv.gate_enabled()

        # Resolve the task once (when gating) — separation of duties and the
        # supervised-only evidence requirement both key off from_agent/to_agent.
        task_row = None
        if gate and role == "close":
            try:
                bt = PgBridge()
                with bt.conn.cursor() as cur:
                    cur.execute(
                        "SELECT to_agent, from_agent FROM dispatch_tasks WHERE id=%s",
                        (dispatch_id,),
                    )
                    row = cur.fetchone()
                bt.conn.close()
                if row:
                    task_row = {"to_agent": row[0], "from_agent": row[1]}
            except Exception:
                task_row = None
            if task_row is not None:
                block = cv.self_close_rejection(app_id, task_row)
                if block is not None:
                    block["dispatch_id"] = dispatch_id
                    return block

        verdict = cv.verify_completion_evidence(evidence) if evidence else None

        # Enforcement is scoped to SUPERVISED closes. Self-managed tasks, and any
        # task that cannot be resolved (DB blip / not found), fail open — they keep
        # the pre-gate behavior so the gate never breaks ordinary self-dispatch.
        supervised = cv.is_supervised(task_row) if task_row else False
        if gate and role == "close" and supervised:
            if verdict is None:
                verdict = {"status": "UNVERIFIED", "reasons": ["no evidence provided"],
                           "checked": {}}
            if verdict["status"] != "VERIFIED":
                _ledger_completion(dispatch_id, app_id, role, "rejected", verdict)
                return {"status": 409,
                        "error": "completion UNVERIFIED — evidence required to close a supervised task",
                        "dispatch_id": dispatch_id, "verdict": verdict}

        new_status = "reported" if (gate and role == "report") else "completed"

        atom_id = None
        try:
            b = PgBridge()
            atom_id = b.ingest_atom(
                title=f"Dispatch result: {dispatch_id}",
                summary=result, source_type="dispatch_result", domain=app_id,
                tier="frontier",
            )
            b.conn.close()
        except Exception:
            pass
        try:
            b2 = PgBridge()
            with b2.conn.cursor() as cur:
                cur.execute(
                    "UPDATE dispatch_tasks SET status=%s,result_atom_id=%s,resolved_at=now()"
                    " WHERE id=%s",
                    (new_status, atom_id, dispatch_id),
                )
            b2.conn.commit()
            b2.conn.close()
        except Exception:
            pass

        if verdict is not None:
            _ledger_completion(dispatch_id, app_id, role, new_status, verdict)

        out = {"dispatch_id": dispatch_id, "atom_id": atom_id, "status": new_status}
        if verdict is not None:
            out["verdict"] = verdict
        return out

    return await loop.run_in_executor(_executor, _result)


def _ledger_completion(dispatch_id: str, app_id: str, role: str, status: str, verdict: dict) -> None:
    """Append a completion-verify provenance entry to the FRANK ledger. Never raises."""
    if not pg:
        return
    try:
        pg.ledger_append("willow", "completion_verify", {
            "dispatch_id": dispatch_id, "app_id": app_id, "role": role,
            "status": status, "verdict": verdict,
        })
    except Exception:
        pass


@mcp.tool()
@sap_gate()
async def agent_task_submit(
    app_id:       str,
    task:         str = "",
    script_body:  str = "",
    script_name:  str = "",
    agent:        str = "kart",
    submitted_by: str = "ganesha",
    allow_net:    bool = False,
    allow_localhost: bool = False,
) -> dict:
    """Queue shell work for Kart (execution plane). Returns task_id immediately.

    Prefer this over agent Bash for ls, git, pytest, pipelines, and scripts.
    Use script_body (not inline task strings) when Python or nested quotes are involved —
    writes {WILLOW_ROOT}/.kart-scripts/kart-*.py and queues python3 <path>.
    script_body must be Python (it always runs via python3); shell goes in task=.

    Set allow_net=True for git push, gh, curl, etc.
    Set allow_localhost=True for loopback-only work (Ollama embeds) without credentials.
    After submit, call kart_task_run(app_id) or wait for kart-worker / Stop kart_poll."""
    logger.info(
        "[w2] agent_task_submit app_id=%s agent=%s allow_net=%s allow_localhost=%s",
        app_id, agent, allow_net, allow_localhost,
    )
    from core.boot_gate import is_booted
    if not is_booted():
        return {
            "error": (
                "Boot sentinel absent for this session. Complete /boot "
                "before submitting Kart tasks — the PreToolUse boot gate "
                "does not fire for MCP tool calls, so this check runs here."
            ),
        }
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    try:
        from willow.fylgja.kart_queue import prepare_task_command
        cmd, script_path = prepare_task_command(task, script_body=script_body, script_name=script_name)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"prepare task: {e}"}

    if allow_net:
        task_text = cmd + "\n# allow_net"
    elif allow_localhost:
        task_text = cmd + "\n# allow_localhost"
    else:
        task_text = cmd

    from core.kart_task_scan import check_kart_task

    blocked = check_kart_task(task_text, script_body=script_body)
    if blocked:
        return blocked

    def _submit():
        task_id = pg.submit_task(task_text, submitted_by=submitted_by or app_id, agent=agent)
        if not task_id:
            return {"error": "failed to submit task"}
        _rl_log_event("task_submit", ref=task_id)
        out = {"task_id": task_id, "status": "pending", "agent": agent, "command": cmd}
        if script_path:
            out["script_path"] = script_path
        return out

    return await loop.run_in_executor(_executor, _submit)


from core.kart_execute import trim_task_result as _trim_task_result


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def agent_task_status(app_id: str, task_id: str) -> dict:
    """Check status of a task in the Postgres tasks table."""
    logger.info("[w2] agent_task_status app_id=%s task_id=%s", app_id, task_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    row = await loop.run_in_executor(_executor, pg.task_status, task_id)
    if row is None:
        return {"error": "not found", "task_id": task_id}
    row = dict(row)
    row["result"] = _trim_task_result(row.get("result"), row.get("status", ""))
    return row


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def agent_task_list(app_id: str, agent: str = "kart", limit: int = 10) -> dict:
    """List pending tasks in the Postgres task queue (read-only; does not claim)."""
    logger.info("[w2] agent_task_list app_id=%s agent=%s", app_id, agent)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    tasks = await loop.run_in_executor(_executor, pg.pending_tasks, agent, limit)
    return {"pending": tasks, "count": len(tasks)}


@mcp.tool()
@sap_gate()
async def kart_task_run(
    app_id: str,
    agent:  str = "kart",
    limit:  int = 5,
) -> dict:
    """Wait for kart-worker, then execute any still-pending tasks in-process (fallback).

    Polls until pending+running clear or KART_POLL_TIMEOUT. If tasks remain pending
    with nothing running, claims and runs them via core/kart_execute (same as stop drain).
    """
    logger.info("[w2] kart_task_run app_id=%s agent=%s limit=%d", app_id, agent, limit)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _reap_exempt_ids() -> list[str]:
        raw = os.environ.get("KART_REAP_EXEMPT_IDS", "")
        return [x.strip() for x in raw.split(",") if x.strip()]

    def _run():
        import time as _time
        from core.kart_execute import drain_claimed_tasks, kart_timeout

        stale_s = int(os.environ.get("KART_STALE_SECONDS", "3600"))
        reaped = pg.reap_stale_tasks(
            max_age_seconds=stale_s, agent=agent, exempt_ids=_reap_exempt_ids()
        )

        timeout = kart_timeout("poll")
        grace = min(2, timeout)
        _time.sleep(grace)
        deadline = _time.monotonic() + timeout
        seen: set = set()
        results = []

        # Snapshot active task IDs at call start so we only report tasks that
        # were pending/running when this call began — not historical completed
        # tasks sitting in Postgres from prior sessions.
        initial_active_ids = {
            r["id"]
            for r in pg.tasks_by_status(
                agent=agent, statuses=["pending", "running"], limit=limit * 4
            )
        }

        while _time.monotonic() < deadline:
            rows = pg.tasks_by_status(agent=agent, limit=limit * 4)
            active = [r for r in rows if r.get("status") in ("pending", "running")]
            done = [
                r
                for r in rows
                if r.get("status") in ("complete", "failed", "completed")
                and r["id"] not in seen
                and r["id"] in initial_active_ids
            ]
            for r in done:
                seen.add(r["id"])
                results.append({
                    "task_id": r["id"],
                    "status": r["status"],
                    "cmd": (r.get("task") or "")[:80],
                    "result": _trim_task_result(r.get("result"), r["status"]),
                })
            if not active:
                break
            _time.sleep(1)

        pending = pg.tasks_by_status(
            agent=agent, statuses=["pending"], limit=limit
        )
        running = pg.tasks_by_status(
            agent=agent, statuses=["running"], limit=1
        )
        if pending and not running:
            batch = pg.claim_kart_tasks(limit=limit, agent=agent)
            for task_id, status, result in drain_claimed_tasks(
                pg, batch, context="poll", log_prefix="kart_task_run"
            ):
                seen.add(task_id)
                row = next((r for r in batch if r["id"] == task_id), {})
                results.append({
                    "task_id": task_id,
                    "status": status,
                    "cmd": (row.get("task") or "")[:80],
                    "result": _trim_task_result(result, status),
                    "executed_by": "fallback",
                })

        out = {"executed": len(results), "results": results}
        if reaped:
            out["reaped_stale"] = reaped
        return out

    return await loop.run_in_executor(_executor, _run)


@mcp.tool()
@sap_gate(write=True)
async def intake_schedule(
    app_id:     str,
    agent:      str = "",
    days:       int = 7,
    limit:      int = 0,
    no_llm:     bool = True,
    all_files:  bool = False,
) -> dict:
    """Queue a promote_intake run as a Kart task. Returns task_id.
    Call kart_task_run() afterwards to execute it, or let Kart poll automatically.
    no_llm=True (default) uses fallback routing; False routes via orin (requires Ollama).
    all_files=True scans every intake JSONL (not just the days window)."""
    logger.info("[w2] intake_schedule app_id=%s agent=%s days=%d", app_id, agent or app_id, days)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _schedule():
        import sys
        target  = agent or app_id
        script  = str(_SAP_ROOT / "scripts" / "promote_intake.py")
        cmd_parts = [sys.executable, script, f"--days={days}", f"--agent={target}"]
        if no_llm:
            cmd_parts.append("--no-llm")
        if all_files:
            cmd_parts.append("--all-files")
        if limit:
            cmd_parts.append(f"--limit={limit}")
        cmd = " ".join(cmd_parts)
        task_id = pg.submit_task(cmd, submitted_by=app_id, agent="kart")
        if not task_id:
            return {"error": "failed to submit task"}
        return {"task_id": task_id, "status": "queued", "cmd": cmd}

    return await loop.run_in_executor(_executor, _schedule)


@mcp.tool()
@sap_gate(write=True)
async def intake_schedule_fleet(
    app_id:     str,
    days:       int = 7,
    limit:      int = 0,
    no_llm:     bool = True,
    all_files:  bool = True,
) -> dict:
    """Queue a fleet-wide promote_intake run as a Kart task (--fleet --all-files)."""
    logger.info("[w2] intake_schedule_fleet app_id=%s days=%d all_files=%s", app_id, days, all_files)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _schedule():
        import sys
        script = str(_SAP_ROOT / "scripts" / "promote_intake.py")
        cmd_parts = [sys.executable, script, "--fleet", f"--days={days}"]
        if no_llm:
            cmd_parts.append("--no-llm")
        if all_files:
            cmd_parts.append("--all-files")
        if limit:
            cmd_parts.append(f"--limit={limit}")
        cmd = " ".join(cmd_parts)
        task_id = pg.submit_task(cmd, submitted_by=app_id, agent="kart")
        if not task_id:
            return {"error": "failed to submit task"}
        return {"task_id": task_id, "status": "queued", "cmd": cmd}

    return await loop.run_in_executor(_executor, _schedule)


# ── Tools — infer_ domain ─────────────────────────────────────────────────────

@mcp.tool()
@sap_gate()
async def infer_chat(app_id: str, agent: str = "willow", message: str = "") -> dict:
    """Chat with a fleet agent persona via provider-agnostic router (Ollama / Gemini / Groq / fleet).

    The IDE model (Claude, Cursor, etc.) is not the agent — `agent` is the fleet identity.
    """
    logger.info("[w2] infer_chat app_id=%s agent=%s", app_id, agent)
    if not message:
        return {"error": "message required"}
    loop    = asyncio.get_running_loop()
    timeout = _TOOL_TIMEOUT_INFERENCE

    def _chat():
        from core.inference_router import chat as router_chat
        system_prompt = _inf.load_persona(agent) or (
            f"You are {agent}, a Willow fleet agent. "
            "You are not the IDE runtime (Claude/Cursor/Gemini). Answer as {agent} only."
        )
        try:
            text, provider = router_chat(system_prompt, message)
            return text, provider
        except Exception as e:
            return f"[{agent}] Inference unavailable: {e}", "none"

    def _log_shadow(actual_provider: str):
        # ADR-20260702 step 3: record the counterfactual rung/engine. infer_chat
        # assembles no KB context, so its taint is genuinely unknown at this call
        # site — logged as 'unknown' (fails closed to local), which is itself the
        # signal motivating the step-5 gateway. Never breaks the inference path.
        if not pg:
            return
        try:
            from willow.routing.shadow import log_shadow
            log_shadow(pg.conn, message, sensitivity="unknown",
                       actual_engine=actual_provider, source="infer_chat")
        except Exception:
            pass

    try:
        response, provider = await asyncio.wait_for(
            loop.run_in_executor(_executor, _chat),
            timeout=timeout,
        )
        await loop.run_in_executor(_executor, _log_shadow, provider)
        return {"agent": agent, "response": response, "provider": provider}
    except asyncio.TimeoutError:
        return {"error": "timeout", "tool": "infer_chat", "timeout_s": timeout}


@mcp.tool()
@sap_gate()
async def infer_imagine(
    app_id:       str,
    prompt:       str,
    output_path:  str = "",
    aspect_ratio: str = "1:1",
) -> dict:
    """Generate an image. Uses OpenRouter (OPENROUTER_API_KEY) with flux-schnell;
    falls back to Novita (NOVITA_API_KEY) if OpenRouter key is absent."""
    logger.info("[w2] infer_imagine app_id=%s", app_id)
    loop = asyncio.get_running_loop()
    from willow.fylgja.willow_home import willow_home
    import json as _json
    creds_path = willow_home() / "secrets" / "credentials.json"
    try:
        creds = _json.loads(creds_path.read_text())
    except Exception:
        creds = {}
    if creds.get("OPENROUTER_API_KEY") or __import__("os").environ.get("OPENROUTER_API_KEY"):
        return await loop.run_in_executor(
            _executor, _inf.imagine_openrouter, prompt, output_path or None, aspect_ratio,
        )
    return await loop.run_in_executor(
        _executor, _inf.imagine_novita, prompt, output_path or None, aspect_ratio,
    )


@mcp.tool()
@sap_gate()
async def infer_speak(app_id: str, text: str, voice: str = "default") -> dict:
    """Text-to-speech via Willow TTS router. Not available in portless mode."""
    return {"status": "not_available", "reason": "TTS not wired in portless mode"}


# ── Tools — fork_ domain ──────────────────────────────────────────────────────

@mcp.tool()
@sap_gate()
async def fork_create(
    app_id:     str,
    title:      str,
    created_by: str,
    topic:      str = "",
    fork_id:    str = "",
) -> dict:
    """Create a new fork — a named, bounded unit of work."""
    logger.info("[w2] fork_create app_id=%s title=%r", app_id, title)
    loop = asyncio.get_running_loop()

    def _create():
        import uuid
        import json as _j
        fid = fork_id or f"FORK-{uuid.uuid4().hex[:8].upper()}"
        with PgBridge() as b:
            b.conn.cursor().execute(
                "INSERT INTO forks (id,title,created_by,topic,status,participants,changes)"
                " VALUES (%s,%s,%s,%s,'open',%s,'[]')",
                (fid, title, created_by, topic, _j.dumps([created_by])),
            )
            b.conn.commit()
        # Snapshot env vars so env_check can diff against them later
        env_snapshot = {k: v for k, v in os.environ.items()
                        if any(k.startswith(p) for p in _ENV_SNAPSHOT_PREFIXES)}
        try:
            store.put(f"{app_id}/forks/{fid}/env", env_snapshot, record_id="snapshot")
        except Exception:
            pass
        return {"fork_id": fid, "status": "open"}

    return await loop.run_in_executor(_executor, _create)


@mcp.tool()
@sap_gate()
async def fork_join(app_id: str, fork_id: str, component: str) -> dict:
    """Join an existing fork as a participant component."""
    logger.info("[w2] fork_join app_id=%s fork=%s component=%s", app_id, fork_id, component)
    loop = asyncio.get_running_loop()

    def _join():
        import json as _j
        with PgBridge() as b:
            cur = b.conn.cursor()
            cur.execute("SELECT participants FROM forks WHERE id=%s", (fork_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"fork {fork_id} not found"}
            parts = row[0] if isinstance(row[0], list) else _j.loads(row[0])
            if component not in parts:
                parts.append(component)
            cur.execute("UPDATE forks SET participants=%s WHERE id=%s", (_j.dumps(parts), fork_id))
            b.conn.commit()
        return {"fork_id": fork_id, "participants": parts}

    return await loop.run_in_executor(_executor, _join)


@mcp.tool()
@sap_gate()
async def fork_log(
    app_id:      str,
    fork_id:     str,
    component:   str,
    type:        str,
    ref:         str,
    description: str = "",
) -> dict:
    """Log a change to an open fork."""
    logger.info("[w2] fork_log app_id=%s fork=%s ref=%s", app_id, fork_id, ref)
    loop = asyncio.get_running_loop()

    def _log():
        import json as _j
        from datetime import datetime as _dt, timezone as _tz
        with PgBridge() as b:
            cur = b.conn.cursor()
            cur.execute("SELECT changes FROM forks WHERE id=%s", (fork_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"fork {fork_id} not found"}
            changes = row[0] if isinstance(row[0], list) else _j.loads(row[0])
            changes.append({
                "component": component, "type": type, "ref": ref,
                "description": description,
                "logged_at": _dt.now(_tz.utc).isoformat(),
            })
            cur.execute("UPDATE forks SET changes=%s WHERE id=%s", (_j.dumps(changes), fork_id))
            b.conn.commit()
        return {"logged": True, "change_count": len(changes)}

    return await loop.run_in_executor(_executor, _log)


@mcp.tool(annotations={"destructiveHint": True})
@sap_gate()
async def fork_merge(app_id: str, fork_id: str, outcome_note: str = "") -> dict:
    """Merge an open fork — promotes KB atoms to permanent."""
    logger.info("[w2] fork_merge app_id=%s fork=%s", app_id, fork_id)
    loop = asyncio.get_running_loop()

    def _merge():
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc).isoformat()
        with PgBridge() as b:
            cur = b.conn.cursor()
            cur.execute(
                "UPDATE forks SET status='merged',merged_at=%s,outcome_note=%s"
                " WHERE id=%s AND status='open'",
                (now, outcome_note, fork_id),
            )
            b.conn.commit()
            if cur.rowcount == 0:
                return {"merged": False, "reason": "not found or not open"}
            cur.execute("UPDATE knowledge SET fork_id=NULL WHERE fork_id=%s", (fork_id,))
            b.conn.commit()
            return {"merged": True, "promoted_count": cur.rowcount}

    return await loop.run_in_executor(_executor, _merge)


@mcp.tool(annotations={"destructiveHint": True})
@sap_gate()
async def fork_delete(app_id: str, fork_id: str, reason: str = "") -> dict:
    """Delete an open fork — archives KB atoms."""
    logger.info("[w2] fork_delete app_id=%s fork=%s", app_id, fork_id)
    loop = asyncio.get_running_loop()

    def _delete():
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc).isoformat()
        with PgBridge() as b:
            cur = b.conn.cursor()
            cur.execute(
                "UPDATE forks SET status='deleted',deleted_at=%s,outcome_note=%s"
                " WHERE id=%s AND status='open'",
                (now, reason, fork_id),
            )
            b.conn.commit()
            if cur.rowcount == 0:
                return {"deleted": False, "reason": "not found or not open"}
            cur.execute(
                "UPDATE knowledge SET invalid_at=now() WHERE fork_id=%s AND invalid_at IS NULL",
                (fork_id,),
            )
            b.conn.commit()
            return {"deleted": True, "archived_count": cur.rowcount}

    return await loop.run_in_executor(_executor, _delete)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fork_status(app_id: str, fork_id: str) -> dict:
    """Get the full status of a fork."""
    logger.info("[w2] fork_status app_id=%s fork=%s", app_id, fork_id)
    loop = asyncio.get_running_loop()

    def _status():
        import json as _j
        with PgBridge() as b:
            cur = b.conn.cursor()
            cur.execute(
                "SELECT id,title,created_by,topic,status,participants,changes,"
                "created_at,merged_at,deleted_at,outcome_note FROM forks WHERE id=%s",
                (fork_id,),
            )
            row = cur.fetchone()
        if not row:
            return {"error": f"fork {fork_id} not found"}
        return {
            "fork_id":      row[0], "title":        row[1], "created_by":   row[2],
            "topic":        row[3], "status":        row[4],
            "participants": row[5] if isinstance(row[5], list) else _j.loads(row[5]),
            "changes":      row[6] if isinstance(row[6], list) else _j.loads(row[6]),
            "created_at":   str(row[7]),
            "merged_at":    str(row[8]) if row[8] else None,
            "deleted_at":   str(row[9]) if row[9] else None,
            "outcome_note": row[10],
        }

    return await loop.run_in_executor(_executor, _status)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fork_list(app_id: str, status: str = "open") -> list:
    """List forks by status (open | merged | deleted)."""
    logger.info("[w2] fork_list app_id=%s status=%s", app_id, status)
    loop = asyncio.get_running_loop()

    def _list():
        with PgBridge() as b:
            cur = b.conn.cursor()
            cur.execute(
                "SELECT id,title,created_at,created_by,topic,"
                "jsonb_array_length(participants),jsonb_array_length(changes)"
                " FROM forks WHERE status=%s ORDER BY created_at DESC LIMIT 100",
                (status,),
            )
            return [
                {"fork_id": r[0], "title": r[1], "created_at": str(r[2]),
                 "created_by": r[3], "topic": r[4],
                 "participant_count": r[5], "change_count": r[6]}
                for r in cur.fetchall()
            ]

    return await loop.run_in_executor(_executor, _list)


# ── Tools — skill_ domain ─────────────────────────────────────────────────────

@mcp.tool()
@sap_gate(write=True)
async def skill_put(
    app_id:          str,
    name:            str,
    domain:          str,
    content:         str,
    trigger:         str,
    auto_load:       bool = True,
    model_agnostic:  bool = True,
    risk:            str = "low",
) -> dict:
    """Store or update a Willow skill in the registry.
    risk: 'low' | 'medium' | 'high' — gates needs_scrutiny confirmation on load."""
    logger.info("[w2] skill_put app_id=%s name=%s domain=%s risk=%s", app_id, name, domain, risk)
    loop = asyncio.get_running_loop()

    def _put():
        from willow.skills import skill_put as _skill_put
        skill_id = _skill_put(
            store, name=name, domain=domain, content=content, trigger=trigger,
            auto_load=auto_load, model_agnostic=model_agnostic, risk=risk,
        )
        return {"skill_id": skill_id}

    return await loop.run_in_executor(_executor, _put)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def skill_load(app_id: str, context: str) -> dict:
    """Load relevant skills for the current context.
    Returns up to 3 auto-loadable skills matched to the context."""
    logger.info("[w2] skill_load app_id=%s ctx=%r", app_id, context)
    loop = asyncio.get_running_loop()

    def _load():
        from willow.skills import skill_load as _skill_load
        skills = _skill_load(store, context=context)
        return {"skills": skills}

    return await loop.run_in_executor(_executor, _load)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def skill_list(app_id: str, domain: str = "") -> dict:
    """List all skills in the registry, optionally filtered by domain.
    domain: session | task | fork | grove | system"""
    logger.info("[w2] skill_list app_id=%s domain=%s", app_id, domain)
    loop = asyncio.get_running_loop()

    def _list():
        from willow.skills import skill_list as _skill_list
        skills = _skill_list(store, domain=domain or None)
        return {"skills": skills}

    return await loop.run_in_executor(_executor, _list)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def skill_mastery(app_id: str, skill_id: str = "", weakest: int = 0) -> dict:
    """Bayesian-Knowledge-Tracing mastery for skills (read-only).
    skill_id: one skill → mastery, p_next_correct, opportunities, mastered.
    weakest=N: the N lowest-mastery skills (drill list)."""
    logger.info("[w2] skill_mastery app_id=%s skill_id=%r weakest=%d", app_id, skill_id, weakest)
    loop = asyncio.get_running_loop()

    def _mastery():
        from core import skill_mastery as _sm
        if weakest and weakest > 0:
            return {"weakest": _sm.weakest(weakest)}
        if not skill_id:
            return {"error": "provide skill_id or weakest=N"}
        rec = _sm.mastery(skill_id)
        if rec is None:
            return {"error": "no mastery record", "skill_id": skill_id}
        return {
            "skill_id":       skill_id,
            "mastery":        rec.get("p_known"),
            "p_next_correct": rec.get("p_next_correct"),
            "opportunities":  rec.get("opportunities"),
            "mastered":       rec.get("mastered"),
        }

    return await loop.run_in_executor(_executor, _mastery)


# ── Tools — mem_ domain (Jeles / Binder / Ratify) ────────────────────────────

@mcp.tool()
@sap_gate()
async def mem_jeles_register(
    app_id:      str,
    agent:       str,
    jsonl_path:  str,
    session_id:  str,
    cwd:         str = "",
    turn_count:  int = 0,
    file_size:   int = 0,
) -> dict:
    """Jeles: Register a raw JSONL in an agent's schema. Returns BASE 17 ID."""
    logger.info("[w2] mem_jeles_register app_id=%s agent=%s sid=%s", app_id, agent, session_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.jeles_register_jsonl,
        agent, jsonl_path, session_id, cwd or None, turn_count, file_size,
    )


@mcp.tool()
@sap_gate(write=True)
async def mem_jeles_extract(
    app_id:    str,
    agent:     str,
    jsonl_id:  str,
    content:   str,
    title:     str  = "",
    domain:    str  = "meta",
    depth:     int  = 1,
    certainty: float = 0.98,
) -> dict:
    """Jeles: Extract an atom from a registered JSONL. Certainty must exceed 0.95.
    Runs the 5-condition boundary-theorem gate (ATTRACTOR, PROVENANCE, FIDELITY_GATE,
    PATTERN_INSTANCE, TEMPORAL_PERSISTENCE) via local Ollama before any DB write.
    Returns {blocked:true, failed_conditions:[...], domain_verdict:...} on gate failure."""
    logger.info("[w2] mem_jeles_extract app_id=%s agent=%s jsonl=%s", app_id, agent, jsonl_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.jeles_extract_atom,
        agent, jsonl_id, content, domain, depth, certainty, title or None,
    )


@mcp.tool()
@sap_gate()
async def mem_jeles_web_search(
    app_id:   str,
    query:    str,
    sources:  list = [],
    limit:    int  = 3,
) -> dict:
    """Jeles: Search trusted, citable sources (LOC, arXiv, PubMed, Smithsonian, Europeana, NASA, Crossref, Open Library, and more — 64 registered sources across 36 subject domains). Results carry full source attribution for academic citation. Pass sources=[] to auto-route to the ~6 sources whose domain best matches the query (semantic routing over pre-built domain centroids), or name specific source IDs to override routing entirely. Returns both a per-source `results` dict and a cross-source `ranked` list (RRF-fused lexical + semantic rerank). Wikipedia is opt-in only (general reference, not academic): pass sources=["wikipedia"] to include it."""
    logger.info("[w2] mem_jeles_web_search app_id=%s query=%r sources=%s", app_id, query, sources or "all")
    from core.jeles_sources import search as jeles_search
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, jeles_search,
        query, sources or None, limit,
    )


@mcp.tool()
@sap_gate()
async def willow_web_search(
    app_id:           str,
    query:            str,
    max_results:      int  = 8,
    trusted_only:     bool = False,
    include_handoffs: bool = False,
) -> dict:
    """Open web search via DuckDuckGo HTML (no API key required). Returns title, url, snippet,
    source, and hostname for each result. Use for current events, tech news, personnel moves,
    and any query that needs the live open web rather than institutional archives.
    trusted_only: filter results to verified institutional domain suffixes.
    include_handoffs: prepend OpenStreetMap/Google Maps links for navigational queries."""
    logger.info("[w2] willow_web_search app_id=%s query=%r max=%d trusted=%s", app_id, query, max_results, trusted_only)
    from core.web_search import search_web
    loop = asyncio.get_running_loop()
    hits = await loop.run_in_executor(
        _executor, lambda: search_web(query, max_results=max_results, trusted_only=trusted_only, include_handoffs=include_handoffs)
    )
    return {"query": query, "results": hits, "count": len(hits)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_web_fetch(
    app_id: str,
    url: str,
    wrap: bool = True,
    max_bytes: int = 512_000,
) -> dict:
    """Fetch a URL through Willow external-guard (not native WebFetch).

    Returns markdown-friendly text with sandwich defense when wrap=True.
    Blocks private/loopback hosts. Use willow_web_search to discover URLs first."""
    logger.info("[w2] willow_web_fetch app_id=%s url=%r", app_id, url[:120])
    from core.web_fetch import fetch_url

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: fetch_url(url, wrap=wrap, max_bytes=max_bytes),
    )


@mcp.tool()
@sap_gate()
async def source_trail_verify(
    app_id:  str,
    text:    str,
    sources: list = [],
) -> dict:
    """source-trail: Extract verifiable factual claims from text and check each
    against trusted sources. Two tiers: academic (Jeles — 29 institutions) and
    press (Psychiatric Times, trade sources). Returns {claims, total, matched}
    where each claim carries {claim, matched, title, url, date, source, tier, confidence}."""
    logger.info("[w2] source_trail_verify app_id=%s text_len=%d", app_id, len(text))
    from core.source_trail import verify_text
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, verify_text,
        text, sources or None, 2,
    )


@mcp.tool()
@sap_gate()
async def mem_jeles_ask(
    app_id:   str,
    question: str,
    sources:  list = [],
    limit:    int  = 2,
    perspectives: int = 0,
    verify: bool = True,
) -> dict:
    """Jeles: Answer a natural language question. Checks local corpus first (jeles_atoms);
    falls back to trusted institutional sources (LOC, arXiv, PubMed, etc.) on a corpus miss.
    Live-source results are auto-promoted into the corpus through the gate check.
    Auto-routes to relevant source groups. Pass sources=[] to auto-route,
    or name specific source IDs to override. limit=results per source (default 2).
    perspectives>=2 enables multi-perspective mode: routes to that many deliberately
    diverse domain lenses (e.g. scientific + philosophical) and synthesises an answer
    that contrasts what they agree and disagree on. Default 0 = single-answer mode.
    verify defaults to true: a per-claim cross-source check runs automatically, tagging
    each atomic claim in the answer corroborated (>=2 distinct institutions), single_source,
    or unsupported, returned under a 'verification' key with a summary count. Pass
    verify=false to skip it for a faster/cheaper answer when verification isn't needed."""
    logger.info("[w2] mem_jeles_ask app_id=%s question=%r sources=%s perspectives=%s verify=%s",
                app_id, question[:80], sources or "auto", perspectives, verify)
    from core.jeles_sources import (
        search as jeles_search, route_sources_semantic, route_perspectives_semantic,
        question_to_query, question_to_intent,
    )
    from core.jeles_verify import verify_claims
    from core.llm_edge import respond as llm_respond

    loop = asyncio.get_running_loop()

    # Multi-perspective mode: route to deliberately diverse domains and contrast them.
    # Bypasses corpus-first (we want live, lens-diverse retrieval). Honoured only when
    # sources are auto-routed — an explicit `sources` override stays single-answer.
    if perspectives >= 2 and not sources:
        p_intent = await loop.run_in_executor(_executor, question_to_intent, question)
        p_query  = question_to_query(p_intent)
        groups   = await loop.run_in_executor(
            _executor, route_perspectives_semantic, p_intent, perspectives,
        )
        logger.info("[w2] mem_jeles_ask multi-perspective intent=%r groups=%s",
                    p_intent[:80], [g[0] for g in groups])
        p_citations:   list = []
        p_promote:     list = []
        p_blocks:      list = []
        p_used:        list = []
        p_idx = 1
        per_budget = max(700, 2400 // max(1, len(groups)))
        for domain, src_ids in groups:
            if not src_ids:
                continue
            raw = await loop.run_in_executor(_executor, jeles_search, p_query, src_ids, limit)
            lines:  list = []
            budget = per_budget
            for source_id, hits in raw.get("results", {}).items():
                for hit in hits:
                    title   = (hit.get("title")   or "").strip()
                    snippet = (hit.get("snippet") or "").strip()
                    if not (title or snippet):
                        continue
                    url  = hit.get("url", "")
                    inst = hit.get("institution", source_id)
                    date = hit.get("date", "")
                    p_citations.append({"n": p_idx, "title": title, "url": url,
                                        "source": inst, "date": date, "perspective": domain})
                    line = f"[{p_idx}] {title}" + (f": {snippet}" if snippet else "")
                    lines.append(line[:400])
                    p_promote.append({
                        "title":   title,
                        "content": f"Source: {inst}\nDate: {date}\nURL: {url}\n\n{snippet}",
                        "domain":  source_id,
                    })
                    budget -= len(line)
                    p_idx  += 1
                    if budget <= 0:
                        break
                if budget <= 0:
                    break
            if lines:
                p_used.append(domain)
                p_blocks.append(f"### Perspective: {domain}\n" + "\n".join(lines))

        if not p_blocks:
            return {
                "answer": "No results found in trusted sources for this query.",
                "citations": [], "sources_used": [g[0] for g in groups],
                "question": question, "total_results": 0, "multi_perspective": True,
            }

        p_system = (
            "You are Jeles, a trusted librarian. You are given source excerpts grouped "
            "under several PERSPECTIVES (different domains/framings of the same question). "
            "Write a synthesis that: (1) states what the perspectives AGREE on; "
            "(2) explicitly surfaces where they DIFFER, contradict, or merely emphasise "
            "different things — attribute each framing to its perspective by name. "
            "Cite every fact with its number in brackets, e.g. [1]. Use ONLY the excerpts "
            "below; never use outside knowledge. If the excerpts do not address the "
            "question, say exactly: 'The trusted sources do not contain this answer.'"
        )
        try:
            p_answer = await loop.run_in_executor(
                _executor, llm_respond, p_system, [],
                f"Question: {question}\n\n" + "\n\n".join(p_blocks),
            )
        except Exception as e:
            p_answer = f"(synthesis unavailable: {e})"

        promoted = 0
        if pg and p_promote:
            def _promote_perspectives():
                count = 0
                for item in p_promote:
                    try:
                        result = pg.jeles_extract_atom(
                            agent=app_id, jsonl_id=f"live-promote-{app_id}",
                            content=item["content"], domain=item["domain"], title=item["title"],
                        )
                        if result.get("id"):
                            count += 1
                    except Exception:
                        pass
                return count
            try:
                promoted = await loop.run_in_executor(_executor, _promote_perspectives)
            except Exception:
                promoted = 0

        p_result = {
            "answer":            p_answer,
            "citations":         p_citations,
            "perspectives_used": p_used,
            "sources_used":      [g[0] for g in groups],
            "question":          question,
            "total_results":     len(p_citations),
            "multi_perspective": True,
            "promoted":          promoted,
        }
        if verify:
            p_result["verification"] = await loop.run_in_executor(
                _executor, verify_claims, p_answer, "\n\n".join(p_blocks), p_citations, llm_respond,
            )
        return p_result

    # Step 0: corpus-first lookup — return early if local jeles_atoms cover the question
    _CORPUS_THRESHOLD = 0.42
    _CORPUS_MIN_HITS  = 2
    if pg:
        try:
            corpus_hits = await loop.run_in_executor(
                _executor, pg.search_jeles_semantic, question, 5,
            )
            strong = [h for h in corpus_hits if h.get("distance", 1.0) < _CORPUS_THRESHOLD]
            if len(strong) >= _CORPUS_MIN_HITS:
                logger.info("[w2] mem_jeles_ask corpus HIT (%d strong) — skipping live sources", len(strong))
                c_citations: list = []
                c_snippets:  list = []
                c_budget = 1500
                for i, h in enumerate(strong, 1):
                    t = (h.get("title")   or "").strip()
                    c = (h.get("content") or "").strip()
                    d = h.get("domain", "corpus")
                    c_citations.append({"n": i, "title": t, "source": d, "date": ""})
                    line = f"[{i}] {t}" + (f": {c[:300]}" if c else "")
                    c_snippets.append(line[:400])
                    c_budget -= len(line)
                    if c_budget <= 0:
                        break
                c_system = (
                    "You are Jeles, a trusted librarian. Answer using ONLY the numbered source "
                    "excerpts below. Cite each fact with its number in brackets, e.g. [1]. "
                    "2-6 sentences or a short bulleted list. "
                    "NEVER use outside knowledge — if the excerpts do not contain the answer, say "
                    "exactly: 'The trusted sources do not contain this answer.'"
                )
                try:
                    c_answer = await loop.run_in_executor(
                        _executor, llm_respond,
                        c_system, [], f"Question: {question}\n\nSources:\n" + "\n\n".join(c_snippets),
                    )
                except Exception as e:
                    c_answer = f"(synthesis unavailable: {e})"
                c_result = {
                    "answer":        c_answer,
                    "citations":     c_citations,
                    "sources_used":  ["corpus"],
                    "question":      question,
                    "total_results": len(strong),
                    "corpus_hit":    True,
                }
                if verify:
                    c_result["verification"] = await loop.run_in_executor(
                        _executor, verify_claims, c_answer, "\n\n".join(c_snippets), c_citations, llm_respond,
                    )
                return c_result
        except Exception as _corpus_err:
            logger.warning("[w2] mem_jeles_ask corpus lookup failed (%s) — falling through to live sources", _corpus_err)

    # Step 1: extract factual intent (handles trivia framing)
    intent = await loop.run_in_executor(_executor, question_to_intent, question)

    # Step 2: route on intent (semantic embedding-based)
    if sources:
        active_sources = list(sources)
    else:
        active_sources = await loop.run_in_executor(_executor, route_sources_semantic, intent)

    # Step 3: clean search terms from intent
    search_query = question_to_query(intent)
    logger.info("[w2] mem_jeles_ask intent=%r route=%s", intent[:80], active_sources)

    raw = await loop.run_in_executor(_executor, jeles_search, search_query, active_sources, limit)
    results_by_source = raw.get("results", {})
    total = raw.get("total", 0)

    if not total:
        return {
            "answer": "No results found in trusted sources for this query.",
            "citations": [],
            "sources_used": active_sources,
            "question": question,
            "total_results": 0,
        }

    # Build citation list + snippet block within token budget
    citations:     list = []
    snippet_lines: list = []
    promote_queue: list = []
    budget = 1500
    idx = 1
    for source_id, hits in results_by_source.items():
        for hit in hits:
            title   = (hit.get("title")   or "").strip()
            snippet = (hit.get("snippet") or "").strip()
            url     = hit.get("url", "")
            inst    = hit.get("institution", source_id)
            date    = hit.get("date", "")
            citations.append({"n": idx, "title": title, "url": url, "source": inst, "date": date})
            line = f"[{idx}] {title}" + (f": {snippet}" if snippet else "")
            snippet_lines.append(line[:400])
            budget -= len(line)
            if title or snippet:
                promote_queue.append({
                    "title":   title,
                    "content": f"Source: {inst}\nDate: {date}\nURL: {url}\n\n{snippet}",
                    "domain":  source_id,
                })
            idx += 1
            if budget <= 0:
                break
        if budget <= 0:
            break

    snippet_block = "\n\n".join(snippet_lines)
    system = (
        "You are Jeles, a trusted librarian. Answer using ONLY the numbered source "
        "excerpts below. Cite each fact with its number in brackets, e.g. [1]. "
        "For list questions (albums, works, titles), enumerate ALL items found across "
        "all sources — do not stop after one. 2-6 sentences or a short bulleted list. "
        "NEVER use outside knowledge — if the excerpts do not contain the answer, say "
        "exactly: 'The trusted sources do not contain this answer.'"
    )
    try:
        answer = await loop.run_in_executor(
            _executor, llm_respond,
            system, [], f"Question: {question}\n\nSources:\n{snippet_block}",
        )
    except Exception as e:
        answer = f"(synthesis unavailable: {e})"

    # Promote live-source results into corpus through gate check
    promoted = 0
    if pg and promote_queue:
        def _promote_all():
            count = 0
            for item in promote_queue:
                try:
                    result = pg.jeles_extract_atom(
                        agent=app_id,
                        jsonl_id=f"live-promote-{app_id}",
                        content=item["content"],
                        domain=item["domain"],
                        title=item["title"],
                    )
                    if result.get("id"):
                        count += 1
                except Exception:
                    pass
            return count
        try:
            promoted = await loop.run_in_executor(_executor, _promote_all)
            logger.info("[w2] mem_jeles_ask promoted %d atoms to corpus", promoted)
        except Exception as _promo_err:
            logger.warning("[w2] mem_jeles_ask promotion failed: %s", _promo_err)

    result = {
        "answer":        answer,
        "citations":     citations,
        "sources_used":  active_sources,
        "question":      question,
        "total_results": total,
        "corpus_hit":    False,
        "promoted":      promoted,
    }
    if verify:
        result["verification"] = await loop.run_in_executor(
            _executor, verify_claims, answer, snippet_block, citations, llm_respond,
        )
    return result


@mcp.tool()
@sap_gate()
async def mem_jeles_build_centroids(
    app_id: str,
    force:  bool = False,
) -> dict:
    """Build (or rebuild) Jeles domain centroid embeddings using nomic-embed-text.
    Centroids cached at ~/.willow/jeles_centroids.json and used by mem_jeles_ask
    for semantic routing. Takes ~30-60s on first build. Pass force=true to rebuild."""
    from core.jeles_sources import build_centroids, _DOMAIN_SEEDS
    loop = asyncio.get_running_loop()
    centroids = await loop.run_in_executor(_executor, build_centroids, force)
    return {
        "status": "built" if centroids else "failed",
        "domains": list(centroids.keys()),
        "domain_count": len(centroids),
        "seed_count": sum(len(v) for v in _DOMAIN_SEEDS.values()),
    }


@mcp.tool()
@sap_gate()
async def mem_jeles_search(
    app_id:   str,
    query:    str,
    limit:    int = 10,
    days_ago: int = 0,
) -> dict:
    """Jeles: Semantic search over extracted jeles_atoms. Returns ranked results."""
    logger.info("[w2] mem_jeles_search app_id=%s query=%r limit=%d", app_id, query, limit)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        _executor, pg.search_jeles_semantic,
        query, limit, days_ago or None,
    )
    return {"results": results, "total": len(results)}


@mcp.tool()
@sap_gate()
async def mem_jeles_invalidate(
    app_id:  str,
    atom_id: str,
    reason:  str = "",
) -> dict:
    """Jeles: Invalidate a jeles_atom by ID. Sets invalid_at=now() — atom is excluded from future searches."""
    logger.info("[w2] mem_jeles_invalidate app_id=%s atom_id=%s", app_id, atom_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.jeles_invalidate_atom, atom_id, reason,
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def mem_jeles_get(app_id: str, atom_id: str) -> dict:
    """Jeles: Fetch a single jeles_atom by ID."""
    logger.info("[w2] mem_jeles_get app_id=%s atom_id=%s", app_id, atom_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    atom = await loop.run_in_executor(_executor, pg.jeles_atom_get, atom_id)
    if atom is None:
        return {"error": "not found", "id": atom_id}
    return atom


@mcp.tool()
@sap_gate()
async def mem_binder_file(
    app_id:    str,
    agent:     str,
    jsonl_id:  str,
    dest_path: str,
) -> dict:
    """Binder: Copy JSONL to agent's .tmp/ folder, update status to filed_tmp."""
    logger.info("[w2] mem_binder_file app_id=%s agent=%s jsonl=%s", app_id, agent, jsonl_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, pg.binder_file, agent, jsonl_id, dest_path)


@mcp.tool()
@sap_gate()
async def mem_binder_edge(
    app_id:      str,
    agent:       str,
    source_atom: str,
    target_atom: str,
    edge_type:   str,
) -> dict:
    """Binder: Propose an edge discovered while filing. Status='tmp' until ratified."""
    logger.info("[w2] mem_binder_edge app_id=%s agent=%s %s→%s", app_id, agent, source_atom, target_atom)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.binder_propose_edge, agent, source_atom, target_atom, edge_type,
    )


@mcp.tool()
@sap_gate()
async def mem_ratify(
    app_id:     str,
    agent:      str,
    jsonl_id:   str,
    approve:    bool = True,
    cache_path: str  = "",
) -> dict:
    """Ratify or reject a JSONL and all its atoms/edges.
    approve=True promotes .tmp/ to cache/. approve=False clears .tmp/."""
    logger.info("[w2] mem_ratify app_id=%s agent=%s jsonl=%s approve=%s", app_id, agent, jsonl_id, approve)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.ratify, agent, jsonl_id, approve, cache_path or None,
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def mem_ratify_list(app_id: str, agent: str = "", limit: int = 50) -> dict:
    """List ratification records, optionally filtered by agent."""
    logger.info("[w2] mem_ratify_list app_id=%s agent=%s", app_id, agent)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(
        _executor, pg.ratifications_list, agent or None, limit,
    )
    return {"ratifications": rows, "count": len(rows)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def mem_binder_list_files(app_id: str, agent: str = "", limit: int = 50) -> dict:
    """Binder: List filed JSONL records, optionally filtered by agent."""
    logger.info("[w2] mem_binder_list_files app_id=%s agent=%s", app_id, agent)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(
        _executor, pg.binder_files_list, agent or None, limit,
    )
    return {"files": rows, "count": len(rows)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def mem_binder_list_edges(
    app_id: str,
    agent:  str = "",
    status: str = "",
    limit:  int = 50,
) -> dict:
    """Binder: List proposed edges, optionally filtered by agent or status (proposed/approved/rejected)."""
    logger.info("[w2] mem_binder_list_edges app_id=%s agent=%s status=%s", app_id, agent, status)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(
        _executor, pg.binder_edges_list, agent or None, status or None, limit,
    )
    return {"edges": rows, "count": len(rows)}


@mcp.tool()
@sap_gate(write=True)
async def mem_binder_edge_update(
    app_id:  str,
    edge_id: str,
    status:  str,
) -> dict:
    """Binder: Update the status of a proposed edge (proposed → approved | rejected)."""
    logger.info("[w2] mem_binder_edge_update app_id=%s edge=%s status=%s", app_id, edge_id, status)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.binder_edge_update_status, edge_id, status,
    )


@mcp.tool()
@sap_gate(write=True)
async def intake_write(
    app_id:     str,
    content:    str,
    source:     str,
    tier:       str   = "observed",
    confidence: float = 0.80,
    keywords:   list  = None,
    tags:       list  = None,
    title:      str   = "",
    namespace:  str   = "",
    domain:     str   = "",
    category:   str   = "",
) -> dict:
    """Write one annotated record to the unified intake layer.
    promote_intake.py routes it to the right KB tier (jeles_atoms / knowledge / opus / binder_queue).
    tier: frontier|contested|canonical|superseded (legacy: observed|fetched|verified|ratified — auto-mapped)
    confidence: 0.0-1.0 — source confidence in this record."""
    logger.info("[w2] intake_write app_id=%s source=%s tier=%s conf=%.2f", app_id, source, tier, confidence)
    loop = asyncio.get_running_loop()

    def _write():
        from core.intake import write as intake_write_fn
        extra: dict = {}
        if domain:
            extra["domain"] = domain
        if category:
            extra["category"] = category
        rid = intake_write_fn(
            content=content,
            source=source,
            agent=app_id,
            tier=tier,
            confidence=confidence,
            keywords=list(keywords) if keywords else [],
            tags=list(tags) if tags else [],
            title=title,
            namespace=namespace or app_id,
            extra=extra or None,
        )
        return {"id": rid, "status": "queued", "tier": tier, "confidence": confidence}

    return await loop.run_in_executor(_executor, _write)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def intake_list(
    app_id: str,
    agent:  str = "",
    days:   int = 7,
) -> dict:
    """List pending (not yet promoted) intake records for an agent.
    agent: defaults to app_id. days: look-back window (default 7)."""
    logger.info("[w2] intake_list app_id=%s agent=%s days=%d", app_id, agent or app_id, days)
    loop = asyncio.get_running_loop()

    def _list():
        from core.intake import read_pending
        target = agent or app_id
        records = read_pending(target, days=days)
        return {"records": records, "count": len(records), "agent": target}

    return await loop.run_in_executor(_executor, _list)


@mcp.tool()
@sap_gate(write=True)
async def intake_promote(
    app_id:     str,
    agent:      str = "",
    days:       int = 7,
    limit:      int = 0,
    no_llm:     bool = True,
    all_files:  bool = False,
) -> dict:
    """Run the fallback-routing promote pass on pending intake records.
    Routes each record to jeles_atoms / knowledge / opus / binder_queue based on
    tier + confidence. no_llm=True (default) uses deterministic routing only.
    all_files=True scans every intake JSONL (not just the days window)."""
    logger.info("[w2] intake_promote app_id=%s agent=%s days=%d limit=%d", app_id, agent or app_id, days, limit)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _promote():
        from core.intake_promote import promote_agent
        return promote_agent(
            pg, agent or app_id,
            days=days, all_files=all_files, no_llm=no_llm, limit=limit,
        )

    return await loop.run_in_executor(_executor, _promote)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def mem_check(
    app_id:     str,
    title:      str,
    summary:    str,
    domain:     str = "",
    collection: str = "",
) -> dict:
    """Check a knowledge candidate against REDUNDANT/CONTRADICTION gates before ingesting."""
    logger.info("[w2] mem_check app_id=%s title=%r", app_id, title)
    loop = asyncio.get_running_loop()

    def _check():
        from sap.core.memory_gate import check_candidate
        effective_domain = domain or _MCP_AGENT
        return check_candidate(
            title=title, summary=summary,
            domain=effective_domain, store=store, pg=pg,
            collection=collection or f"{effective_domain}/atoms",
        )

    try:
        return await asyncio.wait_for(loop.run_in_executor(_executor, _check), timeout=15.0)
    except asyncio.TimeoutError:
        return {"flags": ["TIMEOUT"], "recommendation": "mem_check timed out — executor pool likely saturated; retry or use kb_ingest directly.", "evidence": {}}


# ── Tools — index_ domain (Opus) ──────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def index_search(
    app_id:   str,
    query:    str,
    limit:    int  = 20,
    semantic: bool = False,
) -> dict:
    """Search opus.atoms by title or content."""
    logger.info("[w2] index_search app_id=%s q=%r semantic=%s", app_id, query, semantic)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _search():
        if semantic:
            try:
                results = pg.search_opus_semantic(query, limit)
            except Exception:
                results = pg.search_opus(query, limit)
        else:
            results = pg.search_opus(query, limit)
        return {"results": results, "count": len(results)}

    return await loop.run_in_executor(_executor, _search)


@mcp.tool()
@sap_gate(write=True)
async def index_ingest(
    app_id:     str,
    content:    str,
    domain:     str = "meta",
    depth:      int = 1,
    session_id: str = "",
) -> dict:
    """Write an atom to opus.atoms. Use for Opus-tier knowledge distinct from the main KB."""
    logger.info("[w2] index_ingest app_id=%s domain=%s depth=%d", app_id, domain, depth)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    atom_id = await loop.run_in_executor(
        _executor, pg.ingest_opus_atom,
        content, domain, depth, session_id or None,
    )
    return {"id": atom_id, "status": "ingested" if atom_id else "failed"}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def index_feedback(app_id: str, domain: str = "") -> dict:
    """Read opus feedback entries. Omit domain to return all entries."""
    logger.info("[w2] index_feedback app_id=%s domain=%s", app_id, domain)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    entries = await loop.run_in_executor(_executor, pg.opus_feedback, domain or None)
    return {"feedback": entries, "count": len(entries)}


@mcp.tool()
@sap_gate(write=True)
async def index_feedback_write(
    app_id:    str,
    domain:    str,
    principle: str,
    source:    str = "self",
    title:     str = "",
) -> dict:
    """Write a feedback principle to the opus feedback table."""
    logger.info("[w2] index_feedback_write app_id=%s domain=%s", app_id, domain)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(
        _executor, pg.opus_feedback_write,
        domain, principle, source, app_id, title or None,
    )
    return {"status": "written" if ok else "failed"}


@mcp.tool()
@sap_gate()
async def index_journal(app_id: str, entry: str, session_id: str = "",
                        title: str = "") -> dict:
    """Write a journal entry to the opus journal."""
    logger.info("[w2] index_journal app_id=%s", app_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    jid = await loop.run_in_executor(
        _executor, pg.opus_journal_write,
        entry, session_id or None, app_id, title or None,
    )
    return {"id": jid, "status": "logged" if jid else "failed"}


# ── Tools — ledger_ domain (Frank Ledger) ────────────────────────────────────

@mcp.tool()
@sap_gate(write=True)
async def ledger_write(
    app_id:     str,
    project:    str,
    event_type: str,
    content:    dict,
) -> dict:
    """Append an entry to the FRANK tamper-evident ledger."""
    logger.info("[w2] ledger_write app_id=%s project=%s event=%s", app_id, project, event_type)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    record_id = await loop.run_in_executor(
        _executor, pg.ledger_append, project, event_type, content,
    )
    return {"id": record_id, "status": "written"}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def ledger_read(app_id: str, project: str = "", limit: int = 20, full: bool = False) -> dict:
    """Read the FRANK tamper-evident ledger, optionally filtered by project.

    Entries with content over ~2k chars are compacted (keys + summary fields
    survive; bulk payloads are elided). Pass full=True for raw rows."""
    logger.info("[w2] ledger_read app_id=%s project=%s full=%s", app_id, project, full)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    entries = await loop.run_in_executor(
        _executor, pg.ledger_read, project or None, limit,
    )
    if not full:
        entries = [pg.compact_ledger_entry(e, max_chars=2000) for e in entries]
    return {"entries": entries, "count": len(entries)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def ledger_verify(app_id: str) -> dict:
    """Verify the FRANK ledger hash chain. Returns valid=True and entry count, or broken_at=<id> on failure."""
    logger.info("[w2] ledger_verify app_id=%s", app_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, pg.ledger_verify)


@mcp.tool()
@sap_gate(write=True)
async def ledger_repair(
    app_id: str,
    dry_run: bool = True,
    confirm: bool = False,
) -> dict:
    """Recompute FRANK ledger prev_hash/hash chain in created_at order.

    dry_run=True (default) reports how many rows would change.
    Set confirm=True and dry_run=False to apply repairs (e.g. after concurrent-append fork).
    """
    logger.info(
        "[w2] ledger_repair app_id=%s dry_run=%s confirm=%s",
        app_id, dry_run, confirm,
    )
    if not pg:
        return _no_pg()
    if not dry_run and not confirm:
        return {
            "error": "confirmation_required",
            "message": "Pass confirm=True with dry_run=False to repair the chain",
        }
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.ledger_repair_chain, dry_run
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def hook_list(app_id: str, active_only: bool = True) -> dict:
    """List registered hooks from the hook_registry table.
    active_only=True (default) filters to enabled hooks."""
    logger.info("[w2] hook_list app_id=%s active_only=%s", app_id, active_only)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(_executor, pg.hook_registry_list, active_only)
    return {"hooks": rows, "count": len(rows)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def hook_log_read(app_id: str, hook_name: str = "", limit: int = 50) -> dict:
    """Read hook execution log, optionally filtered by hook_name."""
    logger.info("[w2] hook_log_read app_id=%s hook=%s", app_id, hook_name)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(
        _executor, pg.hook_executions_read, hook_name or None, limit,
    )
    return {"executions": rows, "count": len(rows)}


# ── Tools — handoff_ domain ───────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def handoff_latest(app_id: str, agent: str = "", project: str = "", workspace: str = "") -> dict:
    """Fetch the most recent session handoff document for an agent.

    When ``project`` is set (or resolved from ``workspace``, WILLOW_PROJECT_ROOT, or
    WILLOW_HANDOFF_PROJECT), only handoffs tagged with that project id are considered.
    """
    logger.info("[w2] handoff_latest app_id=%s agent=%s project=%s workspace=%s", app_id, agent, project, workspace)
    loop = asyncio.get_running_loop()

    def _latest():
        import json as _j
        import sqlite3 as _sql
        import psycopg2.extras as _pge
        from willow.fylgja.handoff_project import resolve_handoff_project

        agent_filter = agent or app_id or os.environ.get("WILLOW_AGENT_NAME", "")
        project_filter = (
            project
            or resolve_handoff_project(workspace=workspace)
            or ""
        ).strip()

        # --- Postgres KB atoms (category='handoff', source_type='session') ---
        kb_result: dict | None = None
        if pg is not None:
            try:
                pg._ensure_conn()
                with pg.conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                    if agent_filter:
                        cur.execute(
                            """
                            SELECT id, title, summary, valid_at, created_at, updated_at, content
                            FROM knowledge
                            WHERE category = 'handoff'
                              AND source_type = 'session'
                              AND invalid_at IS NULL
                              AND project = %s
                            ORDER BY COALESCE(updated_at, created_at, valid_at) DESC
                            LIMIT 5
                            """,
                            (agent_filter,),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT id, title, summary, valid_at, created_at, updated_at, content
                            FROM knowledge
                            WHERE category = 'handoff'
                              AND source_type = 'session'
                              AND invalid_at IS NULL
                            ORDER BY COALESCE(updated_at, created_at, valid_at) DESC
                            LIMIT 5
                            """
                        )
                    kb_rows = cur.fetchall()
                    kb_candidates: list[dict] = []
                    for row in kb_rows:
                        content = row.get("content") or {}
                        if isinstance(content, str):
                            try:
                                content = _j.loads(content)
                            except Exception:
                                content = {}
                        if not isinstance(content, dict):
                            content = {}
                        open_threads = content.get("open_threads") or []
                        questions = content.get("next_steps") or content.get("questions") or []
                        if isinstance(open_threads, str):
                            try:
                                open_threads = _j.loads(open_threads)
                            except Exception:
                                open_threads = []
                        if isinstance(questions, str):
                            try:
                                questions = _j.loads(questions)
                            except Exception:
                                questions = []
                        kb_candidates.append({
                            "filename": f"kb_{row['id']}.json",
                            "date": str(row["valid_at"])[:10],
                            "project": str(content.get("project") or "").strip(),
                            "summary": content.get("summary") or row["summary"] or row["title"] or "",
                            "open_threads": open_threads if isinstance(open_threads, list) else [],
                            "questions": questions if isinstance(questions, list) else [],
                            "agreements": content.get("agreements") or [],
                            "capabilities": content.get("capabilities") or [],
                            "_source": "kb",
                            "_valid_at": str(row["valid_at"]),
                            "_sort_at": str(row.get("updated_at") or row.get("created_at") or row["valid_at"]),
                        })
                    kb_candidates = filter_handoff_candidates(kb_candidates, project_filter)
                    if kb_candidates:
                        kb_result = select_best_handoff(kb_candidates)
            except Exception as _e:
                logger.warning("[w2] handoff_latest pg query failed: %s", _e)

        # --- SQLite flat-file store ---
        sqlite_result: dict | None = None
        if Path(HANDOFF_DB).exists():
            try:
                conn = _sql.connect(HANDOFF_DB)
                conn.row_factory = _sql.Row
                cur  = conn.cursor()
                base_sql = handoff_select_sql(conn)
                sql_agent = f"{base_sql} WHERE h.file_type = 'session' AND f.filename LIKE ?"
                rows = cur.execute(sql_agent, (f"%{agent_filter}%",)).fetchall() if agent_filter else []
                sqlite_candidates: list[dict] = []
                for row in rows:
                    sqlite_candidates.append({
                        "filename": row["filename"],
                        "date": row["handoff_date"],
                        "project": row["project"] if "project" in row.keys() else "",
                        "summary": row["summary"],
                        "open_threads": _j.loads(row["open_threads"]) if row["open_threads"] else [],
                        "questions": _j.loads(row["questions"]) if row["questions"] else [],
                        "agreements": _j.loads(row["agreements"]) if row["agreements"] else [],
                        "capabilities": _j.loads(row["capabilities"]) if row["capabilities"] else [],
                        "_source": "sqlite",
                        "_valid_at": row["handoff_date"] or "",
                        "mtime": row["mtime"],
                    })
                sqlite_candidates = filter_handoff_candidates(sqlite_candidates, project_filter)
                sqlite_result = select_best_handoff(sqlite_candidates) if sqlite_candidates else None
                conn.close()
            except Exception as _e:
                logger.warning("[w2] handoff_latest sqlite query failed: %s", _e)

        # --- Markdown on disk (fallback when handoffs.db missing or index stale) ---
        markdown_result: dict | None = None
        if agent_filter:
            try:
                md_candidates: list[dict] = []
                for root in handoffs_roots():
                    md_candidates.extend(
                        scan_markdown_handoffs(agent_filter, root, project_filter)
                    )
                if md_candidates:
                    markdown_result = select_best_handoff(md_candidates)
            except Exception as _e:
                logger.warning("[w2] handoff_latest markdown scan failed: %s", _e)

        # Pick the richest handoff across KB, SQLite, and markdown (substance beats empty recency)
        candidates = [
            r for r in (kb_result, sqlite_result, markdown_result) if r is not None
        ]
        if not candidates:
            if project_filter:
                return {
                    "error": f"No session handoffs found for project {project_filter!r}.",
                    "project": project_filter,
                }
            return {"error": "No session handoffs found."}
        result = select_best_handoff(candidates) or candidates[0]
        if project_filter:
            result["project"] = project_filter
        if agent_filter:
            result.update(
                extract_live_handoff_notes(
                    agent_filter,
                    str(result.get("filename") or ""),
                )
            )
        result["next_bite"] = extract_next_bite(
            result.get("questions") or [],
            str(result.get("summary") or ""),
        )
        for key in ("_source", "_valid_at", "_sort_at", "mtime"):
            result.pop(key, None)
        return result

    return await loop.run_in_executor(_executor, _latest)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def handoff_search(
    app_id:    str,
    query:     str,
    limit:     int = 10,
    file_type: str = "",
) -> list:
    """Search handoff documents by content."""
    logger.info("[w2] handoff_search app_id=%s q=%r", app_id, query)
    loop = asyncio.get_running_loop()

    def _search():
        import sqlite3 as _sql
        import psycopg2.extras as _pge

        results: list[dict] = []

        # --- Postgres KB atoms ---
        if pg is not None and (not file_type or file_type == "session"):
            try:
                pg._ensure_conn()
                with pg.conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, title, summary, valid_at, project
                        FROM knowledge
                        WHERE category = 'handoff'
                          AND source_type = 'session'
                          AND invalid_at IS NULL
                          AND (title ILIKE %s OR summary ILIKE %s)
                        ORDER BY valid_at DESC
                        LIMIT %s
                        """,
                        (f"%{query}%", f"%{query}%", limit),
                    )
                    for r in cur.fetchall():
                        results.append({
                            "filename": f"kb_{r['id']}.json",
                            "type": "session",
                            "date": str(r["valid_at"])[:10],
                            "turns": None,
                            "summary": (r["summary"] or r["title"] or "")[:200],
                        })
            except Exception as _e:
                logger.warning("[w2] handoff_search pg query failed: %s", _e)

        # --- SQLite flat-file store ---
        if Path(HANDOFF_DB).exists():
            try:
                conn = _sql.connect(HANDOFF_DB)
                conn.row_factory = _sql.Row
                cur  = conn.cursor()
                sql  = ("SELECT f.filename, f.file_type, h.handoff_date, h.summary, h.turns"
                        " FROM handoffs h JOIN files f ON h.file_id = f.id"
                        " WHERE (h.summary LIKE ? OR h.raw_content LIKE ?)")
                params: list = [f"%{query}%", f"%{query}%"]
                if file_type:
                    sql += " AND h.file_type = ?"
                    params.append(file_type)
                sql += " ORDER BY h.handoff_date DESC LIMIT ?"
                params.append(limit)
                rows = cur.execute(sql, params).fetchall()
                conn.close()
                results.extend({"filename": r["filename"], "type": r["file_type"],
                                 "date": r["handoff_date"], "turns": r["turns"],
                                 "summary": (r["summary"] or "")[:200]} for r in rows)
            except Exception as _e:
                logger.warning("[w2] handoff_search sqlite query failed: %s", _e)

        results.sort(key=lambda r: r.get("date") or "", reverse=True)
        return results[:limit]

    return await loop.run_in_executor(_executor, _search)


@mcp.tool()
@sap_gate()
async def handoff_rebuild(app_id: str) -> dict:
    """Rebuild the handoffs.db index by scanning HANDOFF_DIRS."""
    logger.info("[w2] handoff_rebuild app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _rebuild():
        import subprocess as _sp
        canonical = Path(__file__).parent / "tools" / "build_handoff_db.py"
        local     = Path(HANDOFF_DB).parent / "build_handoff_db.py"
        script    = str(canonical) if canonical.exists() else str(local)
        if not Path(script).exists():
            return {"error": f"build script not found: {script}"}
        env = os.environ.copy()
        env["WILLOW_HANDOFF_DB"]        = HANDOFF_DB
        env["WILLOW_HANDOFF_DIRS"]      = HANDOFF_DIRS
        env["WILLOW_PG_SKIP_SCHEMA_INIT"] = "1"
        proc = _sp.run(
            [sys.executable, script], capture_output=True, text=True, timeout=60, env=env,
        )
        return {
            "status":  "ok" if proc.returncode == 0 else "error",
            "stdout":  proc.stdout.strip()[-1000:],
            "stderr":  proc.stderr.strip()[-500:],
            "db_path": HANDOFF_DB,
        }

    return await loop.run_in_executor(_executor, _rebuild)


@mcp.tool()
@sap_gate()
async def handoff_write_v3(
    app_id: str,
    summary: str = "",
    claims: list | None = None,
    next_bite: dict | None = None,
    open_questions: list | None = None,
    agreements: list | None = None,
    agent_notes: list | None = None,
    understanding: str = "",
    project: str = "",
    session_id: str = "",
    workspace: str = "",
) -> dict:
    """Write a v3 session handoff (claims record carrying narrative).

    Claims: [{id, text, kind, verify:{type, subject, expect}, opened, carried_from}].
    Kinds: branch_pushed | pr_state | file_exists | flag_open | sha_current | prose.
    Non-prose claims require verify.subject. Code collects the machine skeleton
    and serializes the JSON block — do not author JSON in the narrative.
    Schema: docs/adrs/handoff-v3.schema.json (ADR-20260703).
    """
    logger.info("[w2] handoff_write_v3 app_id=%s claims=%d", app_id, len(claims or []))
    loop = asyncio.get_running_loop()

    def _write():
        from willow.fylgja.handoff_v3 import write_session_handoff_v3

        try:
            path = write_session_handoff_v3(
                app_id,
                summary=summary,
                claims=[c for c in (claims or []) if isinstance(c, dict)],
                next_bite=next_bite if isinstance(next_bite, dict) else None,
                open_questions=[str(q) for q in (open_questions or [])],
                agreements=[str(a) for a in (agreements or [])],
                agent_notes=[str(n) for n in (agent_notes or [])],
                understanding=understanding,
                project=project,
                session_id=session_id,
                repo_root=workspace,
                workspace=workspace,
            )
        except ValueError as exc:
            return {"error": str(exc)}
        return {"status": "ok", "filename": path.name, "path": str(path), "format": "v3"}

    return await loop.run_in_executor(_executor, _write)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def boot_digest(app_id: str, project: str = "", workspace: str = "") -> dict:
    """Boot digest — latest handoff with claims verified at read time.

    Returns {lines, digest}. lines are the model-facing terse rendering;
    every action-driving item carries verified/STALE/unverified + checked_at.
    Replaces stale copy chains (cross-runtime NEXT, anchor threads) at boot.
    """
    logger.info("[w2] boot_digest app_id=%s project=%s", app_id, project)
    loop = asyncio.get_running_loop()

    def _digest():
        from willow.fylgja.boot_digest import build_boot_digest, render_lines

        extra: dict = {}
        try:
            from core.code_version import staleness

            extra["code_version"] = staleness()
        except Exception:
            pass
        digest = build_boot_digest(
            app_id,
            project=project,
            workspace=workspace,
            repo_root=workspace or str(Path(__file__).resolve().parents[1]),
            extra=extra or None,
        )
        return {"lines": render_lines(digest), "digest": digest}

    return await loop.run_in_executor(_executor, _digest)


# ── Tools — soul_ domain (tension detection + AutoDream) ──────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def tension_scan(
    app_id:   str,
    write_kb: bool = False,
    limit:    int  = 30,
) -> dict:
    """Scan KB frontier/contested atoms for semantic tensions or redundancies.
    Uses nomic-embed for neighbour search and mistral:7b for pair classification.
    write_kb=True saves findings as a KB atom (category='tension')."""
    logger.info("[w2] tension_scan app_id=%s write_kb=%s", app_id, write_kb)
    loop = asyncio.get_running_loop()

    def _scan():
        import psycopg2.extras as _pge
        from sap.clients.professor_client import _ask_ollama

        if pg is None:
            return {"error": "Postgres unavailable"}

        # Fetch scannable atoms
        try:
            pg._ensure_conn()
            with pg.conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, title, summary, tier, confidence
                    FROM knowledge
                    WHERE invalid_at IS NULL
                      AND (tier IN ('frontier', 'contested', 'hypothesis', 'observed') OR tier IS NULL)
                      AND summary IS NOT NULL AND summary != ''
                    ORDER BY valid_at DESC
                    LIMIT 60
                """)
                atoms = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            return {"error": f"fetch failed: {e}"}

        if len(atoms) < 2:
            return {"pairs_checked": 0, "tensions": [], "message": "Not enough atoms to scan"}

        seen_pairs: set = set()
        tensions: list = []
        compatible = 0

        for atom in atoms:
            if len(tensions) >= limit:
                break
            try:
                neighbors = pg.knowledge_search_semantic(atom["summary"], limit=4)
            except Exception:
                continue
            for nb in neighbors:
                nid = nb.get("id", "")
                if not nid or nid == atom["id"]:
                    continue
                pair_key = tuple(sorted([atom["id"], nid]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                prompt = (
                    f"Atom A — {atom['title']}\n{atom['summary'][:300]}\n\n"
                    f"Atom B — {nb.get('title','')}\n{(nb.get('summary') or '')[:300]}\n\n"
                    "Classify with EXACTLY one label on the first line, then one reasoning sentence:\n"
                    "TENSION — atoms make conflicting claims\n"
                    "REDUNDANT — one supersedes or fully contains the other\n"
                    "COMPATIBLE — complementary, no conflict"
                )
                try:
                    resp = _ask_ollama(
                        "mistral:7b",
                        "You are a knowledge graph auditor. Classify atom pairs tersely.",
                        prompt,
                    ) or ""
                except Exception:
                    resp = ""

                label = resp.strip().split("\n")[0].upper() if resp else ""
                if "TENSION" in label or "REDUNDANT" in label:
                    tensions.append({
                        "type":   "redundant" if "REDUNDANT" in label else "tension",
                        "atom_a": {"id": atom["id"], "title": atom["title"], "tier": atom.get("tier")},
                        "atom_b": {"id": nid, "title": nb.get("title",""), "tier": nb.get("tier")},
                        "reason": resp.strip()[:400],
                    })
                else:
                    compatible += 1

        result: dict = {
            "pairs_checked":   len(seen_pairs),
            "tensions":        tensions,
            "compatible_pairs": compatible,
        }

        if write_kb and tensions:
            try:
                first = tensions[0]
                kb_summary = (
                    f"Tension scan found {len(tensions)} tension/redundancy pairs among "
                    f"{len(atoms)} scannable atoms ({len(seen_pairs)} pairs checked). "
                    f"First: {first['atom_a']['title']} vs {first['atom_b']['title']}."
                )
                pg.knowledge_put({
                    "title":       f"Tension scan {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
                    "summary":     kb_summary,
                    "content":     {"tensions": tensions, "pairs_checked": len(seen_pairs)},
                    "category":    "tension",
                    "source_type": "session",
                    "project":     app_id,
                    "weight":      0.6,
                    "tier":        "observed",
                    "confidence":  0.7,
                })
            except Exception as e:
                result["write_error"] = str(e)

        return result

    return await loop.run_in_executor(_executor, _scan)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def dream_check(app_id: str) -> dict:
    """Check whether AutoDream conditions are met for this agent.
    Conditions: 24h+ since last dream AND 5+ sessions (willow.runs rows) since last dream.
    Returns {should_dream, hours_since_dream, sessions_since_dream, last_dream_at}."""
    logger.info("[w2] dream_check app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _check():
        from core.dream_state import dream_conditions
        return dream_conditions(app_id, store, pg=pg)

    return await loop.run_in_executor(_executor, _check)


@mcp.tool()
@sap_gate(write=True)
async def dream_run(app_id: str, force: bool = False) -> dict:
    """Run the AutoDream synthesis pipeline.
    Checks conditions unless force=True. Runs tension scan, synthesises patterns
    from recent KB atoms via mistral:7b, writes a dream KB atom, updates dream state.
    Call dream_check first unless you intend force=True."""
    logger.info("[w2] dream_run app_id=%s force=%s", app_id, force)
    loop = asyncio.get_running_loop()

    def _run():
        import psycopg2.extras as _pge
        from datetime import datetime, timezone
        from sap.clients.professor_client import _ask_ollama

        if pg is None:
            return {"error": "Postgres unavailable"}

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Check lock and conditions. A stale lock (crashed run past the TTL) is
        # ignored so dream_run reclaims it instead of refusing forever.
        from core.lock_ttl import lock_is_live

        dream_state = store.get(f"{app_id}/dream", "state") or {}
        if lock_is_live(dream_state) and not force:
            return {"error": "dream already running (locked). Pass force=true to override."}

        if not force:
            last_str = dream_state.get("last_dream_at", "")
            if last_str:
                try:
                    last = datetime.fromisoformat(last_str)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    hours_elapsed = (now - last).total_seconds() / 3600
                    if hours_elapsed < 24:
                        return {"skipped": True, "reason": f"only {hours_elapsed:.1f}h since last dream (need 24h)"}
                except Exception:
                    pass

        # Acquire lock
        try:
            store.put(f"{app_id}/dream", {"locked": True, "lock_acquired_at": now_iso}, record_id="state")
        except Exception:
            pass

        try:
            # 1. Fetch recent atoms for synthesis
            pg._ensure_conn()
            with pg.conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, title, summary, tier, confidence, category
                    FROM knowledge
                    WHERE invalid_at IS NULL
                      AND summary IS NOT NULL AND summary != ''
                    ORDER BY valid_at DESC
                    LIMIT 20
                """)
                atoms = [dict(r) for r in cur.fetchall()]

            # 2. Lightweight tension scan (no KB write — dream atom captures it)
            tensions: list = []
            seen_pairs: set = set()
            for atom in atoms[:10]:
                try:
                    neighbors = pg.knowledge_search_semantic(atom["summary"], limit=3)
                    for nb in neighbors:
                        nid = nb.get("id", "")
                        if not nid or nid == atom["id"]:
                            continue
                        pair_key = tuple(sorted([atom["id"], nid]))
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)
                        resp = _ask_ollama(
                            "llama3.2:3b",
                            "You are a knowledge graph auditor.",
                            (f"A: {atom['title']}\n{atom['summary'][:200]}\n\n"
                             f"B: {nb.get('title','')}\n{(nb.get('summary') or '')[:200]}\n\n"
                             "Reply TENSION or COMPATIBLE (one word), then one sentence."),
                        ) or ""
                        if "TENSION" in resp.upper().split("\n")[0]:
                            tensions.append({"ids": [atom["id"], nid], "reason": resp.strip()[:200]})
                except Exception:
                    continue

            # 3. Synthesise patterns via local LLM
            atom_digest = "\n".join(
                f"- [{a.get('tier','?')}] {a['title']}: {(a.get('summary') or '')[:120]}"
                for a in atoms[:12]
            )
            synthesis = _ask_ollama(
                "mistral:7b",
                "You are a thoughtful knowledge synthesist. Be concise and specific.",
                (f"Reflecting on {len(atoms)} recent knowledge atoms for agent {app_id}:\n\n"
                 f"{atom_digest}\n\n"
                 "In 3-4 sentences: what patterns, connections, or gaps do you notice? "
                 "What should be explored or reconciled next?"),
            ) or ""

            # 4. Write dream KB atom
            dream_summary = (
                f"AutoDream over {len(atoms)} atoms — {len(tensions)} tensions detected. "
                + (synthesis[:300] if synthesis else "")
            )
            atom_id = pg.gen_id(8)
            pg.knowledge_put({
                "id":          atom_id,
                "title":       f"Dream {now.strftime('%Y-%m-%d')} — {app_id}",
                "summary":     dream_summary,
                "content":     {
                    "synthesis":     synthesis,
                    "tensions_found": len(tensions),
                    "tension_pairs": tensions[:5],
                    "atoms_scanned": len(atoms),
                },
                "category":    "dream",
                "source_type": "session",
                "project":     app_id,
                "weight":      0.7,
                "tier":        "observed",
                "confidence":  0.75,
            })

            # 5. Release lock + update state
            store.put(f"{app_id}/dream", {
                "last_dream_at":        now_iso,
                "locked":               False,
                "last_dream_atom":      atom_id,
            }, record_id="state")

            return {
                "atom_id":        atom_id,
                "atoms_scanned":  len(atoms),
                "tensions_found": len(tensions),
                "synthesis":      synthesis[:500] if synthesis else "",
            }

        except Exception as e:
            try:
                store.put(f"{app_id}/dream", {"locked": False, "last_error": str(e)[:200]}, record_id="state")
            except Exception:
                pass
            return {"error": str(e)}

    return await loop.run_in_executor(_executor, _run)


@mcp.tool()
@sap_gate(write=True)
async def dream_schedule(
    app_id: str,
    force: bool = False,
    check_first: bool = True,
) -> dict:
    """Queue AutoDream (auto_dream.py) as a Kart task. Returns task_id.
    check_first=True (default) skips queue unless dream_check says should_dream.
    Call kart_task_run() afterwards or let Kart poll. Requires Ollama (# allow_localhost)."""
    logger.info("[w2] dream_schedule app_id=%s force=%s check_first=%s", app_id, force, check_first)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _schedule():
        from core.dream_state import dream_conditions, queue_dream_task

        if check_first and not force:
            check = dream_conditions(app_id, store, pg=pg)
            if not check.get("should_dream"):
                return {"status": "skipped", "dream_check": check}
        task_id = queue_dream_task(pg, app_id, submitted_by=app_id, force=force)
        if not task_id:
            return {"error": "failed to submit task"}
        return {"task_id": task_id, "status": "queued", "app_id": app_id, "force": force}

    return await loop.run_in_executor(_executor, _schedule)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def wce_check(app_id: str) -> dict:
    """Check whether the weekly WCE witness is due for this agent.
    Conditions: WCE_INTERVAL_DAYS (default 7) since last run in SOIL {agent}/wce/state.
    Returns {should_run, days_since_run, last_run_at, interval_days}."""
    logger.info("[w2] wce_check app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _check():
        from core.wce_state import wce_conditions
        return wce_conditions(app_id, store)

    return await loop.run_in_executor(_executor, _check)


@mcp.tool()
@sap_gate(write=True)
async def wce_schedule(
    app_id: str,
    force: bool = False,
    check_first: bool = True,
    pair_limit: int = 0,
) -> dict:
    """Queue scripts/wce_witness.py as a Kart task. Returns task_id.
    check_first=True (default) skips queue unless wce_check says should_run.
    Call kart_task_run() afterwards or let Kart poll. Requires Postgres + Ollama (# allow_localhost)."""
    logger.info("[w2] wce_schedule app_id=%s force=%s check_first=%s", app_id, force, check_first)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _schedule():
        from core.wce_state import queue_wce_task, wce_conditions

        if check_first and not force:
            check = wce_conditions(app_id, store)
            if not check.get("should_run"):
                return {"status": "skipped", "wce_check": check}
        task_id = queue_wce_task(
            pg, app_id, submitted_by=app_id, force=force, pair_limit=pair_limit,
        )
        if not task_id:
            return {"error": "failed to submit task"}
        return {"task_id": task_id, "status": "queued", "app_id": app_id, "force": force}

    return await loop.run_in_executor(_executor, _schedule)


# ── Tools — intelligence passes (P4.1/P4.2/P4.3) ─────────────────────────────

@mcp.tool()
@sap_gate(write=True)
async def kb_intelligence_run(
    app_id:   str,
    enabled:  bool = False,
    dry_run:  bool = True,
    passes:   list = None,
) -> dict:
    """Trigger KB intelligence consolidation passes (NREM/sleep_consolidation).
    DISABLED BY DEFAULT — must pass enabled=True to actually run.
    dry_run=True (default) reports what would run without writing.
    passes: list of passes to run — ['dedup', 'contradictions', 'decay', 'sqlite']
            defaults to all four. 'intelligence' (insight_pass+chunk_pass) skipped
            unless explicitly requested and PMEM modules are available."""
    logger.info("[w2] kb_intelligence_run app_id=%s enabled=%s dry_run=%s", app_id, enabled, dry_run)
    if not enabled:
        return {
            "status": "disabled",
            "note": "Pass enabled=True to run. dry_run=True by default for safety.",
        }
    if not pg:
        return _no_pg()

    loop = asyncio.get_running_loop()

    def _run():
        import sys
        script = str(_SAP_ROOT / "scripts" / "sleep_consolidation.py")
        cmd = [sys.executable, script]
        if dry_run:
            cmd.append("--dry-run")
        if passes and "intelligence" not in (passes or []):
            cmd.append("--skip-intelligence")

        import subprocess
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {
            "returncode": proc.returncode,
            "stdout":     proc.stdout.strip()[-3000:],
            "stderr":     proc.stderr.strip()[-500:],
            "dry_run":    dry_run,
        }

    return await loop.run_in_executor(_executor, _run)


@mcp.tool()
@sap_gate(write=True)
async def kb_extract_from_session(
    app_id:      str,
    commit_hash: str = "",
    source_type: str = "commit",
    write:       bool = False,
) -> dict:
    """Extract KB atoms from a git commit or recent session using atom_extractor.
    commit_hash: SHA to extract from (source_type=commit or merge).
    write=False (default) — returns the atom without persisting; write=True writes to KB."""
    logger.info("[w2] kb_extract_from_session app_id=%s hash=%s write=%s", app_id, commit_hash, write)
    loop = asyncio.get_running_loop()

    def _extract():
        from core.atom_extractor import extract_commit_atom, extract_merge_atom

        if not commit_hash:
            # Pull the latest commit hash
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            )
            if result.returncode != 0:
                return {"error": "no commit_hash provided and git HEAD unavailable"}
            target = result.stdout.strip()
        else:
            target = commit_hash

        if source_type == "merge":
            atom = extract_merge_atom(target, "")
        else:
            atom = extract_commit_atom(target)

        if atom is None:
            return {"error": "atom extraction failed", "commit_hash": target}

        atom_dict = atom.to_dict()

        if write and pg:
            atom_id = pg.ingest_atom(
                title=atom.title,
                summary=atom.summary,
                source_type=atom.source_type,
                source_id=target,
                category=atom.category,
                tier="frontier",
                confidence=0.85,
            )
            atom_dict["written_id"] = atom_id

        return {"atom": atom_dict, "written": write and pg is not None}

    return await loop.run_in_executor(_executor, _extract)


@mcp.tool()
@sap_gate(write=True)
async def kb_backup(app_id: str, label: str = "") -> dict:
    """Backup the Willow Postgres DB to $WILLOW_HOME/backups/ using pg_dump -Fc.
    label: optional tag appended to filename. Returns path and size on success."""
    logger.info("[w2] kb_backup app_id=%s label=%r", app_id, label)
    loop = asyncio.get_running_loop()

    def _backup():
        import subprocess
        import shutil
        from datetime import datetime

        if not shutil.which("pg_dump"):
            return {"error": "pg_dump not found in PATH"}

        backup_dir = _fleet_home() / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        db_name = os.environ.get("WILLOW_PG_DB", "willow_20")
        ts      = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        slug    = f"_{label}" if label else ""
        fname   = f"{db_name}{slug}_{ts}.dump"
        out_path = backup_dir / fname

        try:
            result = subprocess.run(
                ["pg_dump", "-Fc", "-d", db_name, "-f", str(out_path)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return {"error": result.stderr.strip()[-500:]}
            size_bytes = out_path.stat().st_size
            return {
                "status": "ok",
                "path":   str(out_path),
                "db":     db_name,
                "size_bytes": size_bytes,
                "size_mb":    round(size_bytes / 1_048_576, 2),
            }
        except subprocess.TimeoutExpired:
            return {"error": "pg_dump timed out after 120s"}
        except Exception as e:
            return {"error": str(e)}

    return await loop.run_in_executor(_executor, _backup)


# ── Tools — workflow engine ───────────────────────────────────────────────────

@mcp.tool()
@sap_gate(write=True)
async def workflow_define(
    app_id:     str,
    name:       str,
    definition: str,
) -> dict:
    """Define or update a workflow. definition is a JSON string with shape:
    {"phases": {"phase_name": {"prompt": "...", "depends_on": [], "output_schema": {}, "model": "..."}}}
    Phases with no depends_on run first. Phases whose depends_on are all completed run next.
    Parallel phases (same depends_on set) run concurrently.
    output_schema: JSON schema dict for structured LLM output (optional).
    model: per-phase model override (default: $KART_WORKFLOW_MODEL or mistral:7b)."""
    logger.info("[w2] workflow_define app_id=%s name=%s", app_id, name)
    if not pg:
        return _no_pg()
    try:
        defn = json.loads(definition) if isinstance(definition, str) else definition
    except Exception as e:
        return {"error": f"definition must be valid JSON: {e}"}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, pg.workflow_define, name, defn, app_id)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def workflow_list(app_id: str) -> dict:
    """List all defined workflows."""
    logger.info("[w2] workflow_list app_id=%s", app_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(_executor, pg.workflow_list)
    return {"workflows": rows, "total": len(rows)}


@mcp.tool()
@sap_gate(write=True)
async def workflow_run(
    app_id: str,
    name:   str,
    input:  str = "{}",
) -> dict:
    """Start a workflow run. input is a JSON string of variables available as {{input.key}} in prompts.
    Queues the first phase(s) immediately as kart tasks.
    Returns: {run_id, phases_queued}."""
    logger.info("[w2] workflow_run app_id=%s name=%s", app_id, name)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    wf = await loop.run_in_executor(_executor, pg.workflow_get, name)
    if not wf:
        return {"error": f"workflow '{name}' not defined — call workflow_define first"}

    try:
        input_data = json.loads(input) if isinstance(input, str) else input
    except Exception:
        input_data = {}

    def _start():
        import re as _re
        run_id = pg.workflow_run_create(wf["id"], input_data, app_id)
        phases = wf["definition"].get("phases", {})

        # Queue phases with no dependencies
        queued = 0
        for phase_name, phase_def in phases.items():
            if phase_def.get("depends_on", []):
                continue  # blocked, will be queued when deps complete
            prompt = phase_def.get("prompt", "")
            # Resolve {{input.x}} substitutions for first phase
            def _sub(m):
                expr = m.group(1).strip().split(".")
                if expr[0] == "input":
                    val = input_data
                    for p in expr[1:]:
                        val = val.get(p, "") if isinstance(val, dict) else ""
                    return str(val)
                return m.group(0)
            prompt = _re.sub(r"\{\{([^}]+)\}\}", _sub, prompt)

            phase_input = {
                "prompt":        prompt,
                "model":         phase_def.get("model", os.environ.get("KART_WORKFLOW_MODEL", "mistral:7b")),
                "output_schema": phase_def.get("output_schema", {}),
                "phase_name":    phase_name,
            }
            payload = json.dumps({
                "type":        "workflow_phase",
                "run_id":      run_id,
                "phase_name":  phase_name,
                "phase_input": phase_input,
            })
            task_id = pg.submit_task(payload, submitted_by=app_id, agent="kart")
            pg.workflow_phase_create(run_id, phase_name, phase_input, task_id)
            queued += 1

        return {"run_id": run_id, "workflow": name, "phases_queued": queued}

    return await loop.run_in_executor(_executor, _start)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def workflow_status(app_id: str, run_id: str) -> dict:
    """Get the status of a workflow run — all phases, their outputs, current state."""
    logger.info("[w2] workflow_status app_id=%s run_id=%s", app_id, run_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, pg.workflow_status, run_id)


@mcp.tool()
@sap_gate(write=True)
async def workflow_cancel(app_id: str, run_id: str) -> dict:
    """Cancel a running or pending workflow run. Pending phases are skipped."""
    logger.info("[w2] workflow_cancel app_id=%s run_id=%s", app_id, run_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, pg.workflow_cancel, run_id)


# ── Tools — outcomes domain ───────────────────────────────────────────────────

@mcp.tool()
@sap_gate(write=True)
async def outcome_agent_register(
    app_id:         str,
    name:           str,
    agent_id:       str,
    environment_id: str,
    description:    str = "",
) -> dict:
    """Register a Managed Agent for use with the Outcomes API.

    agent_id and environment_id come from the Anthropic Console.
    name is a local alias (e.g. 'kb-writer', 'summarizer').
    """
    logger.info("[w2] outcome_agent_register app_id=%s name=%s", app_id, name)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.outcome_agent_register, name, agent_id, environment_id, description, app_id
    )


@mcp.tool()
@sap_gate(write=True)
async def outcome_run(
    app_id:         str,
    agent_name:     str,
    prompt:         str,
    rubric:         str,
    max_iterations: int = 3,
    title:          str = "",
    timeout_s:      int = 600,
    skill_id:       str = "",
) -> dict:
    """Run an Outcomes flow against a registered Managed Agent.

    prompt      — what the agent should accomplish (user.define_outcome description).
    rubric      — markdown criteria the grader uses to evaluate success.
    Returns {outcome_run_id, session_id, result, explanation, success, iterations}.
    """
    logger.info("[w2] outcome_run app_id=%s agent=%s", app_id, agent_name)
    if not pg:
        return _no_pg()

    loop = asyncio.get_running_loop()
    agent = await loop.run_in_executor(_executor, pg.outcome_agent_get, agent_name)
    if not agent:
        return {"error": f"agent '{agent_name}' not registered — call outcome_agent_register first"}

    run_id = await loop.run_in_executor(
        _executor, pg.outcome_run_create, agent["id"], prompt, rubric, max_iterations, app_id, skill_id
    )

    try:
        import core.outcomes as _outcomes
        _agent_id  = agent["agent_id"]
        _env_id    = agent["environment_id"]
        _title     = title or prompt[:60]
        result = await loop.run_in_executor(
            _executor,
            lambda: _outcomes.run_outcome(
                agent_id=_agent_id,
                environment_id=_env_id,
                prompt=prompt,
                rubric=rubric,
                max_iterations=max_iterations,
                title=_title,
                timeout_s=timeout_s,
            ),
        )
        _res = result
        await loop.run_in_executor(
            _executor,
            lambda: pg.outcome_run_update(
                run_id,
                status=_res["result"],
                result=_res["result"],
                explanation=_res.get("explanation", ""),
                session_id=_res.get("session_id"),
                iterations_used=_res.get("iterations", 0),
            ),
        )
        return {"outcome_run_id": run_id, **result}
    except Exception as exc:
        logger.error("[w2] outcome_run failed: %s", exc)
        _err = str(exc)
        await loop.run_in_executor(
            _executor,
            lambda: pg.outcome_run_update(run_id, status="failed", error=_err),
        )
        return {"outcome_run_id": run_id, "error": _err}


@mcp.tool()
@sap_gate(write=False)
async def outcome_status(app_id: str, run_id: str) -> dict:
    """Get the status and result of a previously started outcome run."""
    logger.info("[w2] outcome_status app_id=%s run_id=%s", app_id, run_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    row = await loop.run_in_executor(_executor, pg.outcome_run_get, run_id)
    if not row:
        return {"error": f"outcome run {run_id!r} not found"}
    return row


# ── Tools — routines domain ───────────────────────────────────────────────────

@mcp.tool()
@sap_gate(write=True)
async def routine_register(
    app_id:      str,
    name:        str,
    routine_id:  str,
    token:       str,
    description: str = "",
) -> dict:
    """Register a Claude Code Routine credential in the DB.
    routine_id: the Anthropic routine ID (from claude.ai/code/routines).
    token: the bearer token shown once at creation — store it now.
    Upserts on name, so re-registering with a new token rotates the credential."""
    logger.info("[w2] routine_register app_id=%s name=%s", app_id, name)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.routine_register, name, routine_id, token, description, app_id
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def routine_list(app_id: str) -> dict:
    """List all registered routines (IDs and metadata, no tokens)."""
    logger.info("[w2] routine_list app_id=%s", app_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(_executor, pg.routine_list)
    return {"routines": rows, "total": len(rows)}


@mcp.tool()
@sap_gate(write=True)
async def routine_fire(
    app_id:  str,
    name:    str,
    context: str = "",
) -> dict:
    """Fire a registered Claude Code Routine by name via the Anthropic API.
    context: optional freeform text passed as the 'text' field to the Routine.
    Returns: {session_id, session_url} on success."""
    logger.info("[w2] routine_fire app_id=%s name=%s", app_id, name)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    routine = await loop.run_in_executor(_executor, pg.routine_get, name)
    if not routine:
        return {"error": f"routine '{name}' not registered — call routine_register first"}

    def _fire():
        import urllib.request
        import json as _json

        routine_id = routine["id"]
        token      = routine["token"]
        url        = f"https://api.anthropic.com/v1/claude_code/routines/{routine_id}/fire"
        payload    = _json.dumps({"text": context}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization":  f"Bearer {token}",
                "anthropic-beta": "experimental-cc-routine-2026-04-01",
                "anthropic-version": "2023-06-01",
                "Content-Type":   "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = _json.loads(resp.read())
            session_id  = body.get("claude_code_session_id", "")
            session_url = body.get("claude_code_session_url", "")
            pg.routine_mark_fired(name, session_id)
            return {
                "fired":       True,
                "name":        name,
                "session_id":  session_id,
                "session_url": session_url,
            }
        except Exception as e:
            return {"error": str(e), "name": name}

    return await loop.run_in_executor(_executor, _fire)


# ── Tools — nest_ domain ──────────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def nest_scan(app_id: str) -> dict:
    """Scan the Nest intake queue — returns staged items and current queue."""
    logger.info("[w2] nest_scan app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _scan():
        from sap.core.nest_intake import scan_nest, get_queue
        staged = scan_nest()
        queue  = get_queue()
        return {"staged": staged, "queue": queue, "pending": len(queue)}

    return await loop.run_in_executor(_executor, _scan)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def nest_queue(app_id: str) -> dict:
    """Return the current Nest intake queue without scanning."""
    logger.info("[w2] nest_queue app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _queue():
        from sap.core.nest_intake import get_queue
        q = get_queue()
        return {"queue": q, "pending": len(q)}

    return await loop.run_in_executor(_executor, _queue)


@mcp.tool()
@sap_gate()
async def nest_file(
    app_id:        str,
    item_id:       str,
    action:        str,
    override_dest: str = "",
) -> dict:
    """Review a Nest item. action: confirm | skip.
    confirm moves the item to its destination; skip removes it from the queue."""
    logger.info("[w2] nest_file app_id=%s item=%s action=%s", app_id, item_id, action)
    loop = asyncio.get_running_loop()

    def _file():
        from sap.core.nest_intake import confirm_review, skip_item
        iid = int(item_id)
        if action == "confirm":
            return confirm_review(iid, override_dest=override_dest or None)
        return skip_item(iid)

    return await loop.run_in_executor(_executor, _file)


# ── Tools — miscellaneous (blast, journal, governance, persona, base17, agent_create) ──

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_blast(app_id: str, summarize: bool = False) -> dict:
    """Blast-radius scan: map every sensitive file and credential env var reachable by an AI agent.
    Returns a score (0-100, higher = cleaner), reachable paths, and flagged env vars."""
    logger.info("[w2] fleet_blast app_id=%s summarize=%s", app_id, summarize)
    loop = asyncio.get_running_loop()

    def _run():
        result = _blast.run_blast()
        return _blast.summarize_blast(result) if summarize else result

    return await loop.run_in_executor(_executor, _run)


@mcp.tool()
@sap_gate()
async def kb_journal(app_id: str, entry: str, domain: str = "meta") -> dict:
    """Write a journal entry to the knowledge graph."""
    logger.info("[w2] kb_journal app_id=%s domain=%s", app_id, domain)
    loop = asyncio.get_running_loop()

    def _journal():
        if pg:
            atom_id = pg.ingest_ganesha_atom(entry, domain=domain, depth=1)
            return {"status": "logged", "atom_id": atom_id}
        rid, action, _ = store.put("journal/entries", {"text": entry})
        return {"status": "logged_local", "id": rid}

    return await loop.run_in_executor(_executor, _journal)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cmb_get(app_id: str, atom_id: str) -> dict:
    """Fetch a cmb_atom by ID."""
    logger.info("[w2] cmb_get app_id=%s atom_id=%s", app_id, atom_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_executor, pg.cmb_get, atom_id)
    return result or {"error": "not found"}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cmb_list(app_id: str, agent: str = "", limit: int = 20) -> dict:
    """List cmb_atoms (journal entries). Filter by agent if provided."""
    logger.info("[w2] cmb_list app_id=%s agent=%s", app_id, agent)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, pg.cmb_list, agent or None, limit)
    return {"results": results, "total": len(results)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cmb_search(app_id: str, query: str, limit: int = 20) -> dict:
    """Search cmb_atoms by content or title."""
    logger.info("[w2] cmb_search app_id=%s q=%r", app_id, query)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, pg.cmb_search, query, limit)
    return {"results": results, "total": len(results)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def journal_read(app_id: str, agent: str = "", session_id: str = "",
                       limit: int = 20) -> dict:
    """Read journal entries. Filter by agent and/or session_id."""
    logger.info("[w2] journal_read app_id=%s agent=%s", app_id, agent)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        _executor, pg.journal_read, agent or None, session_id or None, limit)
    return {"results": results, "total": len(results)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def context_list(app_id: str, agent: str = "", limit: int = 20) -> dict:
    """List non-expired compact_contexts. Filter by agent if provided."""
    logger.info("[w2] context_list app_id=%s agent=%s", app_id, agent)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(_executor, pg.compact_context_list, agent or None, limit)
    return {"results": results, "total": len(results)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def context_get(app_id: str, ctx_id: str) -> dict:
    """Fetch a compact_context by ID."""
    logger.info("[w2] context_get app_id=%s ctx_id=%s", app_id, ctx_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_executor, pg.compact_context_get, ctx_id)
    return result or {"error": "not found"}


@mcp.tool()
@sap_gate(write=True)
async def context_expire(app_id: str, ctx_id: str) -> dict:
    """Expire a compact_context immediately (sets expires_at=now())."""
    logger.info("[w2] context_expire app_id=%s ctx_id=%s", app_id, ctx_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, pg.compact_context_expire, ctx_id)


@mcp.tool()
@sap_gate(write=True)
async def context_save(
    app_id:    str,
    content:   str,
    category:  str = "handoff",
    ttl_hours: int = 48,
) -> dict:
    """Save a compact context summary to the DB.
    Call this when context depth is high — pass the structured summary as `content`.
    The saved context survives session resets and is loaded by handoff_latest / context_list.
    Returns: {id, agent, category} on success."""
    logger.info("[w2] context_save app_id=%s category=%s ttl=%d", app_id, category, ttl_hours)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        _executor, pg.compact_context_write, app_id, content, category, ttl_hours
    )
    return result


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def routing_log_read(app_id: str, session_id: str = "", limit: int = 20) -> dict:
    """Read routing_decisions log. Filter by session_id if provided."""
    logger.info("[w2] routing_log_read app_id=%s session=%s", app_id, session_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        _executor, pg.routing_decisions_read, session_id or None, limit)
    return {"results": results, "total": len(results)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_governance(app_id: str) -> dict:
    """Governance status: active policy rules from the policy_rules table + proposal directory."""
    logger.info("[w2] fleet_governance app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _governance():
        active_rules = []
        if pg:
            try:
                active_rules = pg.policy_list(active_only=True)
            except Exception:
                pass

        proposals_dir = _SAP_ROOT.parent / "governance" / "commits"
        proposals = []
        if proposals_dir.exists():
            proposals = [p.name for p in sorted(proposals_dir.glob("*.md"))[:20]]

        return {
            "active_rules":  active_rules,
            "rule_count":    len(active_rules),
            "proposals_dir": str(proposals_dir),
            "proposals":     proposals,
        }

    return await loop.run_in_executor(_executor, _governance)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_persona(app_id: str, agent: str = "willow") -> dict:
    """Look up an agent's persona profile location."""
    return {"agent": agent, "note": f"Persona profiles at agents/{agent}/AGENT_PROFILE.md"}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def fleet_base17(app_id: str, length: int = 5) -> dict:
    """Generate a BASE 17 ID."""
    return {"id": PgBridge.gen_id(length)}


@mcp.tool()
@sap_gate()
async def agent_create(
    app_id:      str,
    name:        str,
    trust:       str = "WORKER",
    role:        str = "",
    folder_root: str = "",
) -> dict:
    """Create a new registered agent with a SAFE manifest and folder structure."""
    logger.info("[w2] agent_create app_id=%s name=%s trust=%s", app_id, name, trust)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, pg.agent_create,
        name, trust, role, folder_root or None,
    )


# ── Tools — policy_ domain (S8) ──────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def policy_list(app_id: str, active_only: bool = True) -> dict:
    """List all policy rules. Read-only — any fleet_admin agent may call this."""
    logger.info("[w2] policy_list app_id=%s active_only=%s", app_id, active_only)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rules = await loop.run_in_executor(_executor, pg.policy_list, active_only)
    for r in rules:
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return {"rules": rules, "count": len(rules)}


@mcp.tool()
@sap_gate(write=True)
async def policy_put(
    app_id:     str,
    name:       str,
    rule_type:  str   = "warn",
    target:     str   = "*",
    action:     str   = "warn",
    threshold:  float = None,
    window_sec: int   = 3600,
) -> dict:
    """Create or update a policy rule. Restricted to heimdallr.
    rule_type: block | warn | limit
    target: tool name or '*' for all tools
    action: block | warn (what to do when rule fires)
    threshold: for limit rules — max calls per window_sec"""
    if app_id != "heimdallr":
        return {"error": "not_permitted", "message": "policy_put is restricted to heimdallr"}
    logger.info("[w2] policy_put app_id=%s name=%r rule_type=%s target=%s", app_id, name, rule_type, target)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    rule_id = await loop.run_in_executor(
        _executor, pg.policy_put,
        name, rule_type, target, action, threshold, window_sec, app_id,
    )
    # Invalidate middleware TTL cache so new rule takes effect immediately
    from sap.middleware import _policy_cache_lock
    import sap.middleware as _mw
    with _policy_cache_lock:
        _mw._policy_cache_ts = 0.0
    return {"id": rule_id, "name": name, "status": "upserted"}


@mcp.tool()
@sap_gate(write=True)
async def policy_delete(app_id: str, rule_id: str) -> dict:
    """Deactivate a policy rule by ID or name. Restricted to heimdallr."""
    if app_id != "heimdallr":
        return {"error": "not_permitted", "message": "policy_delete is restricted to heimdallr"}
    logger.info("[w2] policy_delete app_id=%s rule=%s", app_id, rule_id)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(_executor, pg.policy_delete, rule_id)
    import sap.middleware as _mw
    with _mw._policy_cache_lock:
        _mw._policy_cache_ts = 0.0
    return {"deactivated": ok, "rule_id": rule_id}


# ── Tools — voice_ domain (S9) ────────────────────────────────────────────────

def _split_identifier(name: str) -> list:
    """Port of splitIdentifier() from services/voiceKeyterms.ts.
    Splits camelCase, PascalCase, kebab-case, snake_case, and path segments."""
    import re
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return [w.strip() for w in re.split(r"[-_./\s]+", s)
            if 2 < len(w.strip()) <= 20]


_VOICE_GLOBAL_TERMS = [
    "MCP", "symlink", "grep", "regex", "localhost", "codebase",
    "TypeScript", "JSON", "OAuth", "webhook", "gRPC", "dotfiles",
    "subagent", "worktree", "Postgres", "Ollama", "mistral",
    "heimdallr", "hanuman", "willow", "SOIL", "SAFE",
]
_MAX_KEYTERMS = 50


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def voice_keyterms(
    app_id:       str,
    recent_paths: list = None,
) -> dict:
    """Build STT keyterms for voice input accuracy.
    Returns domain-specific vocabulary: global coding terms + project name + git branch + recent paths.
    Ported from services/voiceKeyterms.ts (Claude Code source)."""
    logger.info("[w2] voice_keyterms app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _build():
        import subprocess as _sp
        from os.path import basename as _bn
        terms: set = set(_VOICE_GLOBAL_TERMS)

        # Project root basename
        cwd = os.getcwd()
        proj_name = _bn(cwd)
        if 2 < len(proj_name) <= 50:
            terms.add(proj_name)

        # Git branch words
        try:
            branch = _sp.check_output(
                ["git", "branch", "--show-current"],
                cwd=cwd, stderr=_sp.DEVNULL, timeout=3,
            ).decode().strip()
            for w in _split_identifier(branch):
                terms.add(w)
        except Exception:
            pass

        # Recent file path words
        for path in (recent_paths or []):
            if len(terms) >= _MAX_KEYTERMS:
                break
            stem = _bn(path).rsplit(".", 1)[0]
            for w in _split_identifier(stem):
                terms.add(w)

        keyterms = list(terms)[:_MAX_KEYTERMS]
        return {"keyterms": keyterms, "count": len(keyterms)}

    return await loop.run_in_executor(_executor, _build)


# ── Tools — infer_7b (orin sub-agent) ────────────────────────────────────────

@mcp.tool()
@sap_gate()
async def infer_7b(
    app_id:     str,
    task_type:  str,
    content:    str  = "",
    context:    str  = "",
    categories: list = None,
    atom_a:     str  = "",
    atom_b:     str  = "",
) -> dict:
    """Run a structured task via mistral:7b (orin sub-agent). Synchronous.
    task_type: summarize | classify | extract | tension
    - summarize: content → {bullets, one_line}
    - classify:  content + categories → {category, confidence, reason}
    - extract:   content → {atoms: [{title, summary, category}]}
    - tension:   atom_a + atom_b → {conflict, score, reason}"""
    logger.info("[w2] infer_7b app_id=%s task_type=%s", app_id, task_type)
    loop = asyncio.get_running_loop()

    def _run():
        from agents.orin.tasks import run as orin_run
        payload: dict = {"content": content, "context": context}
        if categories:
            payload["categories"] = categories
        if atom_a:
            payload["atom_a"] = atom_a
        if atom_b:
            payload["atom_b"] = atom_b
        return orin_run(task_type, payload)

    return await loop.run_in_executor(_executor, _run)


# ── Tools — session_review (S10) ─────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def session_review(
    app_id:         str,
    lookback_hours: int  = 24,
    run_tension:    bool = True,
    model:          str  = "llama3.2:3b",
) -> dict:
    """Review recent session activity using a local Ollama model + receipt log.
    Summarises what was done, what succeeded/failed, and flags tensions.
    Mirrors /review (local PR diff) but for Willow sessions, not code PRs.
    model: Ollama model to use (default: llama3.2:3b; mistral:7b for deeper analysis)."""
    logger.info("[w2] session_review app_id=%s hours=%d tension=%s", app_id, lookback_hours, run_tension)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _review():
        from sap.clients.professor_client import _ask_ollama
        import psycopg2.extras as _pge

        # Fetch recent receipts
        receipts = []
        try:
            from core.pg_bridge import get_connection, release_connection
            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT ts, app_id, tool, ok, latency_ms, error_type"
                        " FROM willow.mcp_receipts"
                        " WHERE ts > now() - interval '1 hour' * %s"
                        " ORDER BY ts DESC LIMIT 100",
                        (lookback_hours,),
                    )
                    receipts = [dict(r) for r in cur.fetchall()]
            finally:
                release_connection(conn)
        except Exception as e:
            logger.warning("[w2] session_review: receipts fetch failed: %s", e)

        for r in receipts:
            if hasattr(r.get("ts"), "isoformat"):
                r["ts"] = r["ts"].isoformat()

        tool_counts: dict = {}
        errors = []
        for r in receipts:
            t = r.get("tool", "?")
            tool_counts[t] = tool_counts.get(t, 0) + 1
            if not r.get("ok") and r.get("error_type"):
                errors.append({"tool": t, "error": r["error_type"], "ts": r.get("ts")})

        # Fetch recent KB atoms
        recent_atoms = []
        try:
            pg._ensure_conn()
            with pg.conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, title, summary FROM knowledge"
                    " WHERE valid_at > now() - interval '1 hour' * %s"
                    "   AND invalid_at IS NULL"
                    " ORDER BY valid_at DESC LIMIT 20",
                    (lookback_hours,),
                )
                recent_atoms = [dict(r) for r in cur.fetchall()]
        except Exception:
            pass

        # Build review prompt
        tool_summary = ", ".join(f"{t}×{n}" for t, n in
                                 sorted(tool_counts.items(), key=lambda x: -x[1])[:10])
        atom_summary = "; ".join(a.get("title", "") for a in recent_atoms[:10])
        error_summary = "; ".join(f"{e['tool']}({e['error']})" for e in errors[:5]) or "none"

        prompt = (
            f"Session review (last {lookback_hours}h). "
            f"Tools called: {tool_summary or 'none'}. "
            f"Errors: {error_summary}. "
            f"New KB atoms: {atom_summary or 'none'}.\n\n"
            "Write a concise session review (3-5 bullet points):\n"
            "- What was accomplished\n- What succeeded or failed\n"
            "- Knowledge gaps or loose ends\n- Suggested next steps"
        )

        synthesis = ""
        try:
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as _llm_ex:
                _fut = _llm_ex.submit(
                    _ask_ollama,
                    model,
                    "You are a session analyst. Write concise, actionable reviews.",
                    prompt,
                )
                synthesis = _fut.result(timeout=120) or ""
        except _cf.TimeoutError:
            synthesis = "[review timed out — Ollama busy, retry later]"
        except Exception as e:
            synthesis = f"[review unavailable: {e}]"

        result: dict = {
            "review": synthesis.strip(),
            "lookback_hours": lookback_hours,
            "receipts_sampled": len(receipts),
            "tool_counts": tool_counts,
            "errors_found": len(errors),
            "new_kb_atoms": len(recent_atoms),
            "cited_receipts": [r.get("ts") for r in receipts[:5]],
        }

        # Tension scan inline if requested
        if run_tension:
            try:
                atoms = pg.knowledge_search("", limit=30)
                seen: set = set()
                for atom in atoms[:10]:
                    neighbors = pg.knowledge_search_semantic(atom.get("summary", ""), limit=3)
                    for nb in neighbors:
                        pk = tuple(sorted([atom.get("id", ""), nb.get("id", "")]))
                        if pk in seen:
                            continue
                        seen.add(pk)
                result["tension_pairs_checked"] = len(seen)
                result["tensions_hint"] = "run tension_scan for full report"
            except Exception:
                pass

        return result

    return await loop.run_in_executor(_executor, _review)


# ── Tools — env_ domain (S6) ─────────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def env_check(app_id: str, fork_id: str) -> dict:
    """Compare the current environment against the snapshot saved when fork_id was created.
    Surfaces additions, removals, and value changes for WILLOW_/GROVE_ vars."""
    logger.info("[w2] env_check app_id=%s fork=%s", app_id, fork_id)

    def _check():
        snapshot_rec = store.get(f"{app_id}/forks/{fork_id}/env", record_id="snapshot")
        if not snapshot_rec:
            return {"error": f"No env snapshot for fork {fork_id}. Was fork_create called by this app?"}
        snapshot: dict = snapshot_rec.get("data", snapshot_rec) if "data" in snapshot_rec else snapshot_rec
        current = {k: v for k, v in os.environ.items() if any(k.startswith(p) for p in _ENV_SNAPSHOT_PREFIXES)}
        added   = {k: current[k] for k in current if k not in snapshot}
        removed = {k: snapshot[k] for k in snapshot if k not in current}
        changed = {k: {"was": snapshot[k], "now": current[k]}
                   for k in current if k in snapshot and current[k] != snapshot[k]}
        return {
            "fork_id": fork_id,
            "added":   added,
            "removed": removed,
            "changed": changed,
            "clean":   not (added or removed or changed),
        }

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _check)


# ── Tools — diagnostic_summary (S4) ──────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def diagnostic_summary(
    app_id: str,
    path:   str  = ".",
    tool:   str  = "auto",
) -> dict:
    """Run ruff and/or mypy on path and return structured diagnostic output.
    Mirrors CC's DiagnosticTrackingService.formatDiagnosticsSummary pattern.
    tool: auto | ruff | mypy | both
    Baseline delta: compares against last run saved in SOIL (app_id/diag/baseline)."""
    logger.info("[w2] diagnostic_summary app_id=%s path=%s tool=%s", app_id, path, tool)
    loop = asyncio.get_running_loop()

    def _diag():
        import subprocess as _sp
        import json as _j
        import shutil as _sh

        results: dict = {"path": path, "tool": tool, "diagnostics": []}
        baseline_key = f"{app_id}/diag/baseline"

        def _run_ruff() -> list:
            if not _sh.which("ruff"):
                return []
            try:
                out = _sp.check_output(
                    ["ruff", "check", path, "--output-format=json", "--quiet"],
                    cwd=os.getcwd(), stderr=_sp.DEVNULL, timeout=30,
                )
                items = _j.loads(out.decode())
                return [{"file": i.get("filename"), "line": i.get("location", {}).get("row"),
                         "col": i.get("location", {}).get("column"),
                         "code": i.get("code"), "message": i.get("message"),
                         "severity": "Error" if i.get("code", "").startswith("E") else "Warning",
                         "source": "ruff"} for i in items]
            except _sp.CalledProcessError as e:
                try:
                    return [{"file": i.get("filename"), "line": i.get("location", {}).get("row"),
                             "code": i.get("code"), "message": i.get("message"),
                             "severity": "Warning", "source": "ruff"}
                            for i in _j.loads(e.output.decode())]
                except Exception:
                    return []
            except Exception:
                return []

        def _run_mypy() -> list:
            if not _sh.which("mypy"):
                return []
            try:
                out = _sp.check_output(
                    ["mypy", path, "--output=json", "--no-error-summary"],
                    cwd=os.getcwd(), stderr=_sp.STDOUT, timeout=60,
                )
                lines = out.decode().splitlines()
            except _sp.CalledProcessError as e:
                lines = e.output.decode().splitlines()
            except Exception:
                return []
            diags = []
            for line in lines:
                try:
                    item = _j.loads(line)
                    diags.append({
                        "file": item.get("file"), "line": item.get("line"),
                        "col": item.get("column"), "code": item.get("error_code"),
                        "message": item.get("message"),
                        "severity": "Error" if item.get("severity") == "error" else "Warning",
                        "source": "mypy",
                    })
                except Exception:
                    pass
            return diags

        use_ruff = tool in ("auto", "ruff", "both")
        use_mypy = tool in ("mypy", "both")

        all_diags = []
        if use_ruff:
            all_diags.extend(_run_ruff())
        if use_mypy:
            all_diags.extend(_run_mypy())

        # Baseline delta — subtract known diagnostics
        try:
            baseline_rec = store.get(baseline_key)
            baseline_diags = baseline_rec.get("diagnostics", []) if baseline_rec else []
        except Exception:
            baseline_diags = []

        baseline_sigs = {(d.get("file"), d.get("line"), d.get("code")) for d in baseline_diags}
        new_diags = [d for d in all_diags
                     if (d.get("file"), d.get("line"), d.get("code")) not in baseline_sigs]

        # Save current as new baseline
        try:
            store.put(baseline_key, {"diagnostics": all_diags})
        except Exception:
            pass

        # Format summary (mirrors formatDiagnosticsSummary)
        sev_sym = {"Error": "✗", "Warning": "⚠", "Info": "ℹ", "Hint": "★"}
        lines = []
        for d in new_diags[:50]:
            sym = sev_sym.get(d.get("severity", "Warning"), "·")
            lines.append(
                f"  {sym} [{d.get('file','?')}:{d.get('line','?')}] "
                f"{d.get('message','')} [{d.get('code','')}] ({d.get('source','')})"
            )

        results["diagnostics"] = new_diags
        results["total_found"] = len(all_diags)
        results["new_since_baseline"] = len(new_diags)
        results["summary"] = "\n".join(lines) if lines else "No new diagnostics."
        return results

    return await loop.run_in_executor(_executor, _diag)


# ── Tools — app_ domain (install / uninstall / list / status) ────────────────

_SAFE_APPS_DIR   = Path.home() / "github" / "SAFE" / "apps"
_SAFE_APP_REG    = Path(os.environ.get("WILLOW_SAFE_ROOT", str(Path.home() / "github" / "SAFE" / "Applications")))
_MONOREPO_ROOT   = Path.home() / "github" / "safe-app-store" / "apps"
_WILLOW2_ROOT    = Path(__file__).parent.parent
_MCP_TEMPLATE    = {
    "mcpServers": {
        "willow": {
            "type": "stdio",
            "command": "bash",
            "args": [str(_WILLOW2_ROOT / "sap" / "unified_mcp.sh")],
            "env": {
                "WILLOW_AGENT_NAME":   "__APP_ID__",
                "WILLOW_GROVE_ROOT":   str(Path.home() / "github" / "safe-app-willow-grove"),
                "WILLOW_PG_DB":        os.environ.get("WILLOW_PG_DB", "willow_20"),
                "WILLOW_SAFE_ROOT":    str(_SAFE_APP_REG),
            },
        }
    }
}


def _app_code_path(app_id: str) -> Path | None:
    mono = _MONOREPO_ROOT / app_id
    if mono.exists():
        return mono
    standalone = _SAFE_APPS_DIR / app_id
    if standalone.exists():
        return standalone
    return None


def _app_source(app_id: str) -> str:
    if (_MONOREPO_ROOT / app_id).exists():
        return "monorepo"
    if (_SAFE_APPS_DIR / app_id).exists():
        return "standalone"
    return "unknown"


def _mcp_points_at_willow(cfg: dict) -> tuple[bool, str]:
    """Return whether an app's Willow MCP server points at this Willow 2.0 tree."""
    server = cfg.get("mcpServers", {}).get("willow", {})
    command = str(server.get("command", ""))
    args = [str(arg) for arg in server.get("args", [])]
    command_line = " ".join([command] + args).strip()
    if not command_line:
        return False, "empty"
    ok = "willow-2.0" in command_line or "unified_mcp" in command_line
    if ok:
        return True, "willow-2.0"
    return False, f"stale: {command_line}"


@mcp.tool()
@sap_gate(write=True)
async def app_install(
    app_id:        str,
    target_app_id: str,
    repo_url:      str = "",
    source:        str = "standalone",
) -> dict:
    """Install a SAFE app into Willow.
    app_id: caller identity (for gate auth — use hanuman or your agent id).
    target_app_id: the app to install.
    source='standalone': clones repo_url to ~/SAFE/apps/<target_app_id>/.
    source='monorepo': code already at ~/safe-app-store/apps/<target_app_id>/.
    Registers manifest in SAFE_ROOT and updates the app's .mcp.json to Willow 2.0."""
    logger.info("[w2] app_install app_id=%s target=%s source=%s", app_id, target_app_id, source)
    loop = asyncio.get_running_loop()

    def _install():
        import subprocess as _sp
        tid = target_app_id

        _fetcher = "monorepo"
        if source == "monorepo":
            code_path = _MONOREPO_ROOT / tid
            if not code_path.exists():
                return {"error": f"monorepo path not found: {code_path}"}
        else:
            code_path = _SAFE_APPS_DIR / tid
            if code_path.exists():
                return {"error": f"already exists at {code_path} — uninstall first or use app_status"}
            if not repo_url:
                return {"error": "repo_url required for standalone install"}
            _SAFE_APPS_DIR.mkdir(parents=True, exist_ok=True)
            code_path.mkdir(parents=True, exist_ok=True)

            import shutil as _sh
            ghgrab = (
                _sh.which("ghgrab")
                or (_sh.which("ghgrab", path=os.path.expanduser("~/.cargo/bin")) and
                    os.path.expanduser("~/.cargo/bin/ghgrab"))
                or ""
            )
            if ghgrab:
                # Prefer ghgrab: downloads repo files without .git/ history.
                # Supports GitHub, GitLab, Codeberg, Gitea, Forgejo.
                _fetcher = "ghgrab"
                cmd = [ghgrab, "agent", "download", repo_url,
                       "--repo", "--out", str(code_path), "--no-folder"]
                token = os.environ.get("GITHUB_TOKEN", "")
                if token:
                    cmd += ["--token", token]
                result = _sp.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    try:
                        err_json = json.loads(result.stdout)
                        err_msg = err_json.get("error", result.stderr.strip())
                    except Exception:
                        err_msg = result.stderr.strip() or result.stdout.strip()
                    return {"error": f"ghgrab failed: {err_msg[:500]}"}
            else:
                # Fallback: full git clone (install ghgrab via `cargo install ghgrab` to avoid this)
                _fetcher = "git-clone"
                result = _sp.run(
                    ["git", "clone", repo_url, str(code_path)],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    _sh.rmtree(code_path, ignore_errors=True)
                    return {"error": f"git clone failed: {result.stderr.strip()[:500]}"}

        manifest_src = code_path / "safe-app-manifest.json"
        if not manifest_src.exists():
            return {"error": f"safe-app-manifest.json not found in {code_path}"}
        try:
            manifest_data = json.loads(manifest_src.read_text())
        except Exception as e:
            return {"error": f"manifest parse error: {e}"}

        reg_dir = _SAFE_APP_REG / tid
        reg_dir.mkdir(parents=True, exist_ok=True)
        reg_manifest = reg_dir / "safe-app-manifest.json"
        reg_manifest.write_text(json.dumps(manifest_data, indent=2))

        mcp_cfg = json.loads(json.dumps(_MCP_TEMPLATE))
        mcp_cfg["mcpServers"]["willow"]["env"]["WILLOW_AGENT_NAME"] = tid
        mcp_path = code_path / ".mcp.json"
        mcp_path.write_text(json.dumps(mcp_cfg, indent=2))

        return {
            "status":    "installed",
            "app_id":    tid,
            "code_path": str(code_path),
            "source":    source,
            "fetcher":   _fetcher,
            "manifest":  str(reg_manifest),
            "mcp_json":  str(mcp_path),
        }

    return await loop.run_in_executor(_executor, _install)


@mcp.tool()
@sap_gate(write=True)
async def app_uninstall(app_id: str, target_app_id: str, remove_code: bool = False) -> dict:
    """Uninstall a SAFE app from Willow.
    app_id: caller identity (for gate auth).
    target_app_id: the app to uninstall.
    Removes manifest from SAFE_ROOT. remove_code=True also removes standalone code dir."""
    logger.info("[w2] app_uninstall app_id=%s target=%s remove_code=%s", app_id, target_app_id, remove_code)
    loop = asyncio.get_running_loop()

    def _uninstall():
        import shutil as _sh
        tid = target_app_id

        reg_dir = _SAFE_APP_REG / tid
        if not reg_dir.exists():
            return {"error": f"app '{tid}' not registered in SAFE_ROOT"}

        _sh.rmtree(reg_dir)
        removed = {"manifest_dir": str(reg_dir)}

        if remove_code:
            src = _app_source(tid)
            if src == "standalone":
                code_path = _SAFE_APPS_DIR / tid
                _sh.rmtree(code_path, ignore_errors=True)
                removed["code_path"] = str(code_path)
            elif src == "monorepo":
                removed["code_note"] = "monorepo app — code left in place (never removed automatically)"

        return {"status": "uninstalled", "app_id": tid, "removed": removed}

    return await loop.run_in_executor(_executor, _uninstall)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def app_list(app_id: str) -> dict:
    """List all SAFE apps registered in SAFE_ROOT with their code location and source."""
    logger.info("[w2] app_list app_id=%s", app_id)
    loop = asyncio.get_running_loop()

    def _list():
        apps = []
        if not _SAFE_APP_REG.exists():
            return {"apps": [], "total": 0}
        for entry in sorted(_SAFE_APP_REG.iterdir()):
            manifest_path = entry / "safe-app-manifest.json"
            if not entry.is_dir() or not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                manifest = {}
            aid      = manifest.get("app_id", entry.name)
            src      = _app_source(aid)
            code     = _app_code_path(aid)
            apps.append({
                "app_id":      aid,
                "name":        manifest.get("name", aid),
                "version":     manifest.get("version", "?"),
                "source":      src,
                "code_path":   str(code) if code else None,
                "permissions": manifest.get("permissions", []),
            })
        return {"apps": apps, "total": len(apps)}

    return await loop.run_in_executor(_executor, _list)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def app_status(app_id: str, target_app_id: str = "") -> dict:
    """Check install status of a SAFE app: manifest, code location, .mcp.json validity."""
    logger.info("[w2] app_status app_id=%s target=%s", app_id, target_app_id)
    loop = asyncio.get_running_loop()

    def _status():
        tid = target_app_id or app_id
        reg_dir      = _SAFE_APP_REG / tid
        manifest_path = reg_dir / "safe-app-manifest.json"
        registered   = manifest_path.exists()
        manifest     = {}
        if registered:
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                pass

        src       = _app_source(tid)
        code_path = _app_code_path(tid)

        mcp_ok    = False
        mcp_note  = "not found"
        if code_path:
            mcp_file = code_path / ".mcp.json"
            if mcp_file.exists():
                try:
                    cfg   = json.loads(mcp_file.read_text())
                    mcp_ok, mcp_note = _mcp_points_at_willow(cfg)
                except Exception as e:
                    mcp_note = f"parse error: {e}"

        return {
            "app_id":     tid,
            "registered": registered,
            "source":     src,
            "code_path":  str(code_path) if code_path else None,
            "mcp_wired":  mcp_ok,
            "mcp_note":   mcp_note,
            "manifest":   manifest,
        }

    return await loop.run_in_executor(_executor, _status)


# ── Tools — code_graph domain ────────────────────────────────────────────────

_CODE_GRAPH_DB = Path(os.environ.get(
    "WILLOW_CODE_GRAPH_DB",
    str(_fleet_home() / "code_graph.db"),
))
_CODE_GRAPH_ROOT = Path(os.environ.get(
    "WILLOW_CODE_GRAPH_ROOT",
    str(Path(__file__).resolve().parent.parent),
))


@mcp.tool()
@sap_gate()
async def code_graph_index(
    app_id: str,
    repo_root: str = "",
    force: bool = False,
) -> dict:
    """Index Python files in repo_root into the symbol graph DB.
    Must be run once before other code_graph tools.
    repo_root defaults to WILLOW_CODE_GRAPH_ROOT env var (willow-2.0 root)."""
    root = Path(repo_root).resolve() if repo_root else _CODE_GRAPH_ROOT
    loop = asyncio.get_running_loop()

    def _run():
        from sap.code_graph.indexer import index_repo
        return index_repo(root, _CODE_GRAPH_DB, force=force)

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def code_graph_search(
    app_id: str,
    query: str,
    kinds: list = None,
    max_results: int = 20,
) -> dict:
    """Fuzzy symbol search: exact → prefix → contains → camelCase/snake_case token split.
    kinds: filter by symbol type — module|class|function|method (default: all)."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.code_graph.fuzzy import search_symbols
        results = search_symbols(_CODE_GRAPH_DB, query, max_results=max_results, kinds=kinds)
        return {"query": query, "count": len(results), "results": results}

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def code_graph_explain(app_id: str, symbol: str) -> dict:
    """Explain a symbol: signature, file location, callers, callees.
    symbol: name or fully-qualified name (e.g. 'advance' or 'sandbox.engine.advance')."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.code_graph.fuzzy import explain_symbol
        return explain_symbol(_CODE_GRAPH_DB, symbol)

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def code_graph_walk(
    app_id: str,
    anchor: str,
    hop_depth: int = 2,
    max_tokens: int = 8000,
) -> dict:
    """BFS from anchor symbol, collect context within token budget.
    Walks import + inheritance edges outward. Deterministic (alphabetical within each hop).
    anchor: symbol name or fqn. hop_depth: how many hops to walk (default 2).
    max_tokens: stop collecting when budget hit (default 8000 ≈ ~32k chars)."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.code_graph.walker import walk
        result = walk(_CODE_GRAPH_DB, anchor, hop_depth=hop_depth, max_tokens=max_tokens)
        return {
            "anchor_fqn":     result.anchor_fqn,
            "hops_traversed": result.hops_traversed,
            "tokens_returned": result.tokens_returned,
            "files":          result.files,
            "symbols":        result.symbols,
        }

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def code_graph_suggest(
    app_id: str,
    task: str,
    max_results: int = 10,
) -> dict:
    """Suggest files most relevant to a task description.
    Ranks by keyword overlap with symbol names + file paths. No embeddings, no LLM.
    task: natural language description of what you're about to do."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.code_graph.fuzzy import suggest_files
        files = suggest_files(_CODE_GRAPH_DB, task, max_results=max_results)
        return {"task": task[:100], "suggestions": files}

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def code_graph_impact(
    app_id: str,
    file_paths: list,
) -> dict:
    """Blast radius analysis: which files/symbols import from the given files?
    file_paths: list of repo-relative paths (e.g. ['sap/sap_mcp.py'])."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.code_graph.walker import analyze_impact
        return analyze_impact(_CODE_GRAPH_DB, file_paths)

    return await loop.run_in_executor(_executor, _run)


# ── Tools — cbm domain (codebase-memory-mcp bounded facade) ─────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cbm_status(app_id: str) -> dict:
    """Resolve indexed CBM project for this repo and surface F-001..F-008 guardrails."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.cbm_facade import LIMITATIONS, resolve_project
        resolved = resolve_project()
        return {
            "resolved": resolved,
            "limitations": LIMITATIONS,
            "usage": "Prefer cbm_* over raw codebase-memory-mcp; cross-check with cbm_verify_callers",
        }

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cbm_search(
    app_id: str,
    query: str,
    limit: int = 10,
    exclude_tests: bool = True,
    project: str = "",
) -> dict:
    """Bounded search_graph via codebase-memory-mcp CLI (F-003 LIMIT enforced)."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.cbm_facade import search
        return search(query, limit=limit, project=project, exclude_tests=exclude_tests)

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cbm_trace(
    app_id: str,
    function_name: str,
    direction: str = "both",
    depth: int = 3,
    include_tests: bool = False,
    project: str = "",
) -> dict:
    """Bounded trace_path — caps caller/callee lists (F-004/F-007 verify note attached)."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.cbm_facade import trace
        return trace(
            function_name,
            direction=direction,
            depth=depth,
            project=project,
            include_tests=include_tests,
        )

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cbm_query(
    app_id: str,
    query: str,
    max_rows: int = 25,
    project: str = "",
) -> dict:
    """Bounded query_graph — auto-appends LIMIT when missing (F-001/F-003)."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.cbm_facade import query as cbm_query_fn
        return cbm_query_fn(query, project=project, max_rows=max_rows)

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cbm_verify_callers(
    app_id: str,
    function_name: str,
    file_path: str = "",
    include_tests: bool = False,
    project: str = "",
) -> dict:
    """Graph inbound callers + ripgrep cross-check (F-004/F-007 dead-code guard)."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.cbm_facade import verify_callers
        return verify_callers(
            function_name,
            file_path=file_path,
            project=project,
            include_tests=include_tests,
        )

    return await loop.run_in_executor(_executor, _run)


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def cbm_reconcile(
    app_id: str,
    symbol: str,
    max_results: int = 5,
) -> dict:
    """Side-by-side CBM search + native code_graph explain for one symbol."""
    loop = asyncio.get_running_loop()

    def _run():
        from sap.cbm_facade import reconcile_symbol
        return reconcile_symbol(symbol, max_results=max_results)

    return await loop.run_in_executor(_executor, _run)


# ── Tools — session_query (S11) ──────────────────────────────────────────────

@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def session_query(
    app_id:   str,
    query:    str  = "stats",
    limit:    int  = 20,
    project:  str  = "",
) -> dict:
    """Query the session_index and session_messages tables.

    query options:
      "stats"       — aggregate stats across all sessions (default)
      "compaction"  — sessions with compaction_count > 0, sorted by file size
      "recent"      — most recent N sessions
      "search:<term>" — full-text search user messages for <term>
      "session:<id>"  — all messages for a specific session_id prefix

    project: filter to a specific project_dir substring (optional).
    """
    logger.info("[w2] session_query app_id=%s query=%r project=%r", app_id, query, project)
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()

    def _run():
        import psycopg2.extras as _pge
        from core.pg_bridge import get_connection, release_connection
        conn = get_connection()
        try:
            with conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
                proj_filter = f"%{project}%" if project else "%"

                if query == "stats":
                    cur.execute("""
                        SELECT
                            COUNT(*)                                AS total_sessions,
                            SUM(turn_count)                         AS total_turns,
                            SUM(user_message_count)                 AS total_messages,
                            ROUND(AVG(duration_minutes)::numeric,1) AS avg_duration_min,
                            ROUND(MAX(duration_minutes)::numeric,1) AS max_duration_min,
                            SUM(compaction_count)                   AS total_compactions,
                            COUNT(*) FILTER (WHERE compaction_count > 0) AS sessions_with_compaction,
                            ROUND(AVG(file_size_bytes/1024.0/1024.0)::numeric,2) AS avg_file_mb,
                            ROUND(MAX(file_size_bytes/1024.0/1024.0)::numeric,2) AS max_file_mb,
                            COUNT(DISTINCT project_dir)             AS project_count
                        FROM public.session_index
                        WHERE project_dir ILIKE %s
                    """, (proj_filter,))
                    return {"query": "stats", "result": dict(cur.fetchone())}

                elif query == "compaction":
                    cur.execute("""
                        SELECT
                            LEFT(session_id, 8)     AS session_id,
                            project_dir,
                            started_at::date        AS date,
                            turn_count,
                            user_message_count,
                            compaction_count,
                            ROUND((file_size_bytes/1024.0/1024.0)::numeric,2) AS file_mb,
                            ROUND(duration_minutes::numeric,0) AS duration_min
                        FROM public.session_index
                        WHERE compaction_count > 0
                          AND project_dir ILIKE %s
                        ORDER BY file_size_bytes DESC
                        LIMIT %s
                    """, (proj_filter, limit))
                    return {"query": "compaction", "results": [dict(r) for r in cur.fetchall()]}

                elif query == "recent":
                    cur.execute("""
                        SELECT
                            LEFT(session_id, 8)     AS session_id,
                            project_dir,
                            started_at::date        AS date,
                            turn_count,
                            user_message_count,
                            compaction_count,
                            ROUND((file_size_bytes/1024.0/1024.0)::numeric,2) AS file_mb,
                            ROUND(duration_minutes::numeric,0) AS duration_min
                        FROM public.session_index
                        WHERE project_dir ILIKE %s
                        ORDER BY started_at DESC
                        LIMIT %s
                    """, (proj_filter, limit))
                    return {"query": "recent", "results": [dict(r) for r in cur.fetchall()]}

                elif query.startswith("search:"):
                    term = query[7:].strip()
                    cur.execute("""
                        SELECT
                            LEFT(m.session_id, 8) AS session_id,
                            m.project_dir,
                            m.timestamp::date     AS date,
                            m.turn_index,
                            m.text
                        FROM public.session_messages m
                        WHERE to_tsvector('english', m.text) @@ plainto_tsquery('english', %s)
                          AND m.project_dir ILIKE %s
                        ORDER BY m.timestamp DESC
                        LIMIT %s
                    """, (term, proj_filter, limit))
                    return {"query": f"search:{term}", "results": [dict(r) for r in cur.fetchall()]}

                elif query.startswith("session:"):
                    sid_prefix = query[8:].strip()
                    cur.execute("""
                        SELECT turn_index, timestamp, text
                        FROM public.session_messages
                        WHERE session_id LIKE %s
                          AND project_dir ILIKE %s
                        ORDER BY turn_index
                        LIMIT %s
                    """, (f"{sid_prefix}%", proj_filter, limit))
                    return {"query": f"session:{sid_prefix}", "results": [dict(r) for r in cur.fetchall()]}

                else:
                    return {"error": f"Unknown query type: {query!r}. Use: stats|compaction|recent|search:<term>|session:<id>"}
        finally:
            release_connection(conn)

    return await loop.run_in_executor(_executor, _run)


# ── Tools — willow_ facade domain ─────────────────────────────────────────────

def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _looks_like_code_query(query: str) -> bool:
    q = query.lower()
    markers = (".py", ".ts", ".tsx", ".js", "/", "::", "def ", "class ", "function ", "symbol")
    return any(m in q for m in markers)


def _grove_search_simple(query: str, channel_name: str = "", limit: int = 10) -> list[dict]:
    try:
        from sap import grove_tools as _gt
        if not getattr(_gt, "_GROVE_AVAILABLE", False):
            return [{"error": "Grove package not available"}]
        conn = _gt.db.get_connection()
        try:
            channel_id = None
            if channel_name:
                channels = _gt.db.list_channels(conn)
                ch = next((c for c in channels if c["name"] == channel_name), None)
                channel_id = ch["id"] if ch else None
            msgs = _gt.db.search_messages(conn, query, channel_id=channel_id)
            return [
                {
                    "id": m.get("id"),
                    "sender": m.get("sender"),
                    "content": m.get("content"),
                    "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                }
                for m in msgs[:limit]
            ]
        finally:
            _gt.db.release_connection(conn)
    except Exception as e:
        return [{"error": str(e)}]


def _grove_inbox_simple(agent: str, since_id: int = 0, limit: int = 10) -> list[dict]:
    try:
        from sap import grove_tools as _gt
        if not getattr(_gt, "_GROVE_AVAILABLE", False):
            return [{"error": "Grove package not available"}]
        conn = _gt.db.get_connection()
        try:
            target = agent or os.getenv("GROVE_SENDER") or os.getenv("GROVE_NAME") or _MCP_AGENT
            msgs = _gt.db.inbox(conn, target, since_id=since_id, limit=limit)
            return [
                {
                    "id": m.get("id"),
                    "channel": m.get("channel"),
                    "sender": m.get("sender"),
                    "content": m.get("content"),
                    "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                }
                for m in msgs[:limit]
            ]
        finally:
            _gt.db.release_connection(conn)
    except Exception as e:
        return [{"error": str(e)}]


def _grove_send_simple(channel_name: str, content: str, sender: str) -> dict:
    try:
        from sap import grove_tools as _gt
        if not getattr(_gt, "_GROVE_AVAILABLE", False):
            return {"error": "Grove package not available"}
        conn = _gt.db.get_connection()
        try:
            channels = _gt.db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                ch = _gt.db.create_channel(conn, name=channel_name, channel_type="group")
            msg = _gt.db.send_message(conn, channel_id=ch["id"], sender=sender, content=content)
            return {"id": msg["id"], "channel": channel_name, "sent": True}
        finally:
            _gt.db.release_connection(conn)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_status(app_id: str, level: str = "quick", target_app_id: str = "") -> dict:
    """Facade: answer "is Willow healthy?" with one status entry point.

    level: quick|health|system|identity|app|diagnostic.
    """
    level = (level or "quick").strip().lower()
    if level == "health":
        result = await fleet_health(app_id=app_id)
    elif level == "system":
        result = await fleet_system_status(app_id=app_id)
    elif level == "identity":
        result = await fleet_identity_status(app_id=app_id)
    elif level == "app":
        result = await app_status(app_id=app_id, target_app_id=target_app_id)
    elif level == "diagnostic":
        result = await diagnostic_summary(app_id=app_id)
    else:
        result = await fleet_status(app_id=app_id)
    return {"facade": "willow_status", "level": level, "backend": level if level != "quick" else "fleet_status", "result": result}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_attention(app_id: str, limit: int = 10) -> dict:
    """Facade: what needs attention — inbox, flags, nest, kart, dream (desk cockpit)."""
    from willow.fylgja.desk_attention import attention_as_dict, fetch_attention_summary

    loop = asyncio.get_running_loop()
    inbox = await loop.run_in_executor(_executor, _grove_inbox_simple, app_id, 0, limit)
    summary = fetch_attention_summary(inbox=inbox)
    return {
        "facade": "willow_attention",
        "summary": attention_as_dict(summary),
        "headline": " · ".join(summary.lines),
    }


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def human_required_queue_list(
    app_id: str,
    status: str = "open",
    kind: str = "",
    limit: int = 20,
) -> dict:
    """List human-required queue items: consent, attestation, review, overload, onboarding."""
    if pg is None:
        return {"error": "postgres not connected"}
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(
        _executor,
        pg.human_required_list,
        status,
        kind or None,
        limit,
    )
    stats = await loop.run_in_executor(_executor, pg.human_required_stats)
    return {"items": rows, "count": len(rows), "stats": stats}


@mcp.tool()
@sap_gate()
async def human_required_queue_enqueue(
    app_id: str,
    kind: str,
    title: str,
    summary: str = "",
    priority: str = "normal",
    source_ref: str = "",
    assignee: str = "",
) -> dict:
    """Enqueue work that must pause automation until a human acts."""
    if pg is None:
        return {"error": "postgres not connected"}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: pg.human_required_enqueue(
            kind=kind,
            title=title,
            summary=summary,
            priority=priority,
            source_agent=app_id,
            source_ref=source_ref,
            assignee=assignee,
        ),
    )


@mcp.tool()
@sap_gate()
async def human_required_queue_resolve(
    app_id: str,
    item_id: str,
    status: str = "resolved",
    note: str = "",
) -> dict:
    """Resolve, dismiss, or acknowledge a human-required queue item."""
    if pg is None:
        return {"error": "postgres not connected"}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: pg.human_required_resolve(
            item_id,
            resolved_by=app_id,
            status=status,
            note=note,
        ),
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def human_attestation_list(
    app_id: str,
    subject_id: str = "",
    subject_type: str = "",
    status: str = "",
    limit: int = 20,
) -> dict:
    """List durable human attestation records."""
    if pg is None:
        return {"error": "postgres not connected"}
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(
        _executor,
        pg.human_attestation_list,
        subject_id,
        subject_type,
        status,
        limit,
    )
    return {"items": rows, "count": len(rows)}


@mcp.tool()
@sap_gate()
async def human_attestation_create(
    app_id: str,
    subject_id: str,
    subject_type: str = "knowledge_atom",
    statement: str = "",
    status: str = "attested",
    attested_by: str = "operator",
    evidence_ref: str = "",
) -> dict:
    """Create a durable human attestation/rejection/change-request record."""
    if pg is None:
        return {"error": "postgres not connected"}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: pg.human_attestation_create(
            subject_id=subject_id,
            subject_type=subject_type,
            status=status,
            attested_by=attested_by,
            agent=app_id,
            statement=statement,
            evidence_ref=evidence_ref,
        ),
    )


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_find(
    app_id: str,
    query: str,
    scope: str = "auto",
    limit: int = 5,
) -> dict:
    """Facade: find knowledge, state, handoffs, sessions, code, messages, or sources.

    scope: auto|kb|state|handoff|sessions|code|messages|external|all.
    """
    scope = (scope or "auto").strip().lower()
    routes: list[str]
    if scope == "all":
        routes = ["kb", "state", "handoff", "sessions", "code", "messages", "external"]
    elif scope == "auto":
        routes = ["kb", "state", "handoff"]
        if _looks_like_code_query(query):
            routes.append("code")
    else:
        routes = [scope]

    results: dict[str, object] = {}
    for route in routes:
        if route in {"kb", "memory"}:
            results["kb"] = await kb_search(app_id=app_id, query=query, limit=limit)
        elif route in {"state", "soil"}:
            results["state"] = await soil_search_all(app_id=app_id, query=query)
        elif route == "handoff":
            results["handoff"] = await handoff_search(app_id=app_id, query=query, limit=limit)
        elif route in {"sessions", "session"}:
            results["sessions"] = await session_query(app_id=app_id, query=f"search:{query}", limit=limit)
        elif route == "code":
            results["code"] = await code_graph_search(app_id=app_id, query=query, max_results=limit)
        elif route in {"messages", "grove"}:
            loop = asyncio.get_running_loop()
            results["messages"] = await loop.run_in_executor(_executor, _grove_search_simple, query, "", limit)
        elif route in {"external", "sources", "jeles"}:
            results["external"] = await mem_jeles_web_search(app_id=app_id, query=query, limit=limit)
        elif route == "opus":
            results["opus"] = await index_search(app_id=app_id, query=query, limit=limit)
        else:
            results[route] = {"error": f"unknown scope {route!r}"}
    # Per-scope taint tags (ADR-20260702 step 2, advisory). SOIL, handoffs,
    # sessions, and grove messages have no sensitivity structure yet →
    # sensitive-by-default; code (public repo) and external (public web) are
    # open; kb reports its own computed taint.
    from core.canonical_lanes import max_sensitivity
    _SCOPE_TAINT_DEFAULTS = {
        "state": "sensitive", "handoff": "sensitive",
        "sessions": "sensitive", "messages": "sensitive",
        "code": "open", "external": "open", "opus": "sensitive",
    }
    by_scope = {}
    for key in results:
        if key == "kb":
            kb_res = results["kb"]
            by_scope["kb"] = kb_res.get("taint", "sensitive") if isinstance(kb_res, dict) else "sensitive"
        else:
            by_scope[key] = _SCOPE_TAINT_DEFAULTS.get(key, "sensitive")
    taint = {"overall": max_sensitivity(by_scope.values()), "by_scope": by_scope}
    return {"facade": "willow_find", "scope": scope, "routes": routes,
            "results": results, "taint": taint}


@mcp.tool()
@sap_gate(write=True)
async def willow_remember(
    app_id: str,
    content: str,
    kind: str = "observation",
    title: str = "",
    source: str = "willow_remember",
    confidence: float = 0.80,
    tags: list = None,
) -> dict:
    """Facade: store a note, decision, context, or observation in the right lane.

    kind: observation|note|task|decision|context|journal.
    """
    kind = (kind or "observation").strip().lower()
    tags = _as_list(tags)
    if kind == "decision":
        result = await ledger_write(
            app_id=app_id,
            project=app_id,
            event_type="decision",
            content={"title": title, "content": content, "source": source, "tags": tags},
        )
        backend = "ledger_write"
    elif kind == "context":
        result = await context_save(app_id=app_id, content=content, category=title or "context")
        backend = "context_save"
    elif kind == "journal":
        result = await kb_journal(app_id=app_id, entry=content, domain=app_id)
        backend = "kb_journal"
    else:
        result = await intake_write(
            app_id=app_id,
            content=content,
            source=source,
            tier="frontier" if kind in {"observation", "note", "task"} else "contested",
            confidence=confidence,
            tags=tags,
            title=title,
            namespace=app_id,
            category=kind,
        )
        backend = "intake_write"
    return {"facade": "willow_remember", "kind": kind, "backend": backend, "result": result}


async def _willow_run_detached(
    *,
    app_id: str,
    task: str,
    script_body: str,
    script_name: str,
    allow_net: bool,
    allow_localhost: bool = False,
) -> dict:
    """Launch a long job on the detached lane (no daemon timeout). Helper for willow_run."""
    if not pg:
        return _no_pg()
    loop = asyncio.get_running_loop()
    try:
        from willow.fylgja.kart_queue import prepare_task_command

        cmd, script_path = prepare_task_command(
            task, script_body=script_body, script_name=script_name
        )
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"prepare task: {e}"}

    from core.kart_task_scan import check_kart_task

    blocked = check_kart_task(cmd, script_body=script_body)
    if blocked:
        return blocked

    from core.kart_detached import launch_detached

    handle = await loop.run_in_executor(
        _executor,
        lambda: launch_detached(cmd, allow_net=allow_net, allow_localhost=allow_localhost),
    )
    _rl_log_event("task_submit", ref=handle.get("task_id"))
    if script_path:
        handle["script_path"] = script_path
    handle["poll"] = "willow_run(task_id=<task_id>)"
    return {"facade": "willow_run", "backend": "kart_detached", "submitted": handle}


@mcp.tool()
@sap_gate()
async def willow_run(
    app_id: str,
    task: str = "",
    script_body: str = "",
    script_name: str = "",
    task_id: str = "",
    run_now: bool = False,
    allow_net: bool = False,
    allow_localhost: bool = False,
    agent: str = "kart",
    detached: bool = False,
) -> dict:
    """Facade: run or inspect local work through Kart.

    allow_localhost=True grants loopback-only network (host Ollama /
    embedder at localhost:11434) WITHOUT credential env vars — narrower
    than allow_net; prefer it for embedding/semantic work in the sandbox.

    detached=True launches the job in a new session with NO timeout, bypassing the
    kart daemon's 30-min kill (KART_DAEMON_TIMEOUT). Use for genuinely long jobs —
    benchmark sweeps, full LoCoMo runs, migrations. Returns a task_id immediately;
    poll progress with willow_run(task_id=...). Ordinary jobs should NOT use this —
    the daemon timeout is what kills hangs fast.
    """
    if task_id:
        loop = asyncio.get_running_loop()
        from core.kart_detached import detached_status, is_detached

        if await loop.run_in_executor(_executor, is_detached, task_id):
            result = await loop.run_in_executor(_executor, detached_status, task_id)
            return {"facade": "willow_run", "backend": "kart_detached", "result": result}
        result = await agent_task_status(app_id=app_id, task_id=task_id)
        return {"facade": "willow_run", "backend": "agent_task_status", "result": result}
    if not task and not script_body:
        result = await agent_task_list(app_id=app_id, agent=agent)
        return {"facade": "willow_run", "backend": "agent_task_list", "result": result}

    if detached:
        return await _willow_run_detached(
            app_id=app_id, task=task, script_body=script_body,
            script_name=script_name, allow_net=allow_net,
            allow_localhost=allow_localhost,
        )

    submitted = await agent_task_submit(
        app_id=app_id,
        task=task,
        script_body=script_body,
        script_name=script_name,
        agent=agent,
        submitted_by=app_id,
        allow_net=allow_net,
        allow_localhost=allow_localhost,
    )
    if run_now and not submitted.get("error"):
        from sap.willow_run_compact import compact_willow_run_outcome

        # kart_task_run drains the whole pending backlog, not just this task —
        # compact to one stdout copy (no submitted + run.results + status triple).
        run_payload = await kart_task_run(app_id=app_id, agent=agent)
        tid = submitted.get("task_id")
        status_row = None
        if tid and not any(
            r.get("task_id") == tid for r in (run_payload.get("results") or [])
        ):
            status_row = await agent_task_status(app_id=app_id, task_id=tid)
        return compact_willow_run_outcome(submitted, run_payload, status_row)
    return {"facade": "willow_run", "backend": "agent_task_submit", "submitted": submitted}


@mcp.tool()
@sap_gate()
async def willow_delegate(
    app_id: str,
    prompt: str,
    to: str = "",
    mode: str = "route",
    priority: str = "normal",
) -> dict:
    """Facade: route or dispatch work to another reasoning agent."""
    mode = (mode or "route").strip().lower()
    if mode == "dispatch" or to:
        result = await agent_dispatch(app_id=app_id, to=to, prompt=prompt, priority=priority, reply_to=app_id)
        backend = "agent_dispatch"
    else:
        result = await agent_route(app_id=app_id, message=prompt)
        backend = "agent_route"
    return {"facade": "willow_delegate", "backend": backend, "result": result}


@mcp.tool()
@sap_gate()
async def willow_work(
    app_id: str,
    action: str = "status",
    fork_id: str = "",
    title: str = "",
    note: str = "",
) -> dict:
    """Facade: manage a bounded unit of work.

    action: create|status|log|list.
    """
    action = (action or "status").strip().lower()
    if action == "create":
        result = await fork_create(app_id=app_id, title=title or note or "Willow work", created_by=app_id, topic=note)
        backend = "fork_create"
    elif action == "log":
        result = await fork_log(app_id=app_id, fork_id=fork_id, component=app_id, type="note", ref=title or "note", description=note)
        backend = "fork_log"
    elif action == "list":
        result = await fork_list(app_id=app_id)
        backend = "fork_list"
    else:
        result = await fork_status(app_id=app_id, fork_id=fork_id) if fork_id else await handoff_latest(app_id=app_id, agent=app_id)
        backend = "fork_status" if fork_id else "handoff_latest"
    return {"facade": "willow_work", "backend": backend, "result": result}


@mcp.tool()
@sap_gate()
async def willow_message(
    app_id: str,
    action: str = "inbox",
    content: str = "",
    channel_name: str = "hanuman",
    query: str = "",
    since_id: int = 0,
    limit: int = 10,
) -> dict:
    """Facade: read, search, or send Grove messages."""
    action = (action or "inbox").strip().lower()
    loop = asyncio.get_running_loop()
    if action == "send":
        result = await loop.run_in_executor(_executor, _grove_send_simple, channel_name, content, app_id)
        backend = "grove_send_message"
    elif action == "search":
        result = await loop.run_in_executor(_executor, _grove_search_simple, query or content, channel_name, limit)
        backend = "grove_search"
    else:
        result = await loop.run_in_executor(_executor, _grove_inbox_simple, app_id, since_id, limit)
        backend = "grove_inbox"
    return {"facade": "willow_message", "backend": backend, "result": result}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_app(app_id: str, action: str = "status", target_app_id: str = "") -> dict:
    """Facade: inspect SAFE app registration and manifest state."""
    action = (action or "status").strip().lower()
    if action == "list":
        result = await app_list(app_id=app_id)
        backend = "app_list"
    else:
        result = await app_status(app_id=app_id, target_app_id=target_app_id)
        backend = "app_status"
    return {"facade": "willow_app", "backend": backend, "result": result}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_external(
    app_id: str,
    query: str = "",
    text: str = "",
    url: str = "",
    mode: str = "ask",
    sources: list = None,
    limit: int = 2,
    wrap: bool = True,
) -> dict:
    """Facade: ask, search, verify, or fetch cited external sources (Jeles / guarded fetch)."""
    mode = (mode or "ask").strip().lower()
    sources = _as_list(sources)
    if mode == "fetch":
        target = (url or query or text or "").strip()
        result = await willow_web_fetch(app_id=app_id, url=target, wrap=wrap)
        backend = "willow_web_fetch"
    elif mode == "verify":
        result = await source_trail_verify(app_id=app_id, text=text or query, sources=sources)
        backend = "source_trail_verify"
    elif mode == "search":
        result = await mem_jeles_web_search(app_id=app_id, query=query or text, sources=sources, limit=limit)
        backend = "mem_jeles_web_search"
    else:
        result = await mem_jeles_ask(app_id=app_id, question=query or text, sources=sources, limit=limit)
        backend = "mem_jeles_ask"
    return {"facade": "willow_external", "backend": backend, "result": result}


@mcp.tool(annotations={"readOnlyHint": True})
@sap_gate()
async def willow_code(
    app_id: str,
    query: str,
    mode: str = "search",
    max_results: int = 10,
) -> dict:
    """Facade: search or suggest code context."""
    mode = (mode or "search").strip().lower()
    if mode == "suggest":
        result = await code_graph_suggest(app_id=app_id, task=query, max_results=max_results)
        backend = "code_graph_suggest"
    elif mode in ("cbm", "graph"):
        result = await cbm_search(app_id=app_id, query=query, limit=max_results)
        backend = "cbm_search"
    elif mode == "reconcile":
        result = await cbm_reconcile(app_id=app_id, symbol=query, max_results=max_results)
        backend = "cbm_reconcile"
    elif mode == "verify":
        result = await cbm_verify_callers(app_id=app_id, function_name=query)
        backend = "cbm_verify_callers"
    else:
        result = await code_graph_search(app_id=app_id, query=query, max_results=max_results)
        backend = "code_graph_search"
    return {"facade": "willow_code", "backend": backend, "result": result}


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=f"SAP MCP Server {VERSION}")
    ap.add_argument("--http",  action="store_true", help="Run streamable-HTTP instead of stdio")
    ap.add_argument("--port",  type=int, default=6274, help="HTTP port (default: 6274)")
    ap.add_argument("--host",  default="127.0.0.1",   help="HTTP host (default: 127.0.0.1)")
    args = ap.parse_args()

    if args.http:
        from sap.security_middleware import verify_transport, wrap_streamable_http_app

        if not verify_transport("http", host=args.host):
            sys.exit(1)
        if os.environ.get("WILLOW_MCP_API_KEY", "").strip():
            _orig_streamable_http_app = mcp.streamable_http_app

            def _streamable_http_app_with_api_key():
                return wrap_streamable_http_app(_orig_streamable_http_app())

            mcp.streamable_http_app = _streamable_http_app_with_api_key  # type: ignore[method-assign]
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
