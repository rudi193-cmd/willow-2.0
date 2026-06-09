#!/usr/bin/env python3
"""Manual audit for repo-local file JSONB indexing (read-only by default).

Current indexer landscape (pre-unified file_index):
- scripts/markdown_indexer.py -> public.knowledge project=docs, insert-only, sparse JSONB
- scripts/python_indexer.py   -> public.knowledge project=codebase, insert-only, sparse JSONB
- sap/sap_mcp.py index_ingest -> opus_atoms plain text, no structured file metadata
- scripts/gen_index.py        -> INDEX.md flat index only, no DB verification

Default mode is --check: compares on-disk files against KB and Opus without writes.
Optional --write-kb / --write-opus upsert structured records after reviewing the report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "core"):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

from core.launcher_shadow import clear_willow_launcher_shadow  # noqa: E402

clear_willow_launcher_shadow()

from core.pg_bridge import PgBridge, try_connect  # noqa: E402
from willow.fylgja.file_jsonb_index import (  # noqa: E402
    build_audit_report,
    build_file_record,
    discover_targets,
    kb_payload,
    opus_payload,
)


def _repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return _ROOT


def _index_rows(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        row_id = row.get("id")
        if row_id:
            out[str(row_id)] = row
    return out


def _collect_ids_and_paths(repo_root: Path, *, full: bool) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    rel_paths: list[str] = []
    for rel in discover_targets(repo_root, full=full):
        record = build_file_record(repo_root, rel)
        if record is None:
            continue
        rel_paths.append(record.rel_path)
        ids.append(record.stable_id)
        if record.legacy_id:
            ids.append(record.legacy_id)
    return ids, rel_paths


def _print_human(report) -> None:
    print(f"repo_root: {report.repo_root}")
    print(f"scanned: {report.scanned}")
    print(f"counts: {json.dumps(report.counts, sort_keys=True)}")
    print(f"recommendation: {report.recommendation}")
    if report.write_mode is not None:
        wm = report.write_mode
        print(
            f"write_mode: kb={wm.enable_write_kb} opus={wm.enable_write_opus} "
            f"({wm.reason})"
        )
    print()
    for row in report.results:
        if row["status"] == "ok":
            continue
        print(
            f"- {row['rel_path']} [{row['kind']}] "
            f"status={row['status']} sha={row['sha256'][:12]}… "
            f"kb={row['kb'].get('id')} opus={row['opus'].get('id')}"
        )


def run_check(pg: PgBridge, repo_root: Path, *, full: bool, as_json: bool) -> int:
    ids, rel_paths = _collect_ids_and_paths(repo_root, full=full)
    kb_rows = _index_rows(pg.knowledge_rows_for_file_audit(ids, rel_paths))
    opus_rows = _index_rows(pg.opus_rows_for_file_audit(rel_paths))
    report = build_audit_report(repo_root, full=full, kb_rows=kb_rows, opus_rows=opus_rows)
    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_human(report)
    issues = report.scanned - report.counts.get("ok", 0)
    return 0 if issues == 0 else 1


def run_writes(
    pg: PgBridge,
    repo_root: Path,
    *,
    full: bool,
    write_kb: bool,
    write_opus: bool,
    agent: str,
) -> int:
    written_kb = 0
    written_opus = 0
    for rel in discover_targets(repo_root, full=full):
        record = build_file_record(repo_root, rel)
        if record is None:
            continue
        if write_kb:
            pg.knowledge_put(kb_payload(record))
            written_kb += 1
        if write_opus:
            payload = opus_payload(record, agent=agent)
            if pg.opus_put(payload):
                written_opus += 1
    print(
        json.dumps(
            {
                "write_kb": write_kb,
                "write_opus": write_opus,
                "written_kb": written_kb,
                "written_opus": written_opus,
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="Report KB/Opus coverage without writes (default)",
    )
    parser.add_argument(
        "--write-kb",
        action="store_true",
        help="Upsert structured records into public.knowledge",
    )
    parser.add_argument(
        "--write-opus",
        action="store_true",
        help="Upsert compact records into opus_atoms",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include repo-local markdown/python trees beyond key files",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repo root (defaults to willow-2.0 checkout)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable report")
    parser.add_argument("--agent", default="willow", help="Agent label for Opus writes")
    args = parser.parse_args()

    repo_root = _repo_root(args.repo_root)
    if not repo_root.is_dir():
        print(json.dumps({"error": "repo_root_not_found", "path": str(repo_root)}))
        return 2

    if try_connect() is None:
        print(json.dumps({"error": "postgres_not_connected"}))
        return 2

    pg = PgBridge()
    try:
        if args.write_kb or args.write_opus:
            return run_writes(
                pg,
                repo_root,
                full=args.full,
                write_kb=args.write_kb,
                write_opus=args.write_opus,
                agent=args.agent,
            )
        return run_check(pg, repo_root, full=args.full, as_json=args.json)
    finally:
        pg.close()


if __name__ == "__main__":
    raise SystemExit(main())
