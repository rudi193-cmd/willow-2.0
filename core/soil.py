"""soil.py — compat shim over WillowStore (SOIL layout unification, 2026-06-12).
b17: WDASH  ΔΣ=42

Historically this module wrote `{collection}/store.db` while the MCP layer
(`core/willow_store.py`) wrote `{collection}.db` — the same logical collection
landed in two files depending on the caller (flag-soil-dual-layout-divergence).
Per operator decision the WillowStore layout is canonical; this module keeps
its old 5-function API but delegates every operation to WillowStore.

Legacy `{collection}/store.db` files are merged by scripts/soil_merge_layouts.py
and the `<name>/store` addressing is hard-rejected by WillowStore.
"""
import sqlite3
from pathlib import Path

from core.willow_store import WillowStore

_store: WillowStore | None = None


def _get_store() -> WillowStore:
    global _store
    if _store is None:
        _store = WillowStore()
    return _store


def _root() -> Path:
    return _get_store().root


def _db(collection: str) -> Path:
    """Canonical sqlite file for a collection ({collection}.db)."""
    return _get_store()._db_path(collection)


def put(collection: str, record_id: str, record: dict) -> None:
    """Insert or update a record. Safe to call multiple times (upsert)."""
    _get_store().put(collection, record, record_id=record_id)


def get(collection: str, record_id: str) -> dict | None:
    rec = _get_store().get(collection, record_id)
    if rec is None:
        return None
    rec.setdefault("_id", record_id)
    return rec


def all_records(collection: str) -> list[dict]:
    out = []
    for rec in _get_store().list(collection):
        rec.setdefault("_id", rec.get("id") or rec.get("_soil_id"))
        out.append(rec)
    return out


def stats() -> dict:
    return _get_store().stats()


def query(collection: str, sql: str) -> list[tuple]:
    """Run a raw SQL query against a SOIL collection's canonical db."""
    try:
        db = _db(collection)
    except ValueError:
        return []
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(sql).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


def query_one(collection: str, sql: str) -> tuple | None:
    rows = query(collection, sql)
    return rows[0] if rows else None
