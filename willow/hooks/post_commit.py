#!/usr/bin/env python3
"""
willow/hooks/post_commit.py — Commit atom extraction entry point.

Invoked by the hook pipeline (willow/hooks/runner.py, batched at session
shutdown) — NOT wired as a per-commit .git/hooks/post-commit script in this
checkout. The old docstring claimed per-commit timing that never existed
(2026-07-03 audit, bug 1). Wire .git/hooks/post-commit to this file if
per-commit granularity is ever needed; it extracts HEAD either way.
"""

import sys
import os
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import extract_commit_atom
from willow.hooks.kb_writer import write_atom_to_kb


def main():
    """Extract and store atom from HEAD commit."""
    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return

    try:
        # Get HEAD commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return

        commit_hash = result.stdout.strip()

        # Extract atom (skips merge/WIP commits)
        atom = extract_commit_atom(commit_hash)
        if not atom:
            return

        # Write to KB with dedup check
        write_atom_to_kb(atom, dedup_key=commit_hash)

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[post-commit] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
