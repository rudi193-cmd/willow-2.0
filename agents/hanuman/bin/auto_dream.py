#!/usr/bin/env python3
"""
auto_dream.py — standalone AutoDream synthesis runner.
b17: DRMT1  ΔΣ=42

Mirrors the dream_run logic from sap_mcp.py so it can be called from cron
without an MCP server or Claude session.

Usage:
    auto_dream.py [run] [--force] [--app-id hanuman]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import json
import urllib.request

from core.pg_bridge import PgBridge
from core import soil as _soil
from core.grove_gate import assert_grove as _assert_grove


def _ask_ollama(model: str, system_prompt: str, user_message: str, timeout: int = 90) -> str:
    """Minimal stdlib Ollama caller — no sap.core.gate dependency."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "").strip()
    except Exception as exc:
        print(f"[ollama] {model}: {exc}", file=sys.stderr)
        return ""


def run(app_id: str = "hanuman", force: bool = False) -> dict:
    _assert_grove("auto_dream")
    pg = PgBridge()
    try:
        pg._ensure_conn()
    except Exception as e:
        return {"error": f"Postgres unavailable: {e}"}
    if pg.conn is None:
        return {"error": "Postgres unavailable"}

    store = _soil
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    state_key = f"{app_id}/dream"
    dream_state = store.get(state_key, "state") or {}

    if dream_state.get("locked") and not force:
        return {"error": "dream already running (locked). Pass --force to override."}

    if not force:
        last_str = dream_state.get("last_dream_at", "")
        if last_str:
            try:
                last = datetime.fromisoformat(last_str)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                hours_elapsed = (now - last).total_seconds() / 3600
                if hours_elapsed < 24:
                    return {"skipped": True, "reason": f"only {hours_elapsed:.1f}h since last dream (need 24h)"}
            except Exception:
                pass

    store.put(state_key, "state", {"locked": True, "lock_acquired_at": now_iso})

    try:
        import psycopg2.extras as _pge
        with pg.conn.cursor(cursor_factory=_pge.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, title, summary, tier, confidence, category
                FROM knowledge
                WHERE invalid_at IS NULL
                  AND summary IS NOT NULL AND summary != ''
                ORDER BY valid_at DESC
                LIMIT 20
            """)
            atoms = [dict(r) for r in cur.fetchall()]

        tensions: list = []
        seen_pairs: set = set()
        for atom in atoms[:10]:
            try:
                neighbors = pg.knowledge_search_semantic(atom["summary"], limit=3)
                for nb in neighbors:
                    nid = nb.get("id", "")
                    if not nid or nid == atom["id"]:
                        continue
                    pair_key = tuple(sorted([atom["id"], nid]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    resp = _ask_ollama(
                        "llama3.2:3b",
                        "You are a knowledge graph auditor.",
                        (f"A: {atom['title']}\n{atom['summary'][:200]}\n\n"
                         f"B: {nb.get('title','')}\n{(nb.get('summary') or '')[:200]}\n\n"
                         "Reply TENSION or COMPATIBLE (one word), then one sentence."),
                    ) or ""
                    if "TENSION" in resp.upper().split("\n")[0]:
                        tensions.append({"ids": [atom["id"], nid], "reason": resp.strip()[:200]})
            except Exception:
                continue

        atom_digest = "\n".join(
            f"- [{a.get('tier','?')}] {a['title']}: {(a.get('summary') or '')[:120]}"
            for a in atoms[:12]
        )
        synthesis = _ask_ollama(
            "mistral:7b",
            "You are a thoughtful knowledge synthesist. Be concise and specific.",
            (f"Reflecting on {len(atoms)} recent knowledge atoms for agent {app_id}:\n\n"
             f"{atom_digest}\n\n"
             "In 3-4 sentences: what patterns, connections, or gaps do you notice? "
             "What should be explored or reconciled next?"),
        ) or ""

        dream_summary = (
            f"AutoDream over {len(atoms)} atoms — {len(tensions)} tensions detected. "
            + (synthesis[:300] if synthesis else "")
        )
        atom_id = pg.gen_id(8)
        pg.knowledge_put({
            "id":          atom_id,
            "title":       f"Dream {now.strftime('%Y-%m-%d')} — {app_id}",
            "summary":     dream_summary,
            "content":     {
                "synthesis":      synthesis,
                "tensions_found": len(tensions),
                "tension_pairs":  tensions[:5],
                "atoms_scanned":  len(atoms),
            },
            "category":    "dream",
            "source_type": "session",
            "project":     app_id,
            "weight":      0.7,
            "tier":        "observed",
            "confidence":  0.75,
        })

        store.put(state_key, "state", {
            "last_dream_at":   now_iso,
            "locked":          False,
            "last_dream_atom": atom_id,
        })

        result = {
            "atom_id":        atom_id,
            "atoms_scanned":  len(atoms),
            "tensions_found": len(tensions),
            "synthesis":      synthesis[:500] if synthesis else "",
        }
        print(json.dumps(result))
        return result

    except Exception as e:
        try:
            store.put(state_key, "state", {"locked": False, "last_error": str(e)[:200]})
        except Exception:
            pass
        err = {"error": str(e)}
        print(json.dumps(err), file=sys.stderr)
        return err


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoDream synthesis runner")
    parser.add_argument("command", nargs="?", default="run")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--app-id", default="hanuman")
    args = parser.parse_args()

    result = run(app_id=args.app_id, force=args.force)
    sys.exit(0 if "error" not in result else 1)
