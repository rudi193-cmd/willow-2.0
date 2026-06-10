"""Trace log for ratatosk explain — lightweight JSONL."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_DIR = Path.home() / ".ratatosk" / "traces"


def log_trace(trace_id: str, event: str, detail: dict[str, Any] | None = None) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / f"{trace_id}.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "detail": detail or {},
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def explain_trace(trace_id: str) -> list[dict[str, Any]]:
    path = TRACE_DIR / f"{trace_id}.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
