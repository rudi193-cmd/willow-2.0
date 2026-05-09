#!/usr/bin/env python3
"""
willow/hooks/post_merge.py — Post-merge hook entry point.

Called by .git/hooks/post-merge after merging a branch.
Extracts feature-level atom and writes to KB.
"""

import sys
import os
import subprocess
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import extract_merge_atom
from willow.hooks.kb_writer import write_atom_to_kb


def get_merge_branch_name() -> str:
    """Extract branch name from merge commit message."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        match = re.search(r"Merge branch '([^']+)'", result.stdout)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "unknown"


def main():
    """Extract and store atom from merge commit."""
    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return

        commit_hash = result.stdout.strip()
        branch_name = get_merge_branch_name()

        # Extract atom
        atom = extract_merge_atom(commit_hash, branch_name)
        if not atom:
            return

        # Write to KB with dedup check
        write_atom_to_kb(atom, dedup_key=commit_hash)

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[post-merge] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
