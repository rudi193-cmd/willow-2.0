"""
think_map/store.py — SOIL-backed Think Map persistence.
b17: THNK1  ΔΣ=42

SOIL collection: willow-dashboard/think_maps
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import soil

_COLLECTION = "willow-dashboard/think_maps"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _map_id() -> str:
    short = uuid.uuid4().hex[:6]
    return f"b17:THNK1-{short}"


def _node_id() -> str:
    return f"n{uuid.uuid4().hex[:4]}"


# ── Create ────────────────────────────────────────────────────────────────────

def new_map(problem: str, created_by: str = "sean", source: dict | None = None) -> dict:
    """Create a new Think Map with a center problem node. Returns the record."""
    mid = _map_id()
    record: dict[str, Any] = {
        "id": mid,
        "status": "draft",
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": created_by,
        "source": source or {"type": "manual", "ref": ""},
        "center": {
            "id": "n0",
            "text": problem,
            "kind": "problem",
        },
        "nodes": [],
    }
    soil.put(_COLLECTION, mid, record)
    return record


# ── Read ──────────────────────────────────────────────────────────────────────

def get_map(mid: str) -> dict | None:
    return soil.get(_COLLECTION, mid)


def list_maps(status: str | None = None) -> list[dict]:
    records = soil.all_records(_COLLECTION)
    if status:
        records = [r for r in records if r.get("status") == status]
    return sorted(records, key=lambda r: r.get("updated_at", ""), reverse=True)


def latest_draft() -> dict | None:
    drafts = list_maps(status="draft")
    return drafts[0] if drafts else None


# ── Mutate ────────────────────────────────────────────────────────────────────

def _save(record: dict) -> dict:
    record["updated_at"] = _now()
    soil.put(_COLLECTION, record["id"], record)
    return record


def add_approach(mid: str, text: str, tradeoff: str, recommended: bool = False) -> dict:
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    if r["status"] != "draft":
        raise ValueError(f"Map {mid} is {r['status']} — cannot edit")
    node = {
        "id": _node_id(),
        "parent": "n0",
        "kind": "approach",
        "text": text,
        "tradeoff": tradeoff,
        "recommended": recommended,
    }
    # Ensure only one recommended
    if recommended:
        for n in r["nodes"]:
            if n.get("kind") == "approach":
                n["recommended"] = False
    r["nodes"].append(node)
    return _save(r)


def add_constraint(mid: str, text: str, hard: bool = True) -> dict:
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    node = {
        "id": _node_id(),
        "parent": "n0",
        "kind": "constraint",
        "text": text,
        "hard": hard,
    }
    r["nodes"].append(node)
    return _save(r)


def add_satellite(mid: str, text: str, ref: str = "", pinned: bool = False) -> dict:
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    node = {
        "id": _node_id(),
        "parent": None,
        "kind": "satellite",
        "text": text,
        "ref": ref,
        "pinned": pinned,
    }
    r["nodes"].append(node)
    return _save(r)


def set_recommended(mid: str, node_id: str) -> dict:
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    for n in r["nodes"]:
        if n.get("kind") == "approach":
            n["recommended"] = n["id"] == node_id
    return _save(r)


def set_center(mid: str, text: str) -> dict:
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    r["center"]["text"] = text
    return _save(r)


def delete_node(mid: str, node_id: str) -> dict:
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    r["nodes"] = [n for n in r["nodes"] if n["id"] != node_id]
    return _save(r)


# ── Validation ────────────────────────────────────────────────────────────────

def validate(record: dict) -> list[str]:
    """Return list of validation errors. Empty = ready to confirm."""
    errors = []
    center_text = record.get("center", {}).get("text", "")
    if len(center_text) < 10:
        errors.append("Center problem must be at least 10 characters")

    approaches = [n for n in record.get("nodes", []) if n.get("kind") == "approach"]
    if len(approaches) < 3:
        errors.append(f"Need 3 approach branches (have {len(approaches)})")
    if len(approaches) > 3:
        errors.append(f"Too many approaches ({len(approaches)}) — pick 3 or merge")

    for a in approaches:
        if len(a.get("tradeoff", "")) < 5:
            errors.append(f"Approach '{a['text'][:30]}' needs a tradeoff (≥ 5 chars)")

    if approaches and not any(a.get("recommended") for a in approaches):
        errors.append("One approach must be marked recommended")

    return errors


# ── Confirm ───────────────────────────────────────────────────────────────────

def confirm_map(mid: str) -> dict:
    """Lock a map as confirmed. Raises ValueError if validation fails."""
    r = get_map(mid)
    if not r:
        raise KeyError(mid)
    if r["status"] == "confirmed":
        return r
    errors = validate(r)
    if errors:
        raise ValueError("Cannot confirm:\n" + "\n".join(f"  - {e}" for e in errors))
    r["status"] = "confirmed"
    r["confirmed_at"] = _now()
    return _save(r)
