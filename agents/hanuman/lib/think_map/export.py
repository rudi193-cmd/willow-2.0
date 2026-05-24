"""
think_map/export.py — Export a confirmed Think Map to KB atom + SOIL record.
b17: THNK3  ΔΣ=42

Exports confirmed maps only. Produces:
  - SOIL record in willow-dashboard/think_map_exports
  - KB atom (tier=frontier, category=decision)
  - Optional: fork via fork_create for the recommended approach
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agents.hanuman.lib.think_map.store import get_map
from core import soil

_EXPORT_COLLECTION = "willow-dashboard/think_map_exports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mcp(tool: str, args: dict, timeout: int = 20) -> dict:
    try:
        from willow.fylgja._mcp import call
        return call(tool, args, timeout=timeout)
    except Exception as exc:
        return {"error": str(exc)}


# ── Summary builder ────────────────────────────────────────────────────────────

def _build_summary(record: dict) -> str:
    center = record.get("center", {}).get("text", "")
    nodes = record.get("nodes", [])
    approaches = [n for n in nodes if n.get("kind") == "approach"]
    constraints = [n for n in nodes if n.get("kind") == "constraint"]
    satellites = [n for n in nodes if n.get("kind") == "satellite"]

    rec = next((a for a in approaches if a.get("recommended")), None)

    lines = [f"Problem: {center}", ""]

    lines.append("Approaches considered:")
    for a in approaches:
        star = "(recommended) " if a.get("recommended") else ""
        lines.append(f"  {star}{a['text']}")
        if a.get("tradeoff"):
            lines.append(f"    Tradeoff: {a['tradeoff']}")

    if rec:
        lines += ["", f"Decision: {rec['text']}"]
        if rec.get("tradeoff"):
            lines.append(f"Tradeoff accepted: {rec['tradeoff']}")

    if constraints:
        lines.append("")
        lines.append("Constraints:")
        for c in constraints:
            kind = "hard" if c.get("hard") else "soft"
            lines.append(f"  [{kind}] {c['text']}")

    if satellites:
        lines.append("")
        lines.append("Context:")
        for s in satellites:
            ref = f" ({s['ref']})" if s.get("ref") else ""
            lines.append(f"  {s['text']}{ref}")

    return "\n".join(lines)


def _build_title(record: dict) -> str:
    center = record.get("center", {}).get("text", "")
    rec = next(
        (n for n in record.get("nodes", []) if n.get("kind") == "approach" and n.get("recommended")),
        None,
    )
    date = (record.get("confirmed_at") or record.get("updated_at") or "")[:10]
    if rec:
        return f"Think Map: {center[:60]} -> {rec['text'][:40]} ({date})"
    return f"Think Map: {center[:80]} ({date})"


# ── KB ingest ──────────────────────────────────────────────────────────────────

def _ingest_kb(record: dict, summary: str, title: str) -> str:
    """Ingest map as KB atom. Returns atom id or empty string on failure."""
    nodes = record.get("nodes", [])
    approaches = [n for n in nodes if n.get("kind") == "approach"]
    rec = next((a for a in approaches if a.get("recommended")), None)

    keywords = ["think-map", "decision"]
    center_words = record.get("center", {}).get("text", "").lower().split()
    keywords += [w for w in center_words if len(w) > 4][:5]
    if rec:
        keywords += [w for w in rec["text"].lower().split() if len(w) > 4][:3]

    result = _mcp("kb_ingest", {
        "app_id": "hanuman",
        "title": title,
        "summary": summary,
        "category": "decision",
        "tier": "frontier",
        "source_type": "think_map",
        "source_id": record["id"],
        "keywords": list(dict.fromkeys(keywords)),
        "tags": ["think-map", "confirmed"],
        "confidence": 0.9,
    }, timeout=30)

    return str(result.get("id", result.get("atom_id", ""))) if not result.get("error") else ""


# ── Fork ───────────────────────────────────────────────────────────────────────

def _create_fork(record: dict, export_id: str) -> str:
    """Create a git worktree for the recommended approach. Returns fork id or ''."""
    rec = next(
        (n for n in record.get("nodes", []) if n.get("kind") == "approach" and n.get("recommended")),
        None,
    )
    if not rec:
        return ""

    slug = rec["text"].lower().replace(" ", "-")[:40]
    branch = f"think-map/{record['id'][-6:]}-{slug}"

    result = _mcp("fork_create", {
        "app_id": "hanuman",
        "branch": branch,
        "label": rec["text"][:80],
        "source_map_id": record["id"],
        "export_id": export_id,
    }, timeout=20)

    return str(result.get("id", result.get("fork_id", ""))) if not result.get("error") else ""


# ── Main entry ─────────────────────────────────────────────────────────────────

def export_map(mid: str, create_fork: bool = False) -> dict:
    """
    Export a confirmed Think Map to SOIL + KB.
    Raises ValueError if map is not confirmed.
    Returns the export record.
    """
    record = get_map(mid)
    if not record:
        raise KeyError(mid)
    if record.get("status") != "confirmed":
        raise ValueError(f"Map {mid} is not confirmed (status={record.get('status')})")

    # Check for existing export
    existing = soil.get(_EXPORT_COLLECTION, mid)
    if existing:
        return existing

    title = _build_title(record)
    summary = _build_summary(record)

    kb_atom_id = _ingest_kb(record, summary, title)

    export_id = f"exp-{mid[-6:]}"
    fork_id = _create_fork(record, export_id) if create_fork else ""

    rec = next(
        (n for n in record.get("nodes", []) if n.get("kind") == "approach" and n.get("recommended")),
        None,
    )

    export_record = {
        "id": export_id,
        "map_id": mid,
        "title": title,
        "summary": summary,
        "recommended_approach": rec["text"] if rec else "",
        "recommended_tradeoff": rec.get("tradeoff", "") if rec else "",
        "kb_atom_id": kb_atom_id,
        "fork_id": fork_id,
        "exported_at": _now(),
        "confirmed_at": record.get("confirmed_at", ""),
    }

    soil.put(_EXPORT_COLLECTION, export_id, export_record)
    return export_record
