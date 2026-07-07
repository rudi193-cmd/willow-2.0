#!/usr/bin/env python3
"""
register_jeles_sessions.py — Bulk-register session JSONL files into jeles_sessions.
b17: JLSREG  ΔΣ=42

Scans Claude Code (~/.claude/projects) and Cursor (~/.cursor/projects/.../agent-transcripts)
for fleet repo sessions, skips already-registered jsonl_path rows, and registers new
sessions so extract_jeles_corpus.py / mem_jeles_extract can process them.

Default: four operator repos (willow, willow-2.0, safe-app-store-public, DispatchesFromReality).

Usage:
    WILLOW_AGENT_NAME=willow python3 scripts/register_jeles_sessions.py --dry-run
    WILLOW_AGENT_NAME=willow python3 scripts/register_jeles_sessions.py
    WILLOW_AGENT_NAME=willow python3 scripts/register_jeles_sessions.py --project willow-2.0
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.agent_identity import require_agent_name
from core.pg_bridge import PgBridge
from fleet_repos import FLEET_BY_NAME, FLEET_REPOS, FleetRepo, discover_jsonl_paths

logging.basicConfig(level=logging.INFO, format="%(asctime)s [jlsreg] %(message)s")
log = logging.getLogger("jlsreg")

AGENT = require_agent_name()


def _is_turn_record(obj: dict) -> bool:
    kind = obj.get("type") or obj.get("role") or ""
    return kind in ("human", "assistant", "user")


def _count_turns(path: Path) -> int:
    count = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if _is_turn_record(obj):
                    count += 1
    except Exception:
        pass
    return count


def _already_registered_paths(pg: PgBridge) -> set[str]:
    with pg.conn.cursor() as cur:
        cur.execute("SELECT jsonl_path FROM jeles_sessions")
        return {row[0] for row in (cur.fetchall() or [])}


def discover_candidates(repos: tuple[FleetRepo, ...]) -> list[tuple[Path, FleetRepo]]:
    return discover_jsonl_paths(repos=repos)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-register session JSONLs into jeles_sessions")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--project",
        choices=sorted(FLEET_BY_NAME),
        default="",
        help="Limit scan to one fleet repo (default: all four)",
    )
    args = parser.parse_args()

    repos = (FLEET_BY_NAME[args.project],) if args.project else FLEET_REPOS
    candidates = discover_candidates(repos)
    if not candidates:
        log.warning("No session JSONL files found for repos: %s", ", ".join(r.name for r in repos))
        return 0

    pg = PgBridge()
    registered = _already_registered_paths(pg)
    log.info("Already registered (all agents): %d jsonl paths", len(registered))

    new = [(path, repo) for path, repo in candidates if str(path) not in registered]
    log.info(
        "Discovered %d jsonl files across %d repo(s); %d new to register",
        len(candidates),
        len(repos),
        len(new),
    )
    by_repo: dict[str, int] = {}
    for _, repo in new:
        by_repo[repo.name] = by_repo.get(repo.name, 0) + 1
    for name, count in sorted(by_repo.items()):
        log.info("  %s: %d new", name, count)

    ingested = 0
    for path, repo in new:
        session_id = path.stem
        file_size = path.stat().st_size
        turn_count = _count_turns(path)
        cwd = str(repo.cwd)

        if args.dry_run:
            log.info("[DRY] %s  repo=%s  turns=%d  size=%d", session_id[:8], repo.name, turn_count, file_size)
            ingested += 1
            continue

        result = pg.jeles_register_jsonl(
            agent=AGENT,
            jsonl_path=str(path),
            session_id=session_id,
            cwd=cwd,
            turn_count=turn_count,
            file_size=file_size,
        )
        if "error" in result:
            log.warning("Failed %s (%s): %s", session_id[:8], repo.name, result["error"])
        else:
            log.info("Registered %s → %s  repo=%s  turns=%d", session_id[:8], result["id"], repo.name, turn_count)
            ingested += 1

    log.info("Done. registered=%d", ingested)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
