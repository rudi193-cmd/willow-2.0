#!/usr/bin/env python3
"""
willow/hooks/post_merge.py — Post-merge hook entry point.

Called by .git/hooks/post-merge after merging a branch.
Extracts feature-level atom and writes to KB.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import extract_merge_atom
from core.pg_bridge import PgBridge


def get_merge_branch_name() -> str:
    """Try to extract branch name from merge commit message."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        msg = result.stdout.strip()
        # Format: "Merge branch 'branch-name' ..."
        import re
        match = re.search(r"Merge branch '([^']+)'", msg)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "unknown"


def main():
    """Extract and store atom from merge commit."""
    import json

    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return  # Disabled

    try:
        # Get HEAD commit hash (should be merge commit)
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

        # Write to KB
        try:
            bridge = PgBridge()
            cur = bridge.conn.cursor()
            cur.execute("""
                INSERT INTO knowledge
                (title, summary, category, source_type, b17, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                atom.title,
                atom.summary,
                atom.category,
                atom.source_type,
                atom.b17,
                atom.created_at,
            ))
            bridge.conn.commit()
            bridge.conn.close()

            if os.environ.get("WILLOW_ATOM_VERBOSE"):
                print(f"[atom-merge] {atom.b17}: {atom.title}")

        except Exception as e:
            if os.environ.get("WILLOW_ATOM_VERBOSE"):
                print(f"[atom-merge] Error writing to KB: {e}", file=sys.stderr)

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[atom-merge] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
