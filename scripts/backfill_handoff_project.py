#!/usr/bin/env python3
"""Backfill project: YAML frontmatter on session handoff markdown files.

Dry-run by default. After --apply, run handoff_rebuild(app_id=<agent>) so
handoffs.db picks up the new project column.

Examples:
  python3 scripts/backfill_handoff_project.py --agent willow
  python3 scripts/backfill_handoff_project.py --agent willow --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from willow.fylgja.handoff_backfill import apply_plans, scan_agent_handoffs
from willow.fylgja.willow_home import willow_home


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill handoff project frontmatter")
    parser.add_argument("--agent", default="willow", help="Fleet agent id (default: willow)")
    parser.add_argument(
        "--handoffs-dir",
        default="",
        help="Override handoffs directory (default: ~/.willow/handoffs/<agent>)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default is dry-run JSON plan)",
    )
    args = parser.parse_args(argv)

    agent = args.agent.strip()
    handoffs_dir = (
        Path(args.handoffs_dir).expanduser()
        if args.handoffs_dir
        else willow_home() / "handoffs" / agent
    )
    plans = scan_agent_handoffs(handoffs_dir, agent)
    payload = {
        "agent": agent,
        "handoffs_dir": str(handoffs_dir),
        "planned": len(plans),
        "changes": [
            {
                "file": p.path.name,
                "from": p.current or None,
                "to": p.target,
                "reason": p.reason,
            }
            for p in plans
        ],
    }

    if not args.apply:
        print(json.dumps(payload, indent=2))
        return 0

    applied = apply_plans(plans)
    payload["applied"] = len(applied)
    payload["changes"] = applied
    print(json.dumps(payload, indent=2))
    if applied:
        print(
            f"\nNext: handoff_rebuild(app_id={agent!r}) to refresh handoffs.db",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
