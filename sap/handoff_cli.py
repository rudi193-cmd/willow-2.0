"""CLI entry for ./willow.sh handoff_latest — project-scoped handoff reads."""
from __future__ import annotations

import argparse
import json
import sys

from sap.handoff_index import fetch_latest_handoff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Latest project-scoped session handoff")
    parser.add_argument("agent", nargs="?", default="", help="Fleet agent id (default: WILLOW_AGENT_NAME)")
    parser.add_argument("--project", default="", help="Fleet project id override")
    parser.add_argument("--workspace", default="", help="Repo root for project resolution")
    args = parser.parse_args(argv)

    import os

    agent = (args.agent or os.environ.get("WILLOW_AGENT_NAME") or "").strip()
    result = fetch_latest_handoff(
        agent,
        project=args.project,
        workspace=args.workspace,
    )
    print(json.dumps(result, indent=2))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
