#!/usr/bin/env python3
"""One-shot: ingest fylgja session continuity wiring doc into Postgres KB."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs" / "kb" / "fylgja-session-continuity-wiring.md"


def main() -> int:
    if not DOC.is_file():
        print(f"missing doc: {DOC}", file=sys.stderr)
        return 1

    body = DOC.read_text(encoding="utf-8")
    from core.pg_bridge import PgBridge

    pg = PgBridge()
    pg._ensure_conn()

    content = {
        "summary": (
            "Canonical Fylgja wiring for handoff (select_best_handoff, build_handoff_db, "
            "SessionStart [HANDOFF], handoff_write) and persona (willow.fylgja.persona, "
            "SessionStart [PERSONA], prompt_submit selection). Do not use timestamp-only "
            "handoff_latest or unwired scripts/persona.py."
        ),
        "open_threads": [],
        "agreements": [
            "Handoff write: kb_ingest + markdown in ~/.willow/handoffs/{agent}/ + handoff_rebuild",
            "Handoff read: handoff_latest uses select_best_handoff not max timestamp",
            "Persona: willow/fylgja/persona.py wired via session_start + prompt_submit hooks",
            "scripts/persona.py is CLI wrapper only; paths via project_env.repo_root()",
        ],
        "key_actions": [
            "sap/handoff_index.py — select_best_handoff, extract_next_bite",
            "sap/sap_mcp.py — handoff_latest merges KB + SQLite by richness",
            "sap/tools/build_handoff_db.py — index legacy SESSION_HANDOFF_* + numbered threads",
            "willow/fylgja/events/session_start.py — [HANDOFF] and [PERSONA] anchor blocks",
            "willow/fylgja/persona.py — picker, selection, context load",
            "willow/fylgja/handoff_write.py — canonical markdown path",
        ],
        "next_steps": [
            "Verify handoff_rebuild + handoff_latest after any hook change",
            "New session must show [HANDOFF] and [PERSONA] in anchor",
        ],
        "tools_used": ["kb_ingest", "handoff_rebuild", "handoff_latest"],
        "signals": {"health": "ok", "doc_path": str(DOC.relative_to(ROOT))},
        "full_doc": body[:12000],
        "keywords": [
            "handoff", "persona", "session_start", "prompt_submit",
            "select_best_handoff", "build_handoff_db", "fylgja", "hooks",
        ],
        "tags": ["fylgja", "handoff", "persona", "hooks", "canonical", "architecture"],
        "pr": "#88",
        "branch": "fix/handoff-pipeline",
    }

    atom_id = pg.gen_id(8)
    pg.knowledge_put({
        "id": atom_id,
        "project": "hanuman",
        "domain": "fylgja",
        "title": "Fylgja session continuity wiring — handoff + persona (canonical)",
        "summary": content["summary"],
        "source_type": "session",
        "source_id": "fix/handoff-pipeline",
        "category": "architecture",
        "tier": "canonical",
        "confidence": 1.0,
        "content": content,
    })
    print(json.dumps({"atom_id": atom_id, "title": content["summary"][:80]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
