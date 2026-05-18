"""Markdown / machine summaries for sandbox list & handoff. b17: GSSM7 · ΔΣ=42"""
from __future__ import annotations

import json

from .model import ChangeRecord, ShapeState, allowed_targets


def markdown_table(rows: list[ChangeRecord]) -> str:
    lines = [
        "| id | state | title | updated (UTC) |",
        "|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x.updated_at or x.id), reverse=True):
        lines.append(f"| `{r.id}` | {r.state.value} | {r.title} | {r.updated_at or '—'} |")
    if len(lines) == 2:
        lines.append("| — | — | *(empty store)* | — |")
    return "\n".join(lines)


def allowed_line(state: ShapeState) -> str:
    nxt = ", ".join(s.value for s in sorted(allowed_targets(state), key=lambda x: x.value))
    return f"{state.value} → [{nxt or '∅'}]"


def json_lines(rows: list[ChangeRecord]) -> str:
    return json.dumps([r.to_json() for r in rows], indent=2)
