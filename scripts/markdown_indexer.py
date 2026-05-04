#!/usr/bin/env python3
"""
Markdown docs indexer (Layer 3) — indexes all .md files in github/ and agents/
into public.knowledge (project='docs').
One atom per file. Short files (<3000 chars) = full content. Longer = first 3000 chars.
"""
import os
import glob
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    raise

DB_PARAMS = {"dbname": "willow_19", "user": "sean-campbell"}

ROOTS = [
    "/home/sean-campbell/github",
    "/home/sean-campbell/Ashokoa/agents",
]

# Skip generated/noise directories
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".mypy_cache",
    "dist", "build", ".next", ".nuxt", "venv", ".venv",
}

MAX_CONTENT = 3000


def should_skip_path(path: str) -> bool:
    parts = set(Path(path).parts)
    return bool(parts & SKIP_DIRS)


def make_atom_id(filepath: str) -> str:
    return "D" + hashlib.sha1(filepath.encode()).hexdigest()[:7].upper()


def make_title(filepath: str) -> str:
    p = Path(filepath)
    # relative to home
    try:
        rel = p.relative_to("/home/sean-campbell")
        return str(rel)
    except ValueError:
        return p.name


def get_existing_ids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.knowledge WHERE project='docs'")
        return {row[0] for row in cur.fetchall()}


def bulk_insert(conn, atoms: list[dict], existing_ids: set) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    batch = []

    with conn.cursor() as cur:
        for a in atoms:
            if a["atom_id"] in existing_ids:
                skipped += 1
                continue

            content_json = json.dumps({"file_path": a["filepath"]})
            batch.append((
                a["atom_id"],
                "docs",
                now,      # valid_at
                None,     # invalid_at
                now,      # created_at
                a["title"],
                a["summary"],
                content_json,
                "file",
                "reference",
                None,     # embedding
            ))
            existing_ids.add(a["atom_id"])

            if len(batch) >= 500:
                _flush(cur, batch)
                conn.commit()
                inserted += len(batch)
                print(f"  +{inserted} docs atoms so far...", flush=True)
                batch = []

        if batch:
            _flush(cur, batch)
            conn.commit()
            inserted += len(batch)

    return inserted, skipped


def _flush(cur, batch):
    psycopg2.extras.execute_values(cur, """
        INSERT INTO public.knowledge
            (id, project, valid_at, invalid_at, created_at, title, summary, content,
             source_type, category, embedding)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, batch, template="(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)")


def main():
    print("[docs] Scanning for .md files...")
    all_files = []
    for root in ROOTS:
        if not os.path.exists(root):
            continue
        for fp in glob.glob(os.path.join(root, "**", "*.md"), recursive=True):
            if not should_skip_path(fp):
                all_files.append(fp)

    print(f"[docs] Found {len(all_files)} markdown files.")

    conn = psycopg2.connect(**DB_PARAMS)
    existing_ids = get_existing_ids(conn)
    print(f"[docs] {len(existing_ids)} existing doc atoms (will skip).")

    atoms = []
    errors = 0
    for i, fp in enumerate(all_files):
        if (i + 1) % 200 == 0:
            print(f"  reading {i+1}/{len(all_files)}...", flush=True)
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if len(text.strip()) < 20:
                continue  # skip empty/stub files
            summary = text[:MAX_CONTENT].strip()
            atoms.append({
                "atom_id": make_atom_id(fp),
                "filepath": fp,
                "title": make_title(fp),
                "summary": summary,
            })
        except Exception as e:
            errors += 1

    print(f"[docs] {len(atoms)} files readable ({errors} errors). Inserting...")
    inserted, skipped = bulk_insert(conn, atoms, existing_ids)
    conn.close()
    print(f"[docs] Done. {inserted} new atoms, {skipped} skipped.")
    return inserted


if __name__ == "__main__":
    main()
