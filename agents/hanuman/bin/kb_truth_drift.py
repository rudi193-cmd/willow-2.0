#!/usr/bin/env python3
"""
kb_truth_drift.py — KB atom truth-drift detector.
b17: DRFT1  ΔΣ=42

Compares KB atom claims against current code files. Flags atoms whose
claims no longer match reality. Uses SOIL as the mapping layer — no KB
schema changes required.

Usage:
    kb_truth_drift.py seed      — write initial atom→file mappings to SOIL
    kb_truth_drift.py scan      — check all mapped atoms for drift
    kb_truth_drift.py report    — show current drift results
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import json
import urllib.request

from core import soil
from core.pg_bridge import PgBridge
from core.grove_gate import assert_grove as _assert_grove


def _ask_ollama(model: str, system: str, prompt: str, timeout: int = 90) -> str:
    """Minimal stdlib Ollama caller — no sap.core.gate dependency."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
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
        print(f"  [ollama] {exc}", file=sys.stderr)
        return ""

_APP_ID = "hanuman"
_MAP_COLLECTION = "hanuman/atom_code_map"
_RESULTS_COLLECTION = "hanuman/atom_drift_results"
_REPO_ROOT = Path(_ROOT)

_MIN_EVIDENCE_LEN = 30   # shorter than this → downgrade confidence
_HIGH_CONFIDENCE = 0.75  # drifted + >= this → Grove alert; below → handoff only


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_pg: PgBridge | None = None


def _get_pg() -> PgBridge:
    global _pg
    if _pg is None:
        _pg = PgBridge()
        _pg._ensure_conn()
    return _pg


def _kb_get(atom_id: str) -> dict:
    """Look up a KB atom by ID directly via Postgres (works inside bwrap)."""
    try:
        import psycopg2.extras
        pg = _get_pg()
        with pg.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM knowledge WHERE id = %s AND invalid_at IS NULL",
                (atom_id,),
            )
            row = cur.fetchone()
        if row:
            return {"found": True, "atom": dict(row)}
        return {"found": False}
    except Exception as exc:
        return {"found": False, "error": str(exc)}


def _mcp(tool: str, args: dict, timeout: int = 30) -> Any:
    try:
        from willow.fylgja._mcp import call
        return call(tool, args, timeout=timeout)
    except Exception as exc:
        return {"error": str(exc)}


# ── Seed ──────────────────────────────────────────────────────────────────────

_INITIAL_MAPPINGS: list[dict] = [
    {
        "atom_id": "02377795",
        "title": "kb_truth_drift — KB atom truth-drift detector",
        "file_paths": ["agents/hanuman/bin/kb_truth_drift.py"],
        "added_by": "hanuman",
        "note": "Atom describes kb_truth_drift.py usage and design.",
    },
    {
        "atom_id": "2E063B1C",
        "title": "kart fix: venv PATH was resolving to core/ not repo root",
        "file_paths": ["core/kart_worker.py", "core/pg_bridge.py"],
        "added_by": "hanuman",
        "note": "Atom records the kart venv path fix — drift if kart_worker changes again.",
    },
    {
        "atom_id": "60B9A121",
        "title": "Fylgja hook system: anchor state and prompt count",
        "file_paths": ["sap/fylgja/hooks.py", "sap/sap_mcp.py"],
        "added_by": "hanuman",
        "note": "Atom describes Fylgja hook anchor/prompt-count behavior.",
    },
    {
        "atom_id": "9A4A02C4",
        "title": "grove_session: hard_close crash detection pattern",
        "file_paths": ["core/grove_serve.py"],
        "added_by": "hanuman",
        "note": "Atom describes Grove hard-close crash detection.",
    },
]


def cmd_seed() -> None:
    for m in _INITIAL_MAPPINGS:
        record_id = f"map-{m['atom_id']}"
        if soil.get(_MAP_COLLECTION, record_id):
            print(f"  already mapped: {m['atom_id']} — skipping")
            continue
        soil.put(_MAP_COLLECTION, record_id, {**m, "added_at": _now()})
        print(f"  seeded: {m['atom_id']} → {len(m['file_paths'])} file(s)")
    print(f"Seed complete. Collection: {_MAP_COLLECTION}")


# ── Drift scorer ──────────────────────────────────────────────────────────────

_DRIFT_PROMPT = """\
You are checking whether a knowledge base claim still accurately describes code.

CLAIM (KB atom):
Title: {title}
Summary: {summary}

CURRENT CODE ({file_path}):
{file_content}

Does this claim still accurately describe the code above?

Answer with exactly one of:
  current     — the claim is still accurate
  drifted     — the claim is no longer accurate (specific mismatch found)
  uncertain   — cannot determine from this file alone

Then on a new line, write one sentence of evidence (minimum 30 characters). Be specific.

Format:
VERDICT: <current|drifted|uncertain>
EVIDENCE: <one sentence>"""


def _score_atom_against_file(atom: dict, file_path: str) -> dict:
    full_path = _REPO_ROOT / file_path
    if not full_path.exists():
        return {
            "verdict": "uncertain",
            "evidence": f"File {file_path} not found in repo.",
            "confidence": 0.4,
        }

    content = full_path.read_text(encoding="utf-8", errors="replace")
    snippet = content[:4000]
    if len(content) > 4000:
        snippet += f"\n... ({len(content) - 4000} chars truncated)"

    prompt = _DRIFT_PROMPT.format(
        title=atom.get("title", ""),
        summary=(atom.get("summary") or "")[:1500],
        file_path=file_path,
        file_content=snippet,
    )

    raw = _ask_ollama(
        "llama3.2:3b",
        "You are a precise code auditor. Follow the output format exactly.",
        prompt,
    ) or ""

    verdict = "uncertain"
    evidence = ""
    for line in raw.splitlines():
        if line.startswith("VERDICT:"):
            v = line.split(":", 1)[1].strip().lower()
            if v in ("current", "drifted", "uncertain"):
                verdict = v
        elif line.startswith("EVIDENCE:"):
            evidence = line.split(":", 1)[1].strip()

    confidence = 0.8 if len(evidence) >= _MIN_EVIDENCE_LEN else 0.4
    if not evidence:
        evidence = f"No structured evidence returned. Raw: {raw[:100]}"
        confidence = 0.3

    return {"verdict": verdict, "evidence": evidence, "confidence": confidence}


# ── Scan ──────────────────────────────────────────────────────────────────────

def _ledger_auto_invalidated(atom_id: str, atom_title: str, evidence: str, confidence: float) -> None:
    try:
        pg = _get_pg()
        pg.ledger_append("willow-ratification", "auto_invalidated", {
            "atom_id": atom_id,
            "atom_title": atom_title,
            "ratification_class": "evidence_based",
            "evidence": evidence,
            "confidence": confidence,
        })
    except Exception as exc:
        print(f"  [warn] ledger write failed: {exc}", file=sys.stderr)


def cmd_scan(auto_resolve: bool = False, dry_run: bool = False) -> None:
    mappings = soil.all_records(_MAP_COLLECTION)
    if not mappings:
        print("No mappings found. Run: kb_truth_drift.py seed")
        return

    print(f"Scanning {len(mappings)} atom mapping(s)...  auto_resolve={auto_resolve} dry_run={dry_run}")
    grove_alerts: list[dict] = []
    auto_resolved: list[str] = []

    for mapping in mappings:
        atom_id = mapping.get("atom_id", "")
        file_paths = mapping.get("file_paths", [])

        atom_result = _kb_get(atom_id)
        if not atom_result.get("found"):
            print(f"  [{atom_id}] atom not found in KB — skipping")
            continue

        atom = atom_result["atom"]
        print(f"\n  [{atom_id}] {atom.get('title', '')[:60]}")

        file_scores: list[dict] = []
        for fp in file_paths:
            score = _score_atom_against_file(atom, fp)
            file_scores.append({"file": fp, **score})
            symbol = {"current": "✓", "drifted": "✗", "uncertain": "?"}.get(score["verdict"], "?")
            print(f"    {symbol} {fp}")
            print(f"      → {score['verdict']} ({score['confidence']:.0%}) {score['evidence'][:90]}")

        verdicts = [s["verdict"] for s in file_scores]
        if "drifted" in verdicts:
            aggregate = "drifted"
        elif all(v == "current" for v in verdicts):
            aggregate = "current"
        else:
            aggregate = "uncertain"

        max_conf = max((s["confidence"] for s in file_scores), default=0.0)

        # Auto-resolve: high-confidence drifted atoms are invalidated without human review
        status = "open" if aggregate == "drifted" else "ok"
        if aggregate == "drifted" and auto_resolve and max_conf >= _HIGH_CONFIDENCE:
            if dry_run:
                print(f"  [dry-run] would auto-invalidate {atom_id} (conf={max_conf:.0%})")
            else:
                ok = _kb_invalidate(atom_id)
                if ok:
                    best_evidence = next(
                        (s["evidence"] for s in file_scores if s["verdict"] == "drifted"), ""
                    )
                    _ledger_auto_invalidated(atom_id, atom.get("title", ""), best_evidence, max_conf)
                    status = "auto_resolved"
                    auto_resolved.append(atom_id)
                    print(f"  ✓ auto-invalidated {atom_id}")
                else:
                    print(f"  [error] auto-invalidate failed for {atom_id}", file=sys.stderr)

        result_record = {
            "atom_id": atom_id,
            "atom_title": atom.get("title", ""),
            "aggregate_verdict": aggregate,
            "max_confidence": max_conf,
            "file_scores": file_scores,
            "scanned_at": _now(),
            "status": status,
        }
        if not dry_run:
            soil.put(_RESULTS_COLLECTION, f"drift-{atom_id}", result_record)

        if aggregate == "drifted" and max_conf >= _HIGH_CONFIDENCE and status != "auto_resolved":
            grove_alerts.append(result_record)

    if auto_resolved:
        print(f"\nAuto-resolved {len(auto_resolved)} atom(s): {', '.join(auto_resolved)}")

    if grove_alerts:
        print(f"\nRouting {len(grove_alerts)} high-confidence alert(s) to Grove...")
        for alert in grove_alerts:
            _send_grove_alert(alert)
    else:
        print("\nNo high-confidence drift remaining. Low-conf/uncertain results available in: report")

    print(f"\nScan complete. Results: {_RESULTS_COLLECTION}")


def _send_grove_alert(alert: dict) -> None:
    drifted_files = [s for s in alert["file_scores"] if s["verdict"] == "drifted"]
    evidence_lines = "\n".join(
        f"  {s['file']}: {s['evidence'][:150]}" for s in drifted_files
    )
    msg = (
        f"[KB DRIFT] Atom {alert['atom_id']} claims may be stale.\n"
        f"Title: {alert['atom_title']}\n"
        f"Confidence: {alert['max_confidence']:.0%}\n"
        f"Evidence:\n{evidence_lines}\n"
        f"Action: verify atom or invalidate via kb_ingest with force=True."
    )
    result = _mcp("grove_send_message", {
        "channel_name": "general",
        "content": msg,
        "sender_agent_id": _APP_ID,
    }, timeout=15)
    if isinstance(result, dict) and result.get("error"):
        print(f"  [warn] Grove alert failed: {result['error']}", file=sys.stderr)
    else:
        print(f"  Grove alert sent: {alert['atom_id']}")


# ── Report ────────────────────────────────────────────────────────────────────

def cmd_report() -> None:
    results = soil.all_records(_RESULTS_COLLECTION)
    if not results:
        print("No drift results found. Run: kb_truth_drift.py scan")
        return

    drifted, uncertain, current, acked = [], [], [], []
    for r in results:
        verdict = r.get("aggregate_verdict")
        status = r.get("status")
        if status == "acked" or status == "resolved":
            acked.append(r)
        elif verdict == "current":
            current.append(r)
        elif verdict == "uncertain":
            uncertain.append(r)
        elif verdict == "drifted":
            # Postgres is authoritative: if atom is gone (invalid_at set), it's resolved
            if not _kb_get(r.get("atom_id", "")).get("found"):
                acked.append(r)
            else:
                drifted.append(r)

    print(f"\nKB Truth Drift Report — {_now()[:10]}")
    print("─" * 60)
    print(f"  Current:   {len(current)}")
    print(f"  Uncertain: {len(uncertain)}")
    print(f"  Drifted:   {len(drifted)}")
    print(f"  Acked:     {len(acked)}")

    if drifted:
        print()
        for r in drifted:
            print(f"  [DRIFTED] {r['atom_id']} — {r.get('atom_title', '')[:50]}")
            print(f"    confidence: {r.get('max_confidence', 0):.0%}  "
                  f"scanned: {r.get('scanned_at', '')[:10]}")
            for fs in r.get("file_scores", []):
                if fs["verdict"] == "drifted":
                    print(f"    file: {fs['file']}")
                    print(f"    evidence: {fs['evidence']}")
            print()

    if uncertain:
        print()
        for r in uncertain:
            print(f"  [UNCERTAIN] {r['atom_id']} — {r.get('atom_title', '')[:50]}")
            print(f"    scanned: {r.get('scanned_at', '')[:10]}")


# ── Map-add ───────────────────────────────────────────────────────────────────

def cmd_map_add(atom_id: str, file_paths: list[str], added_by: str = "hanuman", note: str = "") -> None:
    if not atom_id or not file_paths:
        print("Usage: kb_truth_drift.py map-add <atom_id> <file1> [file2 ...]")
        sys.exit(1)

    # Validate files exist
    missing = [fp for fp in file_paths if not (_REPO_ROOT / fp).exists()]
    if missing:
        print(f"[warn] These files don't exist in repo: {missing}")
        print("  Mapping will still be saved — verify paths are correct.")

    record_id = f"map-{atom_id}"
    existing = soil.get(_MAP_COLLECTION, record_id)
    if existing:
        # Merge new paths into existing mapping
        old_paths = existing.get("file_paths", [])
        merged = sorted(set(old_paths) | set(file_paths))
        existing["file_paths"] = merged
        existing["updated_at"] = _now()
        soil.put(_MAP_COLLECTION, record_id, existing)
        print(f"  updated: {atom_id} → {len(merged)} file(s) (was {len(old_paths)})")
    else:
        record = {
            "atom_id": atom_id,
            "file_paths": file_paths,
            "added_by": added_by,
            "added_at": _now(),
        }
        if note:
            record["note"] = note
        soil.put(_MAP_COLLECTION, record_id, record)
        print(f"  mapped: {atom_id} → {len(file_paths)} file(s)")


# ── Ack ───────────────────────────────────────────────────────────────────────

def cmd_ack(atom_id: str, resolution: str = "") -> None:
    """Mark a drift result as reviewed/resolved so it stops appearing in report."""
    result_id = f"drift-{atom_id}"
    record = soil.get(_RESULTS_COLLECTION, result_id)
    if not record:
        print(f"No drift result found for {atom_id}. Run scan first.")
        sys.exit(1)
    record["status"] = "acked"
    record["acked_at"] = _now()
    if resolution:
        record["resolution"] = resolution
    soil.put(_RESULTS_COLLECTION, result_id, record)
    print(f"  acked: {atom_id} — {record.get('atom_title', '')[:50]}")
    if resolution:
        print(f"  resolution: {resolution}")


# ── Resolve ───────────────────────────────────────────────────────────────────

_DRAFT_PROMPT = """\
You are updating a knowledge base atom because the code it describes has changed.

ORIGINAL ATOM TITLE: {title}
ORIGINAL ATOM SUMMARY: {summary}

DRIFT EVIDENCE (what changed):
{evidence}

CURRENT CODE ({file_path}):
{file_content}

Write a concise updated summary (2-4 sentences) that accurately describes what the
code does now. Be specific. Do not mention that this is an update or reference the
original atom. Output only the summary text, nothing else."""


def _draft_replacement(atom: dict, result_record: dict) -> str:
    """Use Ollama to draft an updated atom summary from current code + evidence."""
    drifted_files = [s for s in result_record.get("file_scores", []) if s["verdict"] == "drifted"]
    if not drifted_files:
        return ""

    # Use first drifted file for context
    fp = drifted_files[0]["file"]
    full_path = _REPO_ROOT / fp
    file_content = ""
    if full_path.exists():
        content = full_path.read_text(encoding="utf-8", errors="replace")
        file_content = content[:3000] + (f"\n... ({len(content)-3000} chars truncated)" if len(content) > 3000 else "")

    evidence = "\n".join(f"  {s['file']}: {s['evidence']}" for s in drifted_files)

    return _ask_ollama(
        "llama3.2:3b",
        "You are a precise technical writer updating knowledge base documentation.",
        _DRAFT_PROMPT.format(
            title=atom.get("title", ""),
            summary=(atom.get("summary") or "")[:500],
            evidence=evidence,
            file_path=fp,
            file_content=file_content,
        ),
    ) or ""


def _kb_invalidate(atom_id: str) -> bool:
    """Stamp invalid_at on a KB atom."""
    try:
        pg = _get_pg()
        with pg.conn.cursor() as cur:
            cur.execute(
                "UPDATE knowledge SET invalid_at = now() WHERE id = %s AND invalid_at IS NULL",
                (atom_id,),
            )
            updated = cur.rowcount
        pg.conn.commit()
        return updated > 0
    except Exception as exc:
        print(f"  [error] invalidate failed: {exc}", file=sys.stderr)
        return False


def cmd_resolve() -> None:
    """Interactive human-in-the-loop resolution for drifted atoms."""
    results = soil.all_records(_RESULTS_COLLECTION)
    open_drifts = [
        r for r in results
        if r.get("aggregate_verdict") == "drifted"
        and r.get("status") == "open"
    ]

    if not open_drifts:
        print("No open drift alerts. Run scan first or all alerts are already resolved.")
        return

    print(f"\nKB Truth Drift — Resolve ({len(open_drifts)} open)\n")

    for i, record in enumerate(open_drifts, 1):
        atom_id = record["atom_id"]
        print(f"[{i}/{len(open_drifts)}] {atom_id} — {record.get('atom_title', '')[:60]}")
        print(f"  Confidence: {record.get('max_confidence', 0):.0%}  Scanned: {record.get('scanned_at', '')[:10]}")

        drifted_files = [s for s in record.get("file_scores", []) if s["verdict"] == "drifted"]
        for s in drifted_files:
            print(f"  ✗ {s['file']}")
            print(f"    {s['evidence'][:120]}")

        atom_result = _kb_get(atom_id)
        if not atom_result.get("found"):
            print("  [skip] Atom already invalidated in Postgres — marking resolved.")
            record["status"] = "resolved"
            record["resolution"] = "invalidated_in_pg"
            soil.put(_RESULTS_COLLECTION, f"drift-{atom_id}", record)
            print()
            continue

        atom = atom_result["atom"]
        print(f"\n  Current summary:\n    {(atom.get('summary') or '')[:300]}")

        print("\n  Drafting replacement via Ollama (llama3.2:3b)...")
        draft = _draft_replacement(atom, record)
        if draft:
            print(f"\n  Draft replacement:\n    {draft[:400]}")
        else:
            print("  [warn] Could not draft replacement.")

        print()
        print("  [r] replace with draft   [i] invalidate only   [s] skip   [k] keep (false positive)")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Aborted.")
            return

        if choice == "r" and draft:
            ok = _kb_invalidate(atom_id)
            if ok:
                # Ingest replacement
                pg = _get_pg()
                new_id = pg.gen_id(8)
                pg.knowledge_put({
                    "id":          new_id,
                    "title":       atom.get("title", ""),
                    "summary":     draft,
                    "category":    atom.get("category", "general"),
                    "source_type": "drift-resolve",
                    "project":     atom.get("project", _APP_ID),
                    "tier":        "frontier",
                    "confidence":  0.7,
                    "weight":      atom.get("weight", 1.0),
                })
                record["status"] = "resolved"
                record["resolution"] = f"replaced → {new_id}"
                record["resolved_at"] = _now()
                soil.put(_RESULTS_COLLECTION, f"drift-{atom_id}", record)
                print(f"  ✓ Invalidated {atom_id}, ingested replacement {new_id} (tier=frontier)")
            else:
                print(f"  [error] Could not invalidate {atom_id}")

        elif choice == "i":
            ok = _kb_invalidate(atom_id)
            if ok:
                record["status"] = "resolved"
                record["resolution"] = "invalidated"
                record["resolved_at"] = _now()
                soil.put(_RESULTS_COLLECTION, f"drift-{atom_id}", record)
                print(f"  ✓ Invalidated {atom_id} — no replacement written")
            else:
                print(f"  [error] Could not invalidate {atom_id}")

        elif choice == "k":
            record["status"] = "acked"
            record["resolution"] = "false_positive"
            soil.put(_RESULTS_COLLECTION, f"drift-{atom_id}", record)
            print(f"  Kept — marked as false positive")

        else:
            print(f"  Skipped")

        print()

    print("Resolve session complete.")


# ── Entry ─────────────────────────────────────────────────────────────────────

def _pop_flag(args: list[str], flag: str) -> str:
    """Extract --flag value from args list in-place. Returns '' if not found."""
    try:
        i = args.index(flag)
        args.pop(i)
        return args.pop(i)
    except (ValueError, IndexError):
        return ""


if __name__ == "__main__":
    _assert_grove("kb_truth_drift")
    args = sys.argv[1:]
    cmd = args[0] if args else "report"

    if cmd == "seed":
        cmd_seed()
    elif cmd == "scan":
        cmd_scan(
            auto_resolve="--auto-resolve" in args,
            dry_run="--dry-run" in args,
        )
    elif cmd == "report":
        cmd_report()
    elif cmd == "map-add":
        if len(args) < 3:
            print("Usage: kb_truth_drift.py map-add <atom_id> <file1> [file2 ...] [--by agent] [--note text]")
            sys.exit(1)
        rest = args[1:]
        by = _pop_flag(rest, "--by") or "hanuman"
        note = _pop_flag(rest, "--note")
        cmd_map_add(atom_id=rest[0], file_paths=rest[1:], added_by=by, note=note)
    elif cmd == "ack":
        if len(args) < 2:
            print("Usage: kb_truth_drift.py ack <atom_id> [--note resolution]")
            sys.exit(1)
        rest = args[1:]
        resolution = _pop_flag(rest, "--note")
        cmd_ack(atom_id=rest[0], resolution=resolution)
    elif cmd == "resolve":
        cmd_resolve()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: kb_truth_drift.py [seed|scan|report|map-add|ack|resolve]")
        sys.exit(1)
