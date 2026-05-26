"""
install_cursor.py — Wire Fylgja into Cursor (delegates to install_project).

Run: python3 -m willow.fylgja.install_cursor [--dry-run] [--agent AGENT_NAME]
Prefer: python3 -m willow.fylgja.install_project <agent> --ide cursor
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from willow.fylgja.install_project import install_project
from willow.fylgja.project_env import resolve_agent_name, repo_root

_PACKAGE_ROOT = Path(__file__).parent.parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Wire Fylgja into Cursor hooks.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--package-root", type=Path, default=_PACKAGE_ROOT)
    parser.add_argument("--agent", default="", help="Agent id (default: resolve from env/active-agent)")
    args = parser.parse_args()

    root = args.package_root or repo_root()
    agent = args.agent.strip() or resolve_agent_name(root)

    install_project(
        agent_name=agent,
        ides=["cursor"],
        package_root=root,
        dry_run=args.dry_run,
        claude_global=False,
    )


if __name__ == "__main__":
    main()
