#!/usr/bin/env python3
"""
promote_intake.py — Norn-pass for the unified intake layer.
b17: PRMINT  ΔΣ=42

Reads pending records from ~/.willow/intake/<agent>/ and routes each to
the right KB tier using orin (mistral:7b) classify + record metadata.

Usage:
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py --dry-run
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py --no-llm
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py --all-files
    python3 scripts/promote_intake.py --fleet --no-llm --all-files
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.agent_identity import require_agent_name
from core.intake_promote import promote_agent, promote_fleet
from core.pg_bridge import PgBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [prmint] %(message)s")
log = logging.getLogger("prmint")

AGENT = require_agent_name()


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote intake records to KB tiers")
    parser.add_argument("--dry-run", action="store_true", help="Classify and route but do not write")
    parser.add_argument("--no-llm", action="store_true", help="Skip orin classify, use fallback routing only")
    parser.add_argument("--limit", type=int, default=0, help="Max records to process (0=all)")
    parser.add_argument("--days", type=int, default=7, help="Look-back window in days (ignored with --all-files)")
    parser.add_argument("--all-files", action="store_true", help="Scan every *.jsonl (not just recent days)")
    parser.add_argument("--fleet", action="store_true", help="Run for every agent intake directory")
    parser.add_argument("--agent", default=AGENT, help="Agent to process (default: $WILLOW_AGENT_NAME)")
    args = parser.parse_args()

    # LLM routing on by default; pass --no-llm for deterministic fallback only.
    use_llm = not args.no_llm

    if args.fleet:
        report = promote_fleet(
            days=args.days,
            all_files=args.all_files,
            no_llm=not use_llm,
            limit_per_agent=args.limit,
            dry_run=args.dry_run,
        )
        totals = report["totals"]
        log.info(
            "Fleet done. agents=%d pending=%d promoted=%d failed=%d dry_run=%s",
            report["agents"], totals["pending"], totals["promoted"], totals["failed"], args.dry_run,
        )
        for r in report["reports"]:
            if r["pending"]:
                log.info(
                    "  %s: pending=%d promoted=%d failed=%d routed=%s",
                    r["agent"], r["pending"], r["promoted"], r["failed"], r["routed"],
                )
        return 0 if totals["failed"] == 0 else 1

    pg = PgBridge()
    report = promote_agent(
        pg, args.agent,
        days=args.days,
        all_files=args.all_files,
        no_llm=not use_llm,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    log.info(
        "Done. agent=%s pending=%d promoted=%d failed=%d routed=%s dry_run=%s",
        report["agent"], report["pending"], report["promoted"], report["failed"],
        report["routed"], args.dry_run,
    )
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
