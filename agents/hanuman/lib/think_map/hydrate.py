"""
think_map/hydrate.py — Auto-populate Think Map satellites.
b17: THNK2  ΔΣ=42

Sources: kb_search, handoff_search, tension_scan.
Only runs on draft maps. Skips refs already present as satellites.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agents.hanuman.lib.think_map.store import get_map, add_satellite


# ── MCP bridge ────────────────────────────────────────────────────────────────

def _mcp(tool: str, args: dict, timeout: int = 20) -> dict | list:
    try:
        from willow.fylgja._mcp import call
        return call(tool, args, timeout=timeout)
    except Exception as exc:
        return {"error": str(exc)}


# ── Query building ─────────────────────────────────────────────────────────────

def _build_query(record: dict) -> str:
    parts = [record.get("center", {}).get("text", "")]
    for n in record.get("nodes", []):
        if n.get("kind") == "approach":
            parts.append(n.get("text", ""))
    return " ".join(p for p in parts if p)[:300]


def _existing_refs(record: dict) -> set:
    return {
        n.get("ref", "").strip()
        for n in record.get("nodes", [])
        if n.get("kind") == "satellite" and n.get("ref")
    }


def _existing_texts(record: dict) -> set:
    return {
        n.get("text", "").strip().lower()
        for n in record.get("nodes", [])
        if n.get("kind") == "satellite"
    }


# ── Source adapters ────────────────────────────────────────────────────────────

def _kb_candidates(query: str, limit: int) -> list[dict]:
    result = _mcp("kb_search", {"app_id": "hanuman", "query": query, "limit": limit, "semantic": True})
    if isinstance(result, dict) and result.get("error"):
        return []
    # Response shape: {knowledge: [...], jeles_atoms: [...], opus_atoms: [...]}
    items: list = []
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = (
            result.get("knowledge", [])
            + result.get("jeles_atoms", [])
            + result.get("opus_atoms", [])
        )
    out = []
    for item in items[:limit]:
        atom_id = str(item.get("id", ""))
        title = item.get("title", "")
        summary = (item.get("summary") or "")[:120]
        if title:
            text = title + (f" — {summary}" if summary else "")
            out.append({"text": text[:200], "ref": atom_id or title})
    return out


def _handoff_candidates(query: str, limit: int) -> list[dict]:
    result = _mcp("handoff_search", {"app_id": "hanuman", "query": query, "limit": limit})
    if isinstance(result, dict) and result.get("error"):
        return []
    items: list = result if isinstance(result, list) else result.get("results", result.get("handoffs", []))
    out = []
    for item in items[:limit]:
        title = item.get("title", item.get("handoff_title", ""))
        snippet = (item.get("summary") or item.get("snippet", ""))[:100]
        ref = str(item.get("id", item.get("file", title)))
        if title:
            text = title + (f" — {snippet}" if snippet else "")
            out.append({"text": text[:200], "ref": ref})
    return out


def _tension_candidates(limit: int) -> list[dict]:
    result = _mcp("tension_scan", {"app_id": "hanuman", "limit": limit, "write_kb": False}, timeout=40)
    if isinstance(result, dict) and result.get("error"):
        return []
    # Response shape varies: list of tension dicts or {tensions: [...]}
    items: list = result if isinstance(result, list) else result.get("tensions", result.get("results", []))
    out = []
    for item in items:
        desc = (item.get("description") or item.get("summary", ""))[:150]
        ref = str(item.get("id", "tension"))
        if desc:
            out.append({"text": f"[tension] {desc}", "ref": ref})
    return out[:limit]


# ── Main entry ─────────────────────────────────────────────────────────────────

def hydrate(
    mid: str,
    kb_limit: int = 3,
    handoff_limit: int = 2,
    tension_limit: int = 2,
) -> dict:
    """
    Enrich a draft Think Map with auto-generated satellite nodes.
    Returns the updated map record.
    Skips if map is confirmed or already has >= 5 satellites.
    """
    record = get_map(mid)
    if not record:
        raise KeyError(mid)
    if record.get("status") != "draft":
        return record

    existing_satellites = [n for n in record.get("nodes", []) if n.get("kind") == "satellite"]
    if len(existing_satellites) >= 5:
        return record

    query = _build_query(record)
    existing_refs = _existing_refs(record)
    existing_texts = _existing_texts(record)

    candidates = (
        _kb_candidates(query, kb_limit)
        + _handoff_candidates(query, handoff_limit)
        + _tension_candidates(tension_limit)
    )

    added = 0
    for c in candidates:
        ref = c["ref"].strip()
        text = c["text"].strip()
        if ref in existing_refs:
            continue
        if text.lower() in existing_texts:
            continue
        if len(existing_satellites) + added >= 5:
            break
        record = add_satellite(mid, text, ref=ref)
        existing_refs.add(ref)
        existing_texts.add(text.lower())
        added += 1

    return record


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("Usage: hydrate.py <map_id>")
        sys.exit(1)
    result = hydrate(sys.argv[1])
    sats = [n for n in result.get("nodes", []) if n.get("kind") == "satellite"]
    print(f"Satellites ({len(sats)}):")
    for s in sats:
        print(f"  [{s['id']}] {s['text']}")
        if s.get("ref"):
            print(f"           ref: {s['ref']}")
