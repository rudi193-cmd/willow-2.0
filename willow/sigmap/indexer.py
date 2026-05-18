"""
willow/sigmap/indexer.py — Orchestrator: walk directory, extract, index.
b17: SMAP1  ΔΣ=42

Walks a directory tree, extracts code signatures for all code files,
classifies by tier, builds dependency graph, and upserts to jeles_atoms.
Safe to re-run (upsert logic). Never calls embedder — backfill handles that.
"""
import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional

from willow.sigmap.extractor import extract_file
from willow.sigmap.classifier import classify
from willow.sigmap.graph import build_graph

log = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

_DEFAULT_EXTENSIONS = frozenset([".py", ".js", ".ts", ".go", ".rs", ".rb"])

_SKIP_DIRS = frozenset([
    "vendor", "node_modules", ".git", "__pycache__",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env",
])

_SKIP_FILE_PATTERNS = [".min.", "_pb2.py", ".lock"]


def _should_skip_dir(d: Path) -> bool:
    return d.name in _SKIP_DIRS or d.name.startswith(".")


def _should_skip_file(f: Path) -> bool:
    name = f.name
    for pat in _SKIP_FILE_PATTERNS:
        if pat in name:
            return True
    return False


def _make_id(path: Path) -> str:
    """Generate a stable, unique ID for a file path."""
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    return f"sigmap-{digest}"


def _collect_files(root: Path, extensions: frozenset) -> list[Path]:
    """Walk root, collect all non-skipped files with target extensions."""
    collected = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            for entry in current.iterdir():
                if entry.is_dir():
                    if not _should_skip_dir(entry):
                        stack.append(entry)
                elif entry.is_file():
                    if entry.suffix.lower() in extensions:
                        if not _should_skip_file(entry):
                            collected.append(entry)
        except PermissionError:
            pass
    return collected


def _upsert_atom(pg, atom_id: str, path: Path, root: Path,
                 sigs: list[str], tier: str, agent: str) -> None:
    """Upsert a single jeles_atom record."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path

    content = "\n".join(sigs)
    title = f"{rel} [{tier}]"
    jsonl_id = str(path)  # use file path as source reference

    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute("""
            INSERT INTO jeles_atoms
                (id, jsonl_id, agent, content, domain, depth, certainty, title)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                content    = EXCLUDED.content,
                title      = EXCLUDED.title,
                jsonl_id   = EXCLUDED.jsonl_id
        """, (
            atom_id,
            jsonl_id,
            agent,
            content,
            "code",        # domain
            1,             # depth
            0.98,          # certainty
            title,
        ))
    pg.conn.commit()


def index_directory(
    root: Path,
    agent: str = "sigmap",
    pg=None,
    dry_run: bool = False,
    extensions: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> dict:
    """Walk root, extract signatures for all code files, write to jeles_atoms.

    Returns {"indexed": int, "skipped": int, "errors": int}
    """
    ext_set = frozenset(extensions) if extensions else _DEFAULT_EXTENSIONS

    log.info("[sigmap] collecting files under %s", root)
    files = _collect_files(root, ext_set)
    if limit:
        files = files[:limit]

    log.info("[sigmap] found %d files to process", len(files))

    # Build dependency graph (Python only, across full file set)
    try:
        graph, rev_graph = build_graph(root, files)
    except Exception as e:
        log.warning("[sigmap] graph build failed: %s", e)
        graph, rev_graph = {}, {}

    indexed = 0
    skipped = 0
    errors = 0

    for path in files:
        try:
            sigs = extract_file(path)
            if not sigs:
                skipped += 1
                continue

            tier = classify(path, sigs)
            atom_id = _make_id(path)

            if dry_run:
                try:
                    rel = path.relative_to(root)
                except ValueError:
                    rel = path
                print(f"[dry-run] {rel} [{tier}] — {len(sigs)} sigs → {atom_id}")
                indexed += 1
                continue

            if pg is None:
                # Import lazily so tests without Postgres can still call dry_run
                try:
                    from core.pg_bridge import PgBridge
                    pg = PgBridge()
                except Exception as e:
                    log.error("[sigmap] PgBridge unavailable: %s", e)
                    errors += 1
                    continue

            _upsert_atom(pg, atom_id, path, root, sigs, tier, agent)
            indexed += 1

        except Exception as e:
            log.warning("[sigmap] error processing %s: %s", path, e)
            errors += 1

    log.info("[sigmap] done — indexed=%d skipped=%d errors=%d", indexed, skipped, errors)
    return {"indexed": indexed, "skipped": skipped, "errors": errors}
