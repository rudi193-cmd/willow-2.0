#!/usr/bin/env python3
# b17: MIG20  ΔΣ=42
"""
ingest_seeds.py — Willow 2.0 migration agent.

Scans a source Willow installation, classifies every artifact by layer
(public / system / personal), builds a migration manifest, and on
ratification writes everything into the willow-2.0.db SQLite schema.

Modes
-----
  python3 ingest_seeds.py                 # scan + print manifest, write nothing
  python3 ingest_seeds.py --execute       # scan + execute manifest
  python3 ingest_seeds.py --include-personal  # include personal layer (requires explicit flag)
  python3 ingest_seeds.py --manifest path/to/manifest.json --execute  # execute a saved manifest

Spec: docs/migration-spec.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ── paths ──────────────────────────────────────────────────────────────────────

DB_PATH       = Path(os.environ.get("WILLOW_20_DB", str(Path.home() / ".willow" / "willow-2.0.db"))).expanduser()
MANIFEST_PATH = Path.home() / ".willow" / "migration-manifest.json"
GITHUB_ROOT   = Path(os.environ.get("GITHUB_ROOT", str(Path.home() / "github")))
WILLOW_19_DIR = GITHUB_ROOT / "willow-1.9"
ASHOKOA_ROOT  = Path.home() / "Ashokoa"
SKILLS_SRC    = WILLOW_19_DIR / "willow" / "fylgja" / "skills"
COMMANDS_SRC  = WILLOW_19_DIR / ".claude" / "commands"
SEEDS_DIR     = Path.home() / "Downloads"
PG_DB         = os.environ.get("WILLOW_PG_DB", "willow_19")
PG_USER       = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))

PERSONAL_DBS: list[tuple[str, Path]] = [
    ("sean",   Path.home() / "personal" / "sean.db"),
    ("gerald", Path.home() / "personal" / "writing" / "gerald.db"),
]

# ── layer constants ────────────────────────────────────────────────────────────

PUBLIC   = "public"
SYSTEM   = "system"
PERSONAL = "personal"

ACTIONS  = ("migrate", "skip", "transform", "defer", "conflict")


# ── helpers ───────────────────────────────────────────────────────────────────

def artifact_id(source_path: str, source_id: str = "") -> str:
    raw = f"{source_path}:{source_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def now_iso() -> str:
    return datetime.now().isoformat()


def pg_connect():
    try:
        import psycopg2
        conn = psycopg2.connect(dbname=PG_DB, user=PG_USER)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"  [postgres] unavailable: {e}", file=sys.stderr)
        return None


# ── scanners ──────────────────────────────────────────────────────────────────

def scan_agent_identities() -> list[dict]:
    """CLAUDE.md files → seed_sections (system layer).

    Explicit roots first (agents whose CLAUDE.md lives outside ~/github/*/),
    then subdirectory scan with worktrees filtered out.
    """
    # Explicit agent paths — not reachable by glob
    EXPLICIT: list[tuple[str, Path]] = [
        ("hanuman",     Path.home() / "CLAUDE.md"),
        ("loki",        GITHUB_ROOT / "CLAUDE.md"),
    ]

    # Subdir scan: ~/github/*/CLAUDE.md, skip worktrees
    SUBDIR_MAP = {
        "safe-app-store":  "vishwakarma",
        "skirnir":         "skirnir",
        "willow-1.9":      "hanuman-repo",  # repo identity, distinct from agent CLAUDE.md
    }
    WORKTREE_MARKERS = ("-wt-", "-worktree-", "-wt/")

    artifacts = []
    seen: set[str] = set()

    def _add(agent_name: str, path: Path):
        if agent_name in seen or not path.exists():
            return
        seen.add(agent_name)
        artifacts.append({
            "id":           artifact_id(str(path)),
            "type":         "git/identity",
            "source_path":  str(path),
            "source_id":    agent_name,
            "layer":        SYSTEM,
            "action":       "transform",
            "transform":    "persona_seed",
            "target_table": "seed_sections",
            "seed_id":      agent_name,
            "section":      "identity",
            "reason":       f"CLAUDE.md for agent {agent_name}",
        })

    for agent_name, path in EXPLICIT:
        _add(agent_name, path)

    for path in sorted(GITHUB_ROOT.glob("*/CLAUDE.md")):
        dirname = path.parent.name
        if any(m in dirname for m in WORKTREE_MARKERS):
            continue  # skip worktrees
        agent_name = next(
            (v for k, v in SUBDIR_MAP.items() if dirname == k or dirname.startswith(k)),
            dirname,
        )
        _add(agent_name, path)

    return artifacts


def scan_soil_collections(include_personal: bool) -> list[dict]:
    """SOIL SQLite store → records table. Reads ~/.willow/store/**/*.db."""
    store_root = Path(os.environ.get("WILLOW_STORE_ROOT", str(Path.home() / ".willow" / "store")))
    if not store_root.exists():
        return []

    SYSTEM_PREFIXES  = ("hanuman", "heimdallr", "vishwakarma", "loki", "skirnir", "agents", "fleet")
    PERSONAL_PREFIXES = ("sean", "user-", "gerald")
    SKIP_PREFIXES    = ("_", "archived", "corpus", "chunk_index", "cube_")

    artifacts = []
    for db_file in sorted(store_root.rglob("*.db")):
        rel = db_file.relative_to(store_root)
        collection = str(rel.with_suffix("")).replace(os.sep, "/")

        # skip internal/large collections
        top = collection.split("/")[0]
        if any(top.startswith(s) for s in SKIP_PREFIXES):
            continue

        is_personal = any(collection.startswith(p) for p in PERSONAL_PREFIXES)
        is_system   = any(collection.startswith(p) for p in SYSTEM_PREFIXES)

        if is_personal and not include_personal:
            continue
        if not is_personal and not is_system:
            continue  # unknown namespace — defer

        layer  = PERSONAL if is_personal else SYSTEM
        action = "transform"

        try:
            conn = sqlite3.connect(str(db_file))
            conn.row_factory = sqlite3.Row
            count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            conn.close()
            if count == 0:
                continue
        except Exception:
            continue

        artifacts.append({
            "id":          artifact_id(str(db_file)),
            "type":        "soil/collection",
            "source_path": str(db_file),
            "source_id":   collection,
            "layer":       layer,
            "action":      action,
            "transform":   "soil_to_records",
            "target_table": "records",
            "meta":        {"collection": collection},
            "reason":      f"SOIL collection [{layer}]: {collection}",
        })

    return artifacts


def scan_oakenscroll_seeds() -> list[dict]:
    """Original Oakenscroll JSON seeds → seed_sections (system layer)."""
    seed_files = [
        ("OAKENSCROLL_SEED_v1", SEEDS_DIR / "OAKENSCROLL_SEED.json"),
        ("OAKENSCROLL_SEED_v2", SEEDS_DIR / "OAKENSCROLL_SEED_v2.json"),
        ("OAKENSCROLL_SEED_v3", SEEDS_DIR / "OAKENSCROLL_SEED_v3.json"),
    ]
    artifacts = []
    for seed_id, path in seed_files:
        action = "migrate" if path.exists() else "skip"
        reason = "seed file present" if path.exists() else "file not found"
        artifacts.append({
            "id":          artifact_id(str(path), seed_id),
            "type":        "seed/oakenscroll",
            "source_path": str(path),
            "source_id":   seed_id,
            "layer":       SYSTEM,
            "action":      action,
            "target_table": "seed_sections",
            "reason":      reason,
        })
    return artifacts


def scan_personal_dbs() -> list[dict]:
    """sean.db + gerald.db → records (personal layer, --include-personal required)."""
    artifacts = []
    for db_name, db_path in PERSONAL_DBS:
        if not db_path.exists():
            artifacts.append({
                "id":          artifact_id(str(db_path), db_name),
                "type":        "personal/db",
                "source_path": str(db_path),
                "source_id":   db_name,
                "layer":       PERSONAL,
                "action":      "skip",
                "reason":      f"{db_path} not found",
            })
            continue

        conn = sqlite3.connect(str(db_path))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        conn.close()

        for table in tables:
            try:
                c = sqlite3.connect(str(db_path))
                count = c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                c.close()
            except Exception:
                count = 0
            if count == 0:
                continue

            artifacts.append({
                "id":           artifact_id(str(db_path), f"{db_name}/{table}"),
                "type":         "personal/db/table",
                "source_path":  str(db_path),
                "source_id":    f"{db_name}/{table}",
                "layer":        PERSONAL,
                "action":       "transform",
                "transform":    "personal_table_to_records",
                "target_table": "records",
                "meta": {
                    "db":         db_name,
                    "table":      table,
                    "collection": f"personal/{db_name}/{table}",
                    "row_count":  count,
                },
                "reason": f"{db_name}.db/{table} ({count} rows)",
            })

    return artifacts


def scan_kb_atoms(pg, include_personal: bool) -> list[dict]:
    """knowledge table → notes (system) or records (personal)."""
    if not pg:
        return [{"id": "kb-unavailable", "type": "kb/atoms", "layer": SYSTEM,
                 "action": "defer", "reason": "postgres unavailable",
                 "source_path": f"postgres:{PG_DB}/knowledge", "source_id": ""}]

    artifacts = []
    cur = pg.cursor()

    # system atoms
    cur.execute("""
        SELECT id, project, title, summary, category, source_type, created_at
          FROM knowledge
         WHERE invalid_at IS NULL
           AND project NOT IN ('sean')
         ORDER BY created_at DESC
         LIMIT 500
    """)
    for row in cur.fetchall():
        atom_id, project, title, summary, category, source_type, created_at = row
        artifacts.append({
            "id":          artifact_id("knowledge", atom_id),
            "type":        "kb/atom",
            "source_path": f"postgres:{PG_DB}/knowledge",
            "source_id":   atom_id,
            "layer":       SYSTEM,
            "action":      "transform",
            "transform":   "flatten_to_note",
            "target_table": "notes",
            "meta": {
                "title":    title,
                "tags":     ",".join(filter(None, [project, category, source_type])),
                "created_at": str(created_at),
            },
            "reason": f"system KB atom [{project}]",
        })

    if include_personal:
        cur.execute("""
            SELECT id, project, title, summary, category, created_at
              FROM knowledge
             WHERE invalid_at IS NULL
               AND project = 'sean'
             ORDER BY created_at DESC
             LIMIT 200
        """)
        for row in cur.fetchall():
            atom_id, project, title, summary, category, created_at = row
            artifacts.append({
                "id":          artifact_id("knowledge/personal", atom_id),
                "type":        "kb/atom/personal",
                "source_path": f"postgres:{PG_DB}/knowledge",
                "source_id":   atom_id,
                "layer":       PERSONAL,
                "action":      "transform",
                "transform":   "flatten_to_record",
                "target_table": "records",
                "meta": {
                    "collection": "personal/kb",
                    "title":     title,
                    "created_at": str(created_at),
                },
                "reason": "personal KB atom — included via --include-personal",
            })
    else:
        cur.execute("SELECT COUNT(*) FROM knowledge WHERE invalid_at IS NULL AND project = 'sean'")
        count = cur.fetchone()[0]
        if count:
            artifacts.append({
                "id":          "kb-personal-gate",
                "type":        "kb/atom/personal",
                "source_path": f"postgres:{PG_DB}/knowledge",
                "source_id":   "personal-gate",
                "layer":       PERSONAL,
                "action":      "skip",
                "reason":      f"{count} personal atoms — pass --include-personal to migrate",
            })

    cur.close()
    return artifacts


def scan_frank_ledger(pg) -> list[dict]:
    """frank_ledger → sessions (system layer, last 10 entries)."""
    if not pg:
        return []
    artifacts = []
    cur = pg.cursor()
    try:
        cur.execute("""
            SELECT id, project, event_type, content, created_at
              FROM frank_ledger
             ORDER BY created_at DESC
             LIMIT 10
        """)
        for row in cur.fetchall():
            entry_id, project, event_type, content, created_at = row
            artifacts.append({
                "id":          artifact_id("frank_ledger", str(entry_id)),
                "type":        "ledger/entry",
                "source_path": f"postgres:{PG_DB}/frank_ledger",
                "source_id":   str(entry_id),
                "layer":       SYSTEM,
                "action":      "transform",
                "transform":   "ledger_to_session",
                "target_table": "sessions",
                "meta": {
                    "project":    project,
                    "event_type": event_type,
                    "content":    content if isinstance(content, dict) else {},
                    "created_at": str(created_at),
                },
                "reason": f"frank_ledger {event_type} [{project}]",
            })
    except Exception as e:
        artifacts.append({
            "id": "ledger-error", "type": "ledger/entry", "layer": SYSTEM,
            "action": "defer", "reason": f"ledger scan error: {e}",
            "source_path": f"postgres:{PG_DB}/frank_ledger", "source_id": "",
        })
    cur.close()
    return artifacts


def scan_handoffs() -> list[dict]:
    """Latest handoff per agent → sessions (system layer)."""
    artifacts = []
    handoff_root = ASHOKOA_ROOT / "agents"
    if not handoff_root.exists():
        return []
    for agent_dir in sorted(handoff_root.iterdir()):
        hh = agent_dir / "index" / "haumana_handoffs"
        if not hh.exists():
            continue
        files = sorted(hh.glob("SESSION_HANDOFF_*.md"), reverse=True)
        if not files:
            continue
        latest = files[0]
        artifacts.append({
            "id":          artifact_id(str(latest)),
            "type":        "handoff/session",
            "source_path": str(latest),
            "source_id":   latest.name,
            "layer":       SYSTEM,
            "action":      "transform",
            "transform":   "handoff_to_session",
            "target_table": "sessions",
            "reason":      f"latest handoff for {agent_dir.name}",
        })
    return artifacts


def scan_skills() -> list[dict]:
    """Skill/command .md files → records (public layer)."""
    artifacts = []
    for src_dir in [SKILLS_SRC, COMMANDS_SRC]:
        if not src_dir.exists():
            continue
        for path in sorted(src_dir.glob("*.md")):
            artifacts.append({
                "id":          artifact_id(str(path)),
                "type":        "skill/file",
                "source_path": str(path),
                "source_id":   path.stem,
                "layer":       PUBLIC,
                "action":      "migrate",
                "target_table": "records",
                "meta":        {"collection": f"skills/{src_dir.name}"},
                "reason":      f"skill file: {path.name}",
            })
    return artifacts


# ── manifest ──────────────────────────────────────────────────────────────────

def build_manifest(include_personal: bool) -> dict:
    pg = pg_connect()

    print("Scanning sources...")
    all_artifacts: list[dict] = []
    all_artifacts += scan_agent_identities()
    print(f"  agent identities:    {len(all_artifacts)}")
    soil = scan_soil_collections(include_personal)
    all_artifacts += soil
    print(f"  SOIL collections:    {len(soil)}")
    if include_personal:
        pdbs = scan_personal_dbs()
        all_artifacts += pdbs
        print(f"  personal DBs:        {len([a for a in pdbs if a['action'] != 'skip'])}/{len(pdbs)} tables")
    oak = scan_oakenscroll_seeds()
    all_artifacts += oak
    print(f"  oakenscroll seeds:   {len([a for a in oak if a['action'] != 'skip'])}/{len(oak)}")
    kb = scan_kb_atoms(pg, include_personal)
    all_artifacts += kb
    kb_live = [a for a in kb if a['action'] not in ('skip', 'defer')]
    print(f"  KB atoms:            {len(kb_live)}")
    ledger = scan_frank_ledger(pg)
    all_artifacts += ledger
    print(f"  frank ledger:        {len(ledger)}")
    handoffs = scan_handoffs()
    all_artifacts += handoffs
    print(f"  session handoffs:    {len(handoffs)}")
    skills = scan_skills()
    all_artifacts += skills
    print(f"  skill files:         {len(skills)}")

    if pg:
        pg.close()

    stats = {}
    for a in ACTIONS:
        stats[a] = sum(1 for x in all_artifacts if x.get("action") == a)
    stats["total"] = len(all_artifacts)

    manifest = {
        "manifest_version": "1.0",
        "source":           str(WILLOW_19_DIR),
        "target":           str(DB_PATH),
        "generated_at":     now_iso(),
        "include_personal": include_personal,
        "artifacts":        all_artifacts,
        "conflicts":        [],
        "gaps":             [a for a in all_artifacts if a.get("action") == "defer"],
        "stats":            stats,
    }
    return manifest


# ── execution ─────────────────────────────────────────────────────────────────

def execute_manifest(manifest: dict, conn: sqlite3.Connection) -> dict[str, int]:
    results = {"written": 0, "skipped": 0, "errors": 0}

    for artifact in manifest["artifacts"]:
        action = artifact.get("action")
        if action in ("skip", "defer", "conflict"):
            results["skipped"] += 1
            continue

        try:
            atype = artifact.get("type", "")

            if atype == "git/identity":
                _exec_persona_seed(artifact, conn)

            elif atype == "seed/oakenscroll":
                _exec_oakenscroll(artifact, conn)

            elif atype in ("kb/atom", "kb/atom/personal"):
                _exec_kb_atom(artifact, conn)

            elif atype == "ledger/entry":
                _exec_ledger_entry(artifact, conn)

            elif atype == "handoff/session":
                _exec_handoff(artifact, conn)

            elif atype == "soil/collection":
                _exec_soil_collection(artifact, conn)

            elif atype == "personal/db/table":
                _exec_personal_db_table(artifact, conn)

            elif atype == "skill/file":
                _exec_skill(artifact, conn)

            else:
                results["skipped"] += 1
                continue

            results["written"] += 1

        except Exception as e:
            print(f"  ERROR [{artifact.get('id')}] {artifact.get('type')}: {e}", file=sys.stderr)
            results["errors"] += 1

    return results


def _exec_persona_seed(artifact: dict, conn: sqlite3.Connection):
    path = Path(artifact["source_path"])
    body = path.read_text(encoding="utf-8")
    # Store as plain text string — persona.py renders it directly into session context
    conn.execute("""
        INSERT INTO seed_sections (seed_id, section, body)
        VALUES (?, ?, ?)
        ON CONFLICT(seed_id, section) DO UPDATE SET body=excluded.body
    """, (artifact["seed_id"], artifact["section"], body))


def _exec_oakenscroll(artifact: dict, conn: sqlite3.Connection):
    path = Path(artifact["source_path"])
    if not path.exists():
        return
    raw = json.loads(path.read_text())
    sections = [(k, v) for k, v in raw.items() if k != "seed"]
    seed_id = artifact["source_id"]
    for section, body in sections:
        conn.execute("""
            INSERT INTO seed_sections (seed_id, section, body)
            VALUES (?, ?, ?)
            ON CONFLICT(seed_id, section) DO UPDATE SET body=excluded.body
        """, (seed_id, section, json.dumps(body)))


def _exec_kb_atom(artifact: dict, conn: sqlite3.Connection):
    meta = artifact.get("meta", {})
    transform = artifact.get("transform")

    if transform == "flatten_to_note":
        tags = meta.get("tags", "")
        body = json.dumps({
            "atom_id":  artifact["source_id"],
            "title":    meta.get("title", ""),
            "tags":     tags,
        })
        conn.execute(
            "INSERT OR IGNORE INTO notes (body, tags, created_at) VALUES (?, ?, ?)",
            (body, tags, meta.get("created_at", now_iso())),
        )

    elif transform == "flatten_to_record":
        collection = meta.get("collection", "personal/kb")
        data = json.dumps({
            "atom_id": artifact["source_id"],
            "title":   meta.get("title", ""),
        })
        conn.execute("""
            INSERT OR IGNORE INTO records (id, collection, data, created_at)
            VALUES (?, ?, ?, ?)
        """, (artifact["id"], collection, data, meta.get("created_at", now_iso())))


def _exec_ledger_entry(artifact: dict, conn: sqlite3.Connection):
    meta = artifact.get("meta", {})
    content = meta.get("content", {})
    summary = (
        content.get("summary") or
        f"{meta.get('event_type','?')} [{meta.get('project','?')}] {meta.get('created_at','')}"
    )
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id, summary, created_at) VALUES (?, ?, ?)",
        (artifact["id"], summary, meta.get("created_at", now_iso())),
    )


def _exec_handoff(artifact: dict, conn: sqlite3.Connection):
    path = Path(artifact["source_path"])
    text = path.read_text(encoding="utf-8")
    # first non-empty line after the # header is the summary
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    summary = lines[0] if lines else path.name
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id, summary, created_at) VALUES (?, ?, ?)",
        (artifact["id"], summary, now_iso()),
    )


def _exec_personal_db_table(artifact: dict, conn: sqlite3.Connection):
    meta       = artifact["meta"]
    db_path    = Path(artifact["source_path"])
    table      = meta["table"]
    collection = meta["collection"]

    src = sqlite3.connect(str(db_path))
    src.row_factory = sqlite3.Row
    rows = src.execute(f'SELECT * FROM "{table}" LIMIT 1000').fetchall()
    src.close()

    for row in rows:
        row_dict = dict(row)
        row_id   = str(row_dict.get("id", artifact_id(collection, str(row_dict))))
        rec_id   = f"personal/{meta['db']}/{table}/{row_id}"
        ts       = (str(row_dict.get("created") or row_dict.get("created_at") or now_iso()))
        conn.execute("""
            INSERT OR REPLACE INTO records (id, collection, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (rec_id, collection, json.dumps(row_dict, default=str), ts, now_iso()))


def _exec_soil_collection(artifact: dict, conn: sqlite3.Connection):
    db_file = Path(artifact["source_path"])
    collection = artifact["meta"]["collection"]
    src = sqlite3.connect(str(db_file))
    src.row_factory = sqlite3.Row
    col_names = {r[1] for r in src.execute("PRAGMA table_info(records)").fetchall()}
    ts_col    = "created" if "created" in col_names else "created_at" if "created_at" in col_names else "NULL"
    upd_col   = "updated_at" if "updated_at" in col_names else "NULL"
    del_where = "WHERE deleted=0" if "deleted" in col_names else ""
    src.row_factory = None  # use positional tuples
    rows = src.execute(
        f"SELECT id, data, {ts_col}, {upd_col} FROM records {del_where} LIMIT 500"
    ).fetchall()
    src.close()
    for row_id, row_data, row_ts, row_upd in rows:
        rec_id = f"soil/{collection}/{row_id}"
        data   = row_data if isinstance(row_data, str) else json.dumps(row_data)
        conn.execute("""
            INSERT OR IGNORE INTO records (id, collection, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (rec_id, collection, data, row_ts or now_iso(), row_upd or now_iso()))


def _exec_skill(artifact: dict, conn: sqlite3.Connection):
    path = Path(artifact["source_path"])
    body = path.read_text(encoding="utf-8")
    meta = artifact.get("meta", {})
    collection = meta.get("collection", "skills/misc")
    data = json.dumps({"name": path.stem, "body": body})
    conn.execute("""
        INSERT OR REPLACE INTO records (id, collection, data, updated_at)
        VALUES (?, ?, ?, ?)
    """, (artifact["id"], collection, data, now_iso()))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Willow 2.0 migration agent")
    parser.add_argument("--execute",         action="store_true", help="Execute the manifest (writes to DB)")
    parser.add_argument("--include-personal",action="store_true", help="Include personal-layer artifacts")
    parser.add_argument("--manifest",        metavar="PATH",      help="Path to existing manifest JSON (skip scan)")
    parser.add_argument("--save-manifest",   metavar="PATH",      help="Save manifest to this path")
    args = parser.parse_args()

    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
        print(f"Loaded manifest: {args.manifest}")
        print(f"  generated: {manifest.get('generated_at')}")
    else:
        manifest = build_manifest(include_personal=args.include_personal)
        save_path = Path(args.save_manifest) if args.save_manifest else MANIFEST_PATH
        save_path.write_text(json.dumps(manifest, indent=2, default=str))
        print(f"\nManifest saved → {save_path}")

    s = manifest["stats"]
    print(f"\nManifest summary:")
    print(f"  total:    {s.get('total', 0)}")
    print(f"  migrate:  {s.get('migrate', 0)}")
    print(f"  transform:{s.get('transform', 0)}")
    print(f"  skip:     {s.get('skip', 0)}")
    print(f"  defer:    {s.get('defer', 0)}")
    print(f"  conflict: {s.get('conflict', 0)}")

    if manifest.get("gaps"):
        print(f"\nGaps ({len(manifest['gaps'])}):")
        for g in manifest["gaps"]:
            print(f"  [{g.get('type','?')}] {g.get('reason','')}")

    if not args.execute:
        print("\n(dry run — pass --execute to write to DB)")
        return

    if not DB_PATH.exists():
        print(f"\nDB not found at {DB_PATH} — run init_db.py first", file=sys.stderr)
        sys.exit(1)

    print(f"\nExecuting → {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    results = execute_manifest(manifest, conn)
    conn.commit()
    conn.close()

    print(f"  written:  {results['written']}")
    print(f"  skipped:  {results['skipped']}")
    print(f"  errors:   {results['errors']}")
    print(f"\nDone → {DB_PATH}")


if __name__ == "__main__":
    main()
