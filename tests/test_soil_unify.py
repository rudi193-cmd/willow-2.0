"""Tests for the SOIL layout unification (2026-06-12).

Covers: the core/soil.py shim over WillowStore, the hard reject of legacy
'/store' addressing, and scripts/soil_merge_layouts.py.
"""
import json
import sqlite3

import pytest

from core.willow_store import WillowStore
from scripts.soil_merge_layouts import find_legacy_stores, merge_one


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return tmp_path


# ── shim ──────────────────────────────────────────────────────────────────────

def test_shim_roundtrip_writes_canonical_layout(store_root):
    import core.soil as soil
    soil.put("hanuman/desk", "rec-1", {"note": "unified"})
    # canonical file, not the legacy dir layout
    assert (store_root / "hanuman" / "desk.db").exists()
    assert not (store_root / "hanuman" / "desk" / "store.db").exists()
    rec = soil.get("hanuman/desk", "rec-1")
    assert rec["note"] == "unified"
    assert rec["_id"] == "rec-1"
    assert [r["note"] for r in soil.all_records("hanuman/desk")] == ["unified"]


def test_shim_sees_willowstore_writes(store_root):
    import core.soil as soil
    WillowStore().put("willow/flags", {"title": "x"}, record_id="flag-1")
    assert soil.get("willow/flags", "flag-1")["title"] == "x"


# ── hard reject ───────────────────────────────────────────────────────────────

def test_store_suffix_rejected(store_root):
    ws = WillowStore()
    with pytest.raises(ValueError, match="store"):
        ws.put("hanuman/atoms/store", {"id": "a1"})
    with pytest.raises(ValueError):
        ws.get("hanuman/atoms/store", "a1")


def test_archive_store_paths_still_readable(store_root):
    ws = WillowStore()
    ws.put("_archive/2026-06-10/ci/gaps/store", {"id": "g1", "x": 1})
    assert ws.get("_archive/2026-06-10/ci/gaps/store", "g1")["x"] == 1


# ── merge script ──────────────────────────────────────────────────────────────

def _make_legacy(root, collection, rows):
    d = root / collection
    d.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(d / "store.db"))
    conn.execute("""
        CREATE TABLE records (
            id TEXT PRIMARY KEY, data TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            deleted INTEGER DEFAULT 0
        )
    """)
    for rid, data, ts in rows:
        conn.execute("INSERT INTO records VALUES (?, ?, ?, ?, 0)",
                     (rid, json.dumps(data), ts, ts))
    conn.commit()
    conn.close()


def test_merge_moves_rows_and_archives_source(store_root):
    _make_legacy(store_root, "hanuman/atoms",
                 [("a1", {"v": 1}, "2026-06-01T00:00:00"),
                  ("a2", {"v": 2}, "2026-06-02T00:00:00")])
    src = store_root / "hanuman/atoms/store.db"
    rep = merge_one(src, store_root, apply=True)
    assert rep["inserted"] == 2 and not rep["collisions"]
    assert not src.exists()
    assert (store_root / "hanuman/atoms/store.db.migrated-" ).parent.glob("store.db.migrated-*")
    ws = WillowStore()
    assert ws.get("hanuman/atoms", "a1")["v"] == 1
    assert find_legacy_stores(store_root) == []


def test_merge_collision_newer_updated_at_wins(store_root):
    ws = WillowStore()
    ws.put("willow/flags", {"id": "f1", "v": "canonical"})  # updated_at = now
    _make_legacy(store_root, "willow/flags",
                 [("f1", {"v": "legacy-old"}, "2020-01-01T00:00:00")])
    rep = merge_one(store_root / "willow/flags/store.db", store_root, apply=True)
    assert rep["collisions"][0]["winner"] == "target"
    assert ws.get("willow/flags", "f1")["v"] == "canonical"


def test_merge_dry_run_changes_nothing(store_root):
    _make_legacy(store_root, "willow/atoms", [("a1", {"v": 1}, "2026-06-01T00:00:00")])
    src = store_root / "willow/atoms/store.db"
    rep = merge_one(src, store_root, apply=False)
    assert rep["inserted"] == 1
    assert src.exists()
    target = store_root / "willow/atoms.db"
    if target.exists():
        conn = sqlite3.connect(str(target))
        assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
        conn.close()


def test_find_legacy_skips_archive(store_root):
    _make_legacy(store_root, "_archive/2026-06-10/old", [("x", {}, "2026-01-01")])
    _make_legacy(store_root, "live/coll", [("y", {}, "2026-01-01")])
    found = find_legacy_stores(store_root)
    assert [p.parent.name for p in found] == ["coll"]


def test_merge_archives_empty_husks(store_root):
    # 0-row legacy stores must still archive, or --verify stays red forever
    _make_legacy(store_root, "willow/gaps", [])
    src = store_root / "willow/gaps/store.db"
    rep = merge_one(src, store_root, apply=True)
    assert rep["rows"] == 0 and rep["inserted"] == 0
    assert not src.exists()
    assert find_legacy_stores(store_root) == []
