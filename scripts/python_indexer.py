#!/usr/bin/env python3
"""
Python codebase indexer (Layer 2) — indexes .py files from github/ and agents/
into public.knowledge (project='codebase').
Extracts: file path, module docstring, function/class signatures.
One atom per file. Skips generated, tiny, and test files.
"""
import os
import ast
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

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".mypy_cache",
    "dist", "build", ".next", ".nuxt", "venv", ".venv",
    "migrations", "alembic",
}

MIN_LINES = 10
MAX_SUMMARY = 3000


def should_skip_path(path: str) -> bool:
    parts = set(Path(path).parts)
    return bool(parts & SKIP_DIRS)


def make_atom_id(filepath: str) -> str:
    return "P" + hashlib.sha1(filepath.encode()).hexdigest()[:7].upper()


def make_title(filepath: str) -> str:
    try:
        rel = Path(filepath).relative_to("/home/sean-campbell")
        return str(rel)
    except ValueError:
        return Path(filepath).name


def extract_signatures(source: str) -> str:
    """Extract module docstring + top-level function/class signatures."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    parts = []

    # Module docstring
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        parts.append(f"Module: {mod_doc[:300]}")

    # Top-level defs
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            args = [a.arg for a in node.args.args]
            sig = f"def {node.name}({', '.join(args)})"
            if doc:
                sig += f"  # {doc[:120]}"
            parts.append(sig)
        elif isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            methods = [n.name for n in ast.iter_child_nodes(node)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            sig = f"class {node.name}"
            if doc:
                sig += f"  # {doc[:120]}"
            if methods:
                sig += f"  [methods: {', '.join(methods[:8])}]"
            parts.append(sig)

    return "\n".join(parts)


def get_existing_ids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.knowledge WHERE project='codebase'")
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

            content_json = json.dumps({"file_path": a["filepath"], "lines": a["lines"]})
            batch.append((
                a["atom_id"],
                "codebase",
                now, None, now,
                a["title"],
                a["summary"],
                content_json,
                "file",
                "code",
                None,
            ))
            existing_ids.add(a["atom_id"])

            if len(batch) >= 500:
                _flush(cur, batch)
                conn.commit()
                inserted += len(batch)
                print(f"  +{inserted} code atoms so far...", flush=True)
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
    print("[code] Scanning for .py files...")
    all_files = []
    for root in ROOTS:
        if not os.path.exists(root):
            continue
        for fp in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
            if not should_skip_path(fp):
                all_files.append(fp)

    print(f"[code] Found {len(all_files)} Python files.")

    conn = psycopg2.connect(**DB_PARAMS)
    existing_ids = get_existing_ids(conn)
    print(f"[code] {len(existing_ids)} existing code atoms (will skip).")

    atoms = []
    errors = 0
    for i, fp in enumerate(all_files):
        if (i + 1) % 500 == 0:
            print(f"  reading {i+1}/{len(all_files)}...", flush=True)
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            lines = source.count("\n")
            if lines < MIN_LINES:
                continue

            sigs = extract_signatures(source)
            # Summary = signatures if available, else first MAX_SUMMARY chars of source
            if sigs and len(sigs) > 50:
                summary = sigs[:MAX_SUMMARY]
            else:
                summary = source[:MAX_SUMMARY].strip()

            atoms.append({
                "atom_id": make_atom_id(fp),
                "filepath": fp,
                "title": make_title(fp),
                "summary": summary,
                "lines": lines,
            })
        except Exception:
            errors += 1

    print(f"[code] {len(atoms)} files parsed ({errors} errors). Inserting...")
    inserted, skipped = bulk_insert(conn, atoms, existing_ids)
    conn.close()
    print(f"[code] Done. {inserted} new atoms, {skipped} skipped.")
    return inserted


if __name__ == "__main__":
    main()
