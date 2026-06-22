#!/usr/bin/env python3
"""soil_merge_layouts.py — merge legacy {collection}/store.db files into the
canonical {collection}.db layout (SOIL layout unification, 2026-06-12).

Diagnosis: docs/audits/SOIL_DUAL_LAYOUT_DIAGNOSIS_2026-06-12.md
Operator decisions: Layer A ({collection}.db / WillowStore) canonical; merge in
one session; '/store' addressing hard-rejected afterward (core/willow_store.py).

Policy:
  * additive — INSERT into the target; on id collision the row with the newer
    updated_at wins, collisions are logged
  * archive, never delete — each merged source is renamed to
    store.db.migrated-<date>; --finalize later moves husks under _archive/
  * column map: legacy created_at -> canonical created

Usage:
    python3 scripts/soil_merge_layouts.py              # dry-run (default)
    python3 scripts/soil_merge_layouts.py --apply      # perform the merge
    python3 scripts/soil_merge_layouts.py --verify     # exit 1 if any live
                                                       # store.db remains
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from willow.fylgja.willow_home import resolve_store_root  # noqa: E402

_TARGET_SCHEMA = """
    CREATE TABLE IF NOT EXISTS records (
        id         TEXT PRIMARY KEY,
        data       TEXT NOT NULL,
        created    TEXT DEFAULT (datetime('now')),
        updated_at TEXT,
        deleted    INTEGER DEFAULT 0,
        deviation  REAL DEFAULT 0.0,
        action     TEXT DEFAULT 'work_quiet'
    )
"""


def find_legacy_stores(root: Path) -> list[Path]:
    """Every live {collection}/store.db under root, skipping _archive."""
    return sorted(
        p for p in root.rglob("store.db")
        if "_archive" not in p.relative_to(root).parts
    )


def _columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(records)")}


def merge_one(src: Path, root: Path, apply: bool) -> dict:
    """Merge one legacy store.db into its collection's canonical .db."""
    collection = src.parent.relative_to(root).as_posix()
    target = src.parent.parent / f"{src.parent.name}.db"  # {root}/{collection}.db
    report = {"collection": collection, "source": str(src), "target": str(target),
              "rows": 0, "inserted": 0, "collisions": [], "skipped": 0}

    sconn = sqlite3.connect(str(src))
    sconn.row_factory = sqlite3.Row
    try:
        if "records" not in {r[0] for r in sconn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            report["skipped"] = -1  # no records table (empty husk)
            if apply:
                _archive_source(src)
            return report
        scols = _columns(sconn)
        created_col = "created_at" if "created_at" in scols else "created"
        rows = sconn.execute(
            f"SELECT id, data, {created_col} AS created, updated_at, "
            f"COALESCE(deleted, 0) AS deleted FROM records"
        ).fetchall()
    finally:
        sconn.close()

    report["rows"] = len(rows)
    if not rows:
        # empty husks still archive — leaving them keeps --verify red forever
        if apply:
            _archive_source(src)
        return report

    tconn = sqlite3.connect(str(target))
    tconn.row_factory = sqlite3.Row
    try:
        tconn.execute(_TARGET_SCHEMA)
        for col, typedef in (("deviation", "REAL DEFAULT 0.0"),
                             ("action", "TEXT DEFAULT 'work_quiet'"),
                             ("updated_at", "TEXT"),
                             ("deleted", "INTEGER DEFAULT 0")):
            if col not in _columns(tconn):
                tconn.execute(f"ALTER TABLE records ADD COLUMN {col} {typedef}")
        for row in rows:
            existing = tconn.execute(
                "SELECT updated_at FROM records WHERE id = ?", (row["id"],)
            ).fetchone()
            if existing is None:
                if apply:
                    tconn.execute(
                        "INSERT INTO records (id, data, created, updated_at, deleted) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (row["id"], row["data"], row["created"],
                         row["updated_at"], row["deleted"]),
                    )
                report["inserted"] += 1
            else:
                src_ts = row["updated_at"] or row["created"] or ""
                tgt_ts = existing["updated_at"] or ""
                winner = "source" if src_ts > tgt_ts else "target"
                report["collisions"].append(
                    {"id": row["id"], "winner": winner,
                     "source_ts": src_ts, "target_ts": tgt_ts})
                if winner == "source" and apply:
                    tconn.execute(
                        "UPDATE records SET data = ?, updated_at = ? WHERE id = ?",
                        (row["data"], row["updated_at"], row["id"]),
                    )
        if apply:
            tconn.commit()
    finally:
        tconn.close()

    if apply:
        _archive_source(src)
    return report


def _archive_source(src: Path) -> None:
    """Rename a merged/empty store.db (and WAL/SHM side files) out of the live path."""
    stamp = date.today().isoformat()
    src.rename(src.with_name(f"store.db.migrated-{stamp}"))
    for ext in ("-wal", "-shm"):
        side = src.with_name(f"store.db{ext}")
        if side.exists():
            side.rename(src.with_name(f"store.db.migrated-{stamp}{ext}"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge legacy SOIL store.db files into {collection}.db")
    ap.add_argument("--apply", action="store_true", help="perform the merge (default: dry-run)")
    ap.add_argument("--verify", action="store_true", help="exit 1 if any live store.db remains")
    ap.add_argument("--root", default="", help="store root override (default: resolve_store_root)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else resolve_store_root()
    legacy = find_legacy_stores(root)

    if args.verify:
        if legacy:
            print(f"FAIL: {len(legacy)} live store.db file(s) remain under {root}:")
            for p in legacy:
                print(f"  {p}")
            return 1
        print(f"PASS: no live store.db files under {root}")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"SOIL layout merge [{mode}] — root={root} — {len(legacy)} legacy store.db file(s)")
    total_inserted = total_collisions = 0
    for src in legacy:
        rep = merge_one(src, root, apply=args.apply)
        total_inserted += rep["inserted"]
        total_collisions += len(rep["collisions"])
        tag = "EMPTY-HUSK" if rep["skipped"] == -1 else \
            f"rows={rep['rows']} insert={rep['inserted']} collide={len(rep['collisions'])}"
        print(f"  {rep['collection']:<48} {tag}")
        for c in rep["collisions"]:
            print(f"      collision id={c['id']} winner={c['winner']} "
                  f"src={c['source_ts']} tgt={c['target_ts']}")
    print(f"{mode}: {total_inserted} rows to insert, {total_collisions} collisions"
          + ("" if args.apply else " — re-run with --apply to perform"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
