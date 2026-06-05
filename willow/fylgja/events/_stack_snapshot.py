"""Shared stack snapshot helpers for session_start / stop / shutdown hooks."""
from __future__ import annotations


def parse_agent_task_list(result) -> list[dict]:
    """Normalize agent_task_list MCP result to open task rows."""
    rows: list = []
    if isinstance(result, dict):
        rows = result.get("pending") or []
    elif isinstance(result, list):
        rows = result
    return [
        {
            "id": t.get("id", ""),
            "title": (t.get("task") or t.get("title", ""))[:80],
            "status": t.get("status", "pending"),
        }
        for t in rows
        if isinstance(t, dict)
    ]


def normalize_stack_record(snap) -> dict:
    """soil_get result → stack dict, or {} if missing."""
    if not isinstance(snap, dict) or snap.get("error") == "not_found":
        return {}
    return snap
