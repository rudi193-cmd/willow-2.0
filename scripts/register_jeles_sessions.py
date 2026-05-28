#!/usr/bin/env python3
"""
register_jeles_sessions.py — Bulk-register Claude Code session JSONL files into jeles_sessions.
b17: JLSREG  ΔΣ=42

Scans ~/.claude/projects/<project>/*.jsonl, skips already-registered paths,
and registers new sessions so extract_jeles_corpus.py can process them.

Usage:
    WILLOW_AGENT_NAME=hanuman python3 scripts/register_jeles_sessions.py --dry-run
    WILLOW_AGENT_NAME=hanuman python3 scripts/register_jeles_sessions.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.agent_identity import require_agent_name
from core.pg_bridge import PgBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [jlsreg] %(message)s")
log = logging.getLogger("jlsreg")

AGENT = require_agent_name()
SESSION_DIR = Path.home() / ".claude" / "projects" / "-home-sean-campbell-willow-2-0"
CWD = os.environ.get("WILLOW_ROOT", str(Path.home() / "github" / "willow-2.0"))


def _count_turns(path: Path) -> int:
    count = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                    if obj.get("type") in ("human", "assistant"):
                        count += 1
                except Exception:
                    continue
    except Exception:
        pass
    return count


def _already_registered(pg: PgBridge) -> set[str]:
    with pg.conn.cursor() as cur:
        cur.execute("SELECT jsonl_path FROM jeles_sessions WHERE agent = %s", (AGENT,))
        return {row[0] for row in (cur.fetchall() or [])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-register session JSONLs into jeles_sessions")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SESSION_DIR.exists():
        log.error("Session directory not found: %s", SESSION_DIR)
        return 1

    pg = PgBridge()
    registered = _already_registered(pg)
    log.info("Already registered: %d sessions", len(registered))

    candidates = sorted(SESSION_DIR.glob("*.jsonl"))
    new = [p for p in candidates if str(p) not in registered]
    log.info("Found %d total, %d new to register", len(candidates), len(new))

    ingested = 0
    for path in new:
        session_id = path.stem
        file_size = path.stat().st_size
        turn_count = _count_turns(path)

        if args.dry_run:
            log.info("[DRY] %s  turns=%d  size=%d", session_id, turn_count, file_size)
            ingested += 1
            continue

        result = pg.jeles_register_jsonl(
            agent=AGENT,
            jsonl_path=str(path),
            session_id=session_id,
            cwd=CWD,
            turn_count=turn_count,
            file_size=file_size,
        )
        if "error" in result:
            log.warning("Failed %s: %s", session_id, result["error"])
        else:
            log.info("Registered %s → %s  turns=%d", session_id, result["id"], turn_count)
            ingested += 1

    log.info("Done. registered=%d", ingested)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
