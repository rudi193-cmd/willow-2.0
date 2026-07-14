"""Unattended entrypoint for the empty-room test.

Runs every registered constitutional compliance probe, prints the verdicts as a
single JSON object on stdout, and exits non-zero if any kernel invariant was
breached. Designed to be fired by a timer/loop and have its stdout piped to the
FRANK ledger by the orchestrator:

    python -m constitution.run_compliance        # exit 0 = all clauses held

A breach (exit 1) is a P0: the one night a kernel gate failed is the night this
must escalate to the human_required queue. The runner reports; recording and
escalation are the orchestrator's job — the witness is not the actor (§0.1).
"""
from __future__ import annotations

import json
import sys

from constitution.cases import const_0_3_egress, const_0_4_humankey, const_0_5_ledger

# Registry of probes. Each new eternity-clause adversary is one line here.
PROBES = [const_0_3_egress, const_0_4_humankey, const_0_5_ledger]


def run_suite() -> dict:
    verdicts = [p.run().to_dict() for p in PROBES]
    breaches = [v["trace_id"] for v in verdicts if not v["held"]]
    return {
        "suite": "constitution/compliance",
        "held": not breaches,
        "breached_clauses": breaches,
        "verdicts": verdicts,
    }


def main() -> int:
    result = run_suite()
    print(json.dumps(result, indent=2))
    return 0 if result["held"] else 1


if __name__ == "__main__":
    sys.exit(main())
