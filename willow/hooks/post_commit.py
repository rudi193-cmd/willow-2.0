#!/usr/bin/env python3
"""
willow/hooks/post_commit.py — Post-commit hook entry point.

Called by .git/hooks/post-commit after every commit.
Extracts atom and writes to KB.
"""

import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import extract_commit_atom
from core.pg_bridge import PgBridge

STATE_FILE = Path.home() / ".willow" / "atom_extraction_state.json"


def main():
    """Extract and store atom from HEAD commit."""
    import json

    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return  # Disabled

    try:
        # Get HEAD commit hash
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return

        commit_hash = result.stdout.strip()

        # Extract atom
        atom = extract_commit_atom(commit_hash)
        if not atom:
            return  # No atom (probably merge commit or WIP)

        # Check if already extracted
        state = {}
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
            except Exception:
                pass

        if state.get("extracted_atoms", {}).get(commit_hash):
            return  # Already extracted

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

            # Update state
            state.setdefault("extracted_atoms", {})[commit_hash] = atom.b17
            state["last_extracted_commit"] = commit_hash
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(state, indent=2))

            if os.environ.get("WILLOW_ATOM_VERBOSE"):
                print(f"[atom-extract] {atom.b17}: {atom.title}")

        except Exception as e:
            if os.environ.get("WILLOW_ATOM_VERBOSE"):
                print(f"[atom-extract] Error writing to KB: {e}", file=sys.stderr)

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[atom-extract] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
