"""JSON file store for sandbox changes (no SOIL/MCP — portable demo). b17: GSSM5 · ΔΣ=42"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import ChangeRecord


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[ChangeRecord]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [ChangeRecord.from_json(x) for x in raw]

    def save_all(self, rows: list[ChangeRecord]) -> None:
        data: list[dict[str, Any]] = [r.to_json() for r in rows]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def upsert(self, row: ChangeRecord) -> None:
        rows = self.load_all()
        by_id = {r.id: r for r in rows}
        by_id[row.id] = row
        self.save_all(list(by_id.values()))

    def get(self, change_id: str) -> ChangeRecord | None:
        for r in self.load_all():
            if r.id == change_id:
                return r
        return None
