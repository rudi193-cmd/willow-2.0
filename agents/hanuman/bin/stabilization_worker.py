#!/usr/bin/env python3
"""
agents/hanuman/bin/stabilization_worker.py — Post-push fleet reconciliation.
b17: STBW1 · ΔΣ=42

Reads the push event from SOIL, finds KB atoms that reference changed files
via code_graph, runs a lightweight drift check on each, invalidates stale ones,
fast-tracks corpus/corrections into intake, writes a stabilization brief, and
signals Grove.

Usage:
    python3 agents/hanuman/bin/stabilization_worker.py --push-id <id>
    python3 agents/hanuman/bin/stabilization_worker.py --sha <sha>
    python3 agents/hanuman/bin/stabilization_worker.py --dry-run
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import soil
from core.grove_gate import assert_grove as _assert_grove
from core.pg_bridge import PgBridge
from willow.fylgja.willow_home import willow_home

_APP_ID = "hanuman"
_BRIEF_COLLECTION = "willow/stabilization_brief"
_FLAG_COLLECTION = "willow/flags"
_EVENTS_COLLECTION = "willow/push_events"
_CORRECTIONS_COLLECTION = "corpus/corrections"
_CODE_GRAPH_DB = Path(os.environ.get(
    "WILLOW_CODE_GRAPH_DB",
    str(willow_home(Path(__file__).resolve().parents[3]) / "code_graph.db"),
))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ── Grove signal ──────────────────────────────────────────────────────────────

def _grove_signal(message: str) -> None:
    try:
        from willow.fylgja._mcp import call
        call("grove_send_message", {
            "channel_name": "general",
            "content": message,
            "sender_agent_id": _APP_ID,
        }, timeout=10)
    except Exception as exc:
        print(f"  [warn] Grove signal failed: {exc}", file=sys.stderr)


# ── Load push event ───────────────────────────────────────────────────────────

def _load_push_event(push_id: str | None, sha: str | None) -> dict | None:
    if sha:
        event = soil.get(_EVENTS_COLLECTION, sha)
        if event:
            return event
    if push_id:
        all_events = soil.all_records(_EVENTS_COLLECTION)
        for e in all_events:
            if e.get("push_id") == push_id:
                return e
    return None


# ── Atoms referencing changed files ──────────────────────────────────────────

def _atoms_for_files(changed_files: list[str], pg: PgBridge) -> list[dict]:
    """Find KB atoms whose summary mentions any changed file path (keyword match)."""
    if not changed_files:
        return []

    atoms: list[dict] = []
    seen: set[str] = set()

    # Build path search terms — use specific identifiers only, not short/common words
    _STOP_STEMS = {"main", "init", "base", "core", "util", "utils", "common",
                   "config", "test", "tests", "data", "index", "schema", "model"}
    stems = set()
    for f in changed_files:
        p = Path(f)
        parts = p.parts
        # Full relative path is most specific
        stems.add(f.lower())
        # Two-segment path (e.g. code_graph/indexer.py)
        if len(parts) >= 2:
            stems.add("/".join(parts[-2:]).lower())
        # Stem only if long and specific (avoids "prompt", "core", "init")
        stem = p.stem.lower()
        if len(stem) >= 10 and stem not in _STOP_STEMS and "_" in stem:
            stems.add(stem)

    try:
        pg._ensure_conn()
        import psycopg2.extras
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title, summary, tier, confidence FROM knowledge "
                "WHERE invalid_at IS NULL ORDER BY valid_at DESC LIMIT 500"
            )
            rows = cur.fetchall()
    except Exception as exc:
        print(f"  [warn] could not query KB: {exc}", file=sys.stderr)
        return []

    for row in rows:
        atom_id = str(row["id"])
        if atom_id in seen:
            continue
        text = f"{row.get('title','')} {row.get('summary','')}".lower()
        for stem in stems:
            if stem.lower() in text:
                atoms.append(dict(row))
                seen.add(atom_id)
                break

    return atoms


# ── Lightweight drift check ───────────────────────────────────────────────────

def _atom_is_stale(atom: dict, changed_files: list[str]) -> bool:
    """Heuristic: atom is likely stale if it references a changed file by name."""
    summary = (atom.get("summary") or "").lower()
    title = (atom.get("title") or "").lower()
    text = f"{title} {summary}"

    for f in changed_files:
        p = Path(f)
        # If the atom specifically names the changed file, flag it
        if p.name.lower() in text or p.stem.lower() in text:
            return True
    return False


# ── Fast-track corrections ────────────────────────────────────────────────────

def _fast_track_corrections(since_hours: int = 48, dry_run: bool = False) -> int:
    """Promote recent corpus/corrections to intake for ratification."""
    cutoff = _now() - timedelta(hours=since_hours)
    records = soil.all_records(_CORRECTIONS_COLLECTION)
    promoted = 0

    for r in records:
        created_str = r.get("created_at", "")
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        if created < cutoff:
            continue
        if r.get("promoted"):
            continue

        content = r.get("content", "").strip()
        if not content:
            continue

        if not dry_run:
            try:
                from willow.fylgja._mcp import call
                call("intake_write", {
                    "app_id": _APP_ID,
                    "title": f"correction (post-push): {content[:60]}",
                    "content": content,
                    "source": "stabilization_worker/corpus_corrections",
                    "tier": "frontier",
                    "confidence": 0.75,
                    "category": "correction",
                    "domain": "agent-behavior",
                }, timeout=15)
                soil.put(_CORRECTIONS_COLLECTION, r.get("id", ""), {**r, "promoted": True})
                promoted += 1
            except Exception as exc:
                print(f"  [warn] intake_write failed: {exc}", file=sys.stderr)
        else:
            print(f"  [dry-run] would promote correction: {content[:80]!r}")
            promoted += 1

    return promoted


# ── Write stabilization brief ─────────────────────────────────────────────────

def _write_brief(
    push_sha: str,
    invalidated: list[dict],
    corrections_promoted: int,
    changed_files: list[str],
    dry_run: bool,
) -> None:
    do_not_assume = [
        f"{Path(f).name} may have changed" for f in changed_files[:8]
    ]
    titles_invalidated = [a.get("title", a.get("id", "?"))[:60] for a in invalidated]

    summary_parts = []
    if changed_files:
        summary_parts.append(f"{len(changed_files)} file(s) changed")
    if invalidated:
        summary_parts.append(f"{len(invalidated)} atom(s) invalidated")
    if corrections_promoted:
        summary_parts.append(f"{corrections_promoted} correction(s) promoted")

    brief = {
        "push_sha": push_sha,
        "generated_at": _now_iso(),
        "ttl_hours": 72,
        "changed_files": changed_files[:30],
        "atoms_invalidated": titles_invalidated,
        "corrections_promoted": corrections_promoted,
        "do_not_assume": do_not_assume,
        "summary": ". ".join(summary_parts) + "." if summary_parts else "No significant changes detected.",
    }

    if not dry_run:
        soil.put(_BRIEF_COLLECTION, "latest", brief)
        print(f"  Brief written → SOIL {_BRIEF_COLLECTION}/latest")
    else:
        print(f"  [dry-run] brief summary: {brief['summary']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    push_id: str | None = None,
    sha: str | None = None,
    dry_run: bool = False,
) -> int:
    _assert_grove("stabilization_worker")
    print(f"\n[STABILIZATION] Starting reconciliation "
          f"(push_id={push_id or 'auto'} sha={sha or 'auto'} dry_run={dry_run})")

    # Load push event
    event = _load_push_event(push_id, sha)
    if not event:
        # Fall back: use HEAD and all files changed in last commit
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(_ROOT), "diff", "--name-only", "HEAD^", "HEAD"],
            capture_output=True, text=True,
        )
        changed_files = [f for f in result.stdout.splitlines() if f.strip()]
        push_sha = subprocess.run(
            ["git", "-C", str(_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        print(f"  No push event found — using HEAD ({push_sha[:8]}, {len(changed_files)} files)")
    else:
        changed_files = event.get("changed_files", [])
        push_sha = event.get("sha", "unknown")
        print(f"  Push event: sha={push_sha[:8]} commits={event.get('commit_count',0)} files={len(changed_files)}")

    if not changed_files:
        print("  No changed files — nothing to reconcile.")
        return 0

    pg = PgBridge()

    # Step 1: find atoms referencing changed files
    _grove_signal(f"[STABILIZATION] Reconciliation running — {len(changed_files)} changed files, scanning KB atoms…")

    candidate_atoms = _atoms_for_files(changed_files, pg)
    print(f"  {len(candidate_atoms)} candidate atom(s) reference changed files")

    # Step 2: drift check + invalidate
    invalidated: list[dict] = []
    for atom in candidate_atoms:
        if _atom_is_stale(atom, changed_files):
            atom_id = str(atom["id"])
            print(f"  → invalidating: [{atom_id}] {atom.get('title','')[:60]}")
            if not dry_run:
                try:
                    from willow.fylgja._mcp import call
                    call("kb_ingest", {
                        "app_id": _APP_ID,
                        "title": atom.get("title", ""),
                        "summary": atom.get("summary", ""),
                        "tier": "superseded",
                        "confidence": 0.0,
                        "force": True,
                        "source_id": f"stabilization_worker/{push_sha[:8]}",
                    }, timeout=20)
                    invalidated.append(atom)
                except Exception as exc:
                    print(f"    [warn] invalidation failed: {exc}", file=sys.stderr)
            else:
                invalidated.append(atom)

    # Step 3: fast-track corrections
    corrections_promoted = _fast_track_corrections(since_hours=48, dry_run=dry_run)
    print(f"  {corrections_promoted} correction(s) promoted to intake")

    # Step 4: write brief
    _write_brief(push_sha, invalidated, corrections_promoted, changed_files, dry_run)

    # Step 5: clear flag + update push event
    if not dry_run:
        soil.put(_FLAG_COLLECTION, "stabilization_needed", {"value": False, "cleared_at": _now_iso()})
        if event:
            soil.put(_EVENTS_COLLECTION, push_sha, {**event, "status": "complete", "completed_at": _now_iso()})

    # Grove completion signal
    grove_msg = (
        f"[STABILIZATION] Complete — "
        f"{len(invalidated)} atom(s) invalidated, "
        f"{corrections_promoted} correction(s) promoted. "
        f"Fleet is stable. Brief: SOIL {_BRIEF_COLLECTION}/latest"
    )
    _grove_signal(grove_msg)
    print(f"\n{grove_msg}")

    pg.close()
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Post-push fleet stabilization worker")
    p.add_argument("--push-id", default="", help="Push ID from push event record")
    p.add_argument("--sha", default="", help="Merge commit SHA")
    p.add_argument("--dry-run", action="store_true", help="Scan only, no writes")
    args = p.parse_args()

    raise SystemExit(run(
        push_id=args.push_id or None,
        sha=args.sha or None,
        dry_run=args.dry_run,
    ))
