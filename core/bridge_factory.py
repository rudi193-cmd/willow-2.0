#!/usr/bin/env python3
"""
bridge_factory.py — Return the right bridge for this environment. b17: BFCT1 ΔΣ=42

    WILLOW_BACKEND=sqlite                         → SqliteBridge (~/.willow/willow.db)
    WILLOW_BACKEND=postgres                        → PgBridge (willow_20)
    unset (auto)                                   → PgBridge; raises on failure unless
                                                     WILLOW_ALLOW_SQLITE_FALLBACK=1 is set
    unset + WILLOW_ALLOW_SQLITE_FALLBACK=1         → PgBridge, fall back to SqliteBridge

Usage:
    from core.bridge_factory import get_bridge
    bridge = get_bridge()
"""
import os
import sys

_BACKEND = os.environ.get("WILLOW_BACKEND", "auto").lower()
_ALLOW_SQLITE_FALLBACK = os.environ.get("WILLOW_ALLOW_SQLITE_FALLBACK", "").strip() == "1"


def get_bridge():
    """Return a PgBridge or SqliteBridge depending on WILLOW_BACKEND and availability."""
    if _BACKEND == "sqlite":
        from core.sqlite_bridge import SqliteBridge
        return SqliteBridge()

    if _BACKEND == "postgres":
        from core.pg_bridge import PgBridge
        return PgBridge()

    # auto — try Postgres first
    try:
        from core.pg_bridge import try_connect, PgBridge
        conn = try_connect()
        if conn:
            conn.close()
            return PgBridge()
    except Exception:
        pass

    if _ALLOW_SQLITE_FALLBACK:
        print("[bridge_factory] Postgres unavailable — falling back to SQLite (WILLOW_ALLOW_SQLITE_FALLBACK=1)", file=sys.stderr)
        from core.sqlite_bridge import SqliteBridge
        return SqliteBridge()

    raise RuntimeError(
        "Postgres is unreachable and WILLOW_ALLOW_SQLITE_FALLBACK is not set. "
        "Set WILLOW_BACKEND=sqlite to use SQLite explicitly, or set "
        "WILLOW_ALLOW_SQLITE_FALLBACK=1 to allow automatic fallback."
    )


def backend_name() -> str:
    bridge = get_bridge()
    name = type(bridge).__name__
    try:
        bridge.close()
    except Exception:
        pass
    return name
