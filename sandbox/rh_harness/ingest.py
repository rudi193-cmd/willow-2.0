"""
Ingest a folder of APO/RH math files into Willow KB under a tagged run namespace.

Usage:
    python -m sandbox.rh_harness.ingest --folder /path/to/data --run-id clean
    python -m sandbox.rh_harness.ingest --folder /path/to/data --run-id dirty

Each file is chunked by paragraph, tagged with run_id + source filename.
The run-id is stored as a KB tag so compare.py can diff by run.

Supported file types: .tex, .md, .txt, .lean
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterator

SUPPORTED_SUFFIXES = {".tex", ".md", ".txt", ".lean"}
CHUNK_MIN_CHARS = 200
CHUNK_MAX_CHARS = 3000


def iter_files(folder: Path) -> Iterator[Path]:
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix in SUPPORTED_SUFFIXES:
            yield path


def chunk_text(text: str) -> list[str]:
    """Split on blank lines; merge short fragments, cap at CHUNK_MAX_CHARS."""
    raw = re.split(r"\n{2,}", text.strip())
    chunks: list[str] = []
    buf = ""
    for block in raw:
        block = block.strip()
        if not block:
            continue
        if len(buf) + len(block) < CHUNK_MAX_CHARS:
            buf = (buf + "\n\n" + block).strip() if buf else block
        else:
            if len(buf) >= CHUNK_MIN_CHARS:
                chunks.append(buf)
            buf = block
    if len(buf) >= CHUNK_MIN_CHARS:
        chunks.append(buf)
    return chunks


def build_manifest(folder: Path, run_id: str) -> list[dict]:
    """Walk folder, chunk files, return list of atom dicts ready for ingestion."""
    atoms = []
    for path in iter_files(folder):
        try:
            text = path.read_text(errors="replace")
        except OSError as e:
            print(f"SKIP {path}: {e}", file=sys.stderr)
            continue
        chunks = chunk_text(text)
        rel = path.relative_to(folder)
        for i, chunk in enumerate(chunks):
            atoms.append({
                "run_id": run_id,
                "source_file": str(rel),
                "chunk_index": i,
                "chunk_count": len(chunks),
                "text": chunk,
                "tags": [run_id, "apo", "rh", str(path.suffix.lstrip("."))],
                "title": f"[{run_id}] {rel} chunk {i + 1}/{len(chunks)}",
            })
    return atoms


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest APO/RH folder into Willow KB")
    parser.add_argument("--folder", required=True, help="Path to data folder")
    parser.add_argument("--run-id", required=True, choices=["clean", "dirty"],
                        help="Run label: clean (curated) or dirty (raw dump)")
    parser.add_argument("--manifest-out", default="",
                        help="Write manifest JSON to this path (default: stdout)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print manifest only, do not call Willow")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        sys.exit(f"ERROR: {folder} is not a directory")

    manifest = build_manifest(folder, args.run_id)
    print(f"[ingest] {args.run_id}: {len(manifest)} chunks from {folder}", file=sys.stderr)

    if args.manifest_out:
        Path(args.manifest_out).write_text(json.dumps(manifest, indent=2))
        print(f"[ingest] manifest written to {args.manifest_out}", file=sys.stderr)
    elif args.dry_run:
        print(json.dumps(manifest, indent=2))
        return

    if args.dry_run:
        return

    # Live ingestion path — requires Willow MCP to be running.
    # Each atom is submitted as a kb_ingest call via the willow CLI shim.
    try:
        from sandbox.rh_harness.willow_shim import ingest_atom
    except ImportError:
        sys.exit("ERROR: willow_shim not available — run with --dry-run or ensure Willow MCP is reachable")

    ok = failed = 0
    for atom in manifest:
        atom_id = ingest_atom(atom)
        if atom_id:
            ok += 1
        else:
            failed += 1
            print(f"FAIL {atom['title']}", file=sys.stderr)

    print(f"[ingest] done: {ok} ingested, {failed} failed", file=sys.stderr)


if __name__ == "__main__":
    main()
