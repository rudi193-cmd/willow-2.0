#!/usr/bin/env python3
"""Sync Willow fleet safe-app-manifest.json files to ~/SAFE/Agents/."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.safe_agents import sync_all, write_manifest, FLEET_AGENTS  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("agent", nargs="?", help="Single agent (default: all in FLEET_AGENTS)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-sign", action="store_true")
    args = p.parse_args()

    if args.agent:
        aid = args.agent.strip().lower()
        if aid not in FLEET_AGENTS:
            print(f"Unknown agent: {aid}", file=sys.stderr)
            return 1
        print(json.dumps(write_manifest(aid, force=args.force, sign=not args.no_sign), indent=2))
        return 0

    print(json.dumps(sync_all(force=args.force, sign=not args.no_sign), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
