#!/usr/bin/env python3
"""
willow/hooks/kb_writer.py — Consolidated KB writer for atom extraction.

All hooks use this to write atoms, ensuring:
- Content field always stored
- Deduplication at DB level
- Consistent error handling
- No code triplication
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import Atom
from core.pg_bridge import PgBridge


def write_atom_to_kb(atom: Atom, dedup_key: Optional[str] = None) -> bool:
    """Write atom to KB with deduplication and content storage.

    Args:
        atom: Atom object to write
        dedup_key: Optional unique key for dedup check (e.g., commit hash).
                   If provided, skips insert if key already exists.

    Returns:
        True if written, False if skipped or error
    """
    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        # Check deduplication if key provided
        if dedup_key:
            # Commits/merges: the key is the commit hash. Everything else:
            # the caller's key is stored in content->>'dedup_key' and matched
            # exactly. Never dedup on title — recurring titles ("Tests: 2
            # newly passing") collided forever, silently swallowing every
            # later event with the same title (2026-07-05 audit).
            if atom.source_type in ('commit', 'merge'):
                cur.execute(
                    "SELECT id FROM knowledge WHERE source_type = %s AND content->>'commit' = %s",
                    (atom.source_type, dedup_key)
                )
            else:
                atom.content["dedup_key"] = dedup_key
                cur.execute(
                    "SELECT id FROM knowledge WHERE source_type = %s AND content->>'dedup_key' = %s",
                    (atom.source_type, dedup_key)
                )

            if cur.fetchone():
                bridge.close()
                return False  # Already exists

        # Insert with content field
        cur.execute("""
            INSERT INTO knowledge
            (id, title, summary, category, source_type, created_at, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            atom.id,
            atom.title,
            atom.summary,
            atom.category,
            atom.source_type,
            atom.created_at,
            json.dumps(atom.content),
        ))
        bridge.conn.commit()

        # Generate embedding via nomic-embed-text so the atom is visible to semantic search
        try:
            import urllib.request as _urllib
            import json as _json
            text_for_embed = f"{atom.title}. {atom.summary}"[:2000]
            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/embeddings"
            payload = _json.dumps({"model": "nomic-embed-text", "prompt": text_for_embed}).encode()
            req = _urllib.Request(ollama_url, data=payload, headers={"Content-Type": "application/json"})
            with _urllib.urlopen(req, timeout=10) as resp:
                embedding = _json.loads(resp.read())["embedding"]
            cur.execute(
                "UPDATE knowledge SET embedding = %s WHERE id = %s",
                (_json.dumps(embedding), atom.id),
            )
            bridge.conn.commit()
        except Exception:
            pass  # Embedding is best-effort; atom is already written

        bridge.close()

        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            source_tag = atom.source_type.replace("_", "-")
            print(f"[atom-{source_tag}] {atom.id[:8]}: {atom.title[:60]}")

        return True

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[atom-writer] Error: {e}", file=sys.stderr)
        return False
