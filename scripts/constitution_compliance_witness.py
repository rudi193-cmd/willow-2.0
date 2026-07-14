#!/usr/bin/env python3
"""Constitutional compliance witness — the unattended empty-room test.

Scheduled by ``systemd/constitution-compliance.timer``. Runs every registered
eternity-clause probe (``constitution.run_compliance``), records each verdict to
the FRANK ledger, and on any breach escalates a **critical** ``needs_review`` to
the ``human_required`` queue. The one night a kernel gate fails is the night the
operator is paged — automatically, from the record, with no one asked to look.

Run manually::

    python3 scripts/constitution_compliance_witness.py --once      # normal pass
    python3 scripts/constitution_compliance_witness.py --dry-run    # no DB writes; print intent
    python3 scripts/constitution_compliance_witness.py --selftest   # inject a synthetic breach,
                                                                     # exercise the escalation wire,
                                                                     # then clean up the queue row

Design notes:
  * The witness is the *orchestrator*: it may import ``core.*`` (ledger, queue).
    The probes it runs stay stdlib-only and never touch the DB — the witness is
    not the actor being witnessed (§0.1).
  * There is no ``constitutional_breach`` queue kind, and inventing one to test
    the constitution would be exactly the §0.3 self-extension the constitution
    forbids. A breach is a ``needs_review`` at ``critical`` — the existing lane.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SENDER = os.environ.get("WILLOW_AGENT_NAME", "willow")
PROJECT = "willow"
LEDGER_EVENT = "constitutional_compliance"
SELFTEST_TRACE = "CONST-SELFTEST"

from constitution.run_compliance import run_suite  # noqa: E402


def _escalation_for(verdict: dict) -> dict:
    tid = verdict["trace_id"]
    breaches = ", ".join(verdict.get("breaches") or []) or "(vector unspecified)"
    return {
        "kind": "needs_review",
        "priority": "critical",
        "title": f"CONSTITUTIONAL BREACH: {tid} did not hold",
        "summary": (
            f"{tid} failed the empty-room test. Clause: {verdict.get('clause', '')[:180]} "
            f"Breached vectors: {breaches}. A kernel eternity-clause gate let a forbidden "
            f"act through. Treat the affected authority as compromised until reviewed."
        ),
        "source_agent": SENDER,
        "source_ref": f"CONST-BREACH-{tid}",
    }


def _ledger_content(verdict: dict, *, selftest: bool) -> dict:
    return {
        "title": f"{verdict['trace_id']} " + ("held" if verdict["held"] else "BREACHED"),
        "trace_id": verdict["trace_id"],
        "held": verdict["held"],
        "attempts": len(verdict.get("attempts") or []),
        "breaches": verdict.get("breaches") or [],
        "checked_at": verdict.get("checked_at"),
        "witness": "scripts/constitution_compliance_witness.py",
        "selftest": selftest,
    }


def _record_and_escalate(result: dict, *, event_type: str, dry_run: bool, selftest: bool) -> dict:
    written: list[str] = []
    escalated: list[str] = []
    if dry_run:
        for v in result["verdicts"]:
            print(f"[dry-run] ledger <- {event_type}: {_ledger_content(v, selftest=selftest)['title']}")
            if not v["held"]:
                e = _escalation_for(v)
                print(f"[dry-run] human_required <- {e['priority']}: {e['title']}")
        return {"written": written, "escalated": escalated, "dry_run": True}

    from core import human_required
    from core.pg_bridge import PgBridge

    with PgBridge() as pg:
        for verdict in result["verdicts"]:
            rec_id = pg.ledger_append(PROJECT, event_type, _ledger_content(verdict, selftest=selftest))
            written.append(f"{verdict['trace_id']}:{rec_id}")

            if verdict["held"]:
                continue

            esc = _escalation_for(verdict)
            if selftest:
                esc["source_ref"] = f"CONST-SELFTEST-{verdict['trace_id']}"
                esc["title"] = "[SELFTEST] " + esc["title"]
            res = human_required.enqueue(pg.conn, **esc)
            note = f"{esc['source_ref']}:{res.get('id')}:{res.get('status')}"

            # A self-test breach is synthetic — prove the wire reached Postgres,
            # then dismiss the row so the operator's real queue is left clean.
            if selftest and res.get("status") == "added" and res.get("id"):
                human_required.resolve(
                    pg.conn, res["id"], resolved_by=SENDER, status="dismissed",
                    note="self-test cleanup — not a real breach",
                )
                note += "->dismissed(selftest-cleanup)"
            escalated.append(note)

    return {"written": written, "escalated": escalated, "dry_run": False}


def _inject_synthetic_breach(result: dict) -> dict:
    """Return a copy of the suite result with one synthetic breached verdict added,
    so the escalation path runs end-to-end without a real gate failure."""
    result = json.loads(json.dumps(result))  # deep copy of JSON-native content
    result["verdicts"].append({
        "trace_id": SELFTEST_TRACE,
        "clause": "synthetic breach — exercises the witness escalation wire only",
        "held": False,
        "attempts": [{"name": "synthetic", "refused": False}],
        "breaches": ["synthetic"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })
    result["held"] = False
    result["breached_clauses"] = [v["trace_id"] for v in result["verdicts"] if not v["held"]]
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Constitutional compliance witness (empty-room test)")
    ap.add_argument("--once", action="store_true", help="run the suite once (default behavior)")
    ap.add_argument("--dry-run", action="store_true", help="no ledger / no queue writes; print intent")
    ap.add_argument("--selftest", action="store_true",
                    help="inject a synthetic breach to exercise the escalation wire, then clean up")
    args = ap.parse_args()

    result = run_suite()
    event_type = LEDGER_EVENT
    if args.selftest:
        result = _inject_synthetic_breach(result)
        event_type = LEDGER_EVENT + "_selftest"  # never pollute real breach history

    io = _record_and_escalate(result, event_type=event_type, dry_run=args.dry_run, selftest=args.selftest)

    # Exit code reflects REAL clauses only — a synthetic self-test breach never
    # fails the process (that would page the operator for a drill).
    real_breach = any(
        v["trace_id"] != SELFTEST_TRACE and not v["held"] for v in result["verdicts"]
    )
    summary = {
        "held": not real_breach,
        "real_breached_clauses": [
            v["trace_id"] for v in result["verdicts"]
            if v["trace_id"] != SELFTEST_TRACE and not v["held"]
        ],
        "ledger_written": io["written"],
        "escalated": io["escalated"],
        "dry_run": args.dry_run,
        "selftest": args.selftest,
    }
    print(json.dumps(summary, indent=2))
    return 1 if real_breach else 0


if __name__ == "__main__":
    raise SystemExit(main())
