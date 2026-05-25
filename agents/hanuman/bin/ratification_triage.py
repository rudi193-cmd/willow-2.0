#!/usr/bin/env python3
"""
ratification_triage.py — Periodic ratification backlog digest.
b17: TRGE1  ΔΣ=42

Reads four sources, ranks pending items by urgency, and surfaces the top 5
to Grove #hanuman and writes a machine-readable SOIL record.

Sources:
  1. SOIL hanuman/atom_drift_results  — drifted/uncertain atoms not yet resolved
  2. Postgres knowledge (frontier tier, older than 7 days, never ratified)
  3. SOIL upstream_steward/pending    — draft items past veto window
  4. Postgres knowledge               — atoms never surfaced to any agent (unread)

Ranking: staleness_days × confidence — highest score first.

Usage:
    python3 agents/hanuman/bin/ratification_triage.py [--dry-run]
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import soil
from core.pg_bridge import PgBridge
from core.kb_read_log import read_atoms_set, record_read

_APP_ID = "hanuman"
_DRIFT_COLLECTION    = "hanuman/atom_drift_results"
_UPSTREAM_COLLECTION = "upstream_steward/pending"
_DIGEST_COLLECTION   = "hanuman/triage_digest"
_FRONTIER_STALE_DAYS = 7
_UNREAD_STALE_DAYS   = 7
_TOP_N = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(iso: str) -> float:
    """Return how many days ago an ISO timestamp was. Returns 0.0 on parse error."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (_now() - dt).total_seconds() / 86400
    except Exception:
        return 0.0


# ── Source readers ────────────────────────────────────────────────────────────

def _read_drift_items() -> list[dict]:
    items = []
    results = soil.all_records(_DRIFT_COLLECTION)
    for r in results:
        status = r.get("status", "open")
        if status in ("auto_resolved", "resolved", "acked"):
            continue
        verdict = r.get("aggregate_verdict", "")
        if verdict not in ("drifted", "uncertain"):
            continue
        confidence = float(r.get("max_confidence", 0.5))
        scanned = r.get("scanned_at", _now().isoformat())
        staleness = _days_ago(scanned)
        items.append({
            "type": "KB_DRIFT",
            "id": r.get("atom_id", ""),
            "label": r.get("atom_title", "")[:60],
            "staleness_days": staleness,
            "confidence": confidence,
            "score": staleness * confidence,
            "action": f"kb_truth_drift.py resolve {r.get('atom_id', '')}",
            "status": status,
            "verdict": verdict,
        })
    return items


def _read_frontier_items(pg: PgBridge) -> list[dict]:
    """Frontier atoms older than _FRONTIER_STALE_DAYS that have never been ratified."""
    items = []
    cutoff = _now() - timedelta(days=_FRONTIER_STALE_DAYS)
    try:
        import psycopg2.extras
        pg._ensure_conn()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, confidence, valid_at
                FROM knowledge
                WHERE tier = 'frontier'
                  AND invalid_at IS NULL
                  AND valid_at < %s
                ORDER BY valid_at ASC
                LIMIT 50
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        print(f"[warn] frontier query failed: {exc}", file=sys.stderr)
        return []

    for row in rows:
        valid_at = row["valid_at"]
        if hasattr(valid_at, "isoformat"):
            valid_at_str = valid_at.isoformat()
        else:
            valid_at_str = str(valid_at)
        staleness = _days_ago(valid_at_str)
        confidence = float(row.get("confidence") or 0.5)
        items.append({
            "type": "FRONTIER",
            "id": str(row["id"]),
            "label": (row.get("title") or "")[:60],
            "staleness_days": staleness,
            "confidence": confidence,
            "score": staleness * confidence,
            "action": f"willow.sh kb ratify {row['id']}",
        })
    return items


def _read_upstream_items() -> list[dict]:
    """Upstream drafts older than 1 day waiting for review."""
    items = []
    records = soil.all_records(_UPSTREAM_COLLECTION)
    for r in records:
        if r.get("status") in ("posted", "closed", "skipped"):
            continue
        if r.get("lane") not in ("draft", "urgent"):
            continue
        created = r.get("created_at", _now().isoformat())
        staleness = _days_ago(created)
        if staleness < 1.0:
            continue
        # Urgency proxy: urgent lane gets confidence=0.9, draft=0.7
        confidence = 0.9 if r.get("lane") == "urgent" else 0.7
        wid = r.get("work_id") or r.get("_id", "")
        items.append({
            "type": "UPSTREAM",
            "id": wid,
            "label": f"{r.get('repo', '')} — {r.get('title', '')[:40]}",
            "staleness_days": staleness,
            "confidence": confidence,
            "score": staleness * confidence,
            "action": f"willow.sh upstream approve {wid}",
            "veto_deadline": r.get("veto_deadline", ""),
        })
    return items


# ── Unread atoms ─────────────────────────────────────────────────────────────

def _read_unread_items(pg: PgBridge) -> list[dict]:
    """Atoms written to KB but never surfaced to any agent in the last N days."""
    recently_read = read_atoms_set(since_days=_UNREAD_STALE_DAYS)
    cutoff = _now() - timedelta(days=_UNREAD_STALE_DAYS)
    items = []
    try:
        import psycopg2.extras
        pg._ensure_conn()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, confidence, valid_at, tier
                FROM knowledge
                WHERE invalid_at IS NULL
                  AND valid_at < %s
                ORDER BY valid_at ASC
                LIMIT 100
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        print(f"[warn] unread query failed: {exc}", file=sys.stderr)
        return []

    for row in rows:
        atom_id = str(row["id"])
        if atom_id in recently_read:
            continue
        valid_at = row["valid_at"]
        valid_at_str = valid_at.isoformat() if hasattr(valid_at, "isoformat") else str(valid_at)
        staleness = _days_ago(valid_at_str)
        confidence = float(row.get("confidence") or 0.5)
        items.append({
            "type": "UNREAD",
            "id": atom_id,
            "label": (row.get("title") or "")[:60],
            "staleness_days": staleness,
            "confidence": confidence,
            "score": staleness * confidence,
            "action": f"kb_get {atom_id}",
            "tier": row.get("tier", ""),
        })
    return items


# ── Digest writer ─────────────────────────────────────────────────────────────

def _format_grove_message(ranked: list[dict]) -> str:
    lines = [f"[TRIAGE] {len(ranked)} item(s) need ratification (ranked by urgency)\n"]
    for i, item in enumerate(ranked[:_TOP_N], 1):
        staleness = item["staleness_days"]
        conf = item["confidence"]
        label = item["label"]
        itype = item["type"]
        action = item["action"]
        lines.append(
            f"{i}. [{itype}] {label} "
            f"({staleness:.0f}d stale, {conf:.0%} conf)\n"
            f"   Action: {action}"
        )
    return "\n".join(lines)


def _send_grove(message: str) -> bool:
    try:
        from willow.fylgja._mcp import call
        result = call("grove_send_message", {
            "channel_name": "hanuman",
            "content": message,
            "sender_agent_id": _APP_ID,
        }, timeout=15)
        return not (isinstance(result, dict) and result.get("error"))
    except Exception as exc:
        print(f"[warn] Grove send failed: {exc}", file=sys.stderr)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> int:
    pg = PgBridge()

    drift_items    = _read_drift_items()
    frontier_items = _read_frontier_items(pg)
    upstream_items = _read_upstream_items()
    unread_items   = _read_unread_items(pg)

    all_items = drift_items + frontier_items + upstream_items + unread_items
    ranked = sorted(all_items, key=lambda x: x["score"], reverse=True)

    total = len(ranked)
    top = ranked[:_TOP_N]

    print(f"\n[TRIAGE] {total} item(s) pending  "
          f"(drift={len(drift_items)} frontier={len(frontier_items)} "
          f"upstream={len(upstream_items)} unread={len(unread_items)})")
    for i, item in enumerate(top, 1):
        print(
            f"  {i}. [{item['type']}] {item['label'][:55]} "
            f"({item['staleness_days']:.0f}d, {item['confidence']:.0%})"
        )
        print(f"     → {item['action']}")

    if not dry_run:
        # Write read log for all atoms surfaced in this digest
        for item in top:
            if item["type"] in ("KB_DRIFT", "FRONTIER", "UNREAD"):
                record_read(item["id"], source="triage")

        digest = {
            "generated_at": _now().isoformat(),
            "total": total,
            "top": top,
            "counts": {
                "drift":    len(drift_items),
                "frontier": len(frontier_items),
                "upstream": len(upstream_items),
                "unread":   len(unread_items),
            },
        }
        soil.put(_DIGEST_COLLECTION, "latest", digest)
        print(f"\nDigest written → SOIL {_DIGEST_COLLECTION}/latest")

        if top:
            msg = _format_grove_message(top)
            sent = _send_grove(msg)
            if sent:
                print("Grove #hanuman notified.")
            else:
                print("Grove not available — SOIL digest only.")

        # Brief any pending kart tasks with KB context
        try:
            from agents.hanuman.bin.kb_briefer import brief_pending_tasks
            briefed = brief_pending_tasks(pg=pg)
            if briefed:
                print(f"Briefed {briefed} pending task(s) with KB context.")
        except Exception as exc:
            print(f"[warn] kb_briefer failed: {exc}", file=sys.stderr)
    else:
        print("\n[dry-run] no writes performed")

    pg.close()
    return 0


if __name__ == "__main__":
    import sys as _sys
    dry = "--dry-run" in _sys.argv
    raise SystemExit(run(dry_run=dry))
