#!/usr/bin/env python3
"""W8 census witness — scheduled heartbeat for the canonical-reconstruction trust instrument.

Runs ``canonical_reconstruction_census()``, refreshes the saved report the W8
evaluator consumes (``sandbox/stone_soup/reports/recon-canonical.json``),
computes ``cost = unsupported / canonical_total``, and posts a Grove ``#alerts``
message when cost exceeds the threshold (default 0.05).

Before this, W8 was the fleet's stated trust instrument with no scheduler: the
census only ran when someone invoked it by hand, so the saved report the
evaluator reads could silently go stale. This is the heartbeat.

Scheduled weekly by ``systemd/willow-w8-census.timer``. Run manually:

    ./willow.sh w8-census
    python3 scripts/w8_census_witness.py --dry-run   # compute + report, never post
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

MAX_COST = float(os.environ.get("W8_MAX_COST", "0.05"))
ALERT_CHANNEL_ID = int(os.environ.get("W8_ALERT_CHANNEL_ID", "15"))  # Grove #alerts
SENDER = os.environ.get("WILLOW_AGENT_NAME", "willow")


def _post_grove(content: str, *, dry_run: bool) -> None:
    """Post a breach alert to Grove. Never raises — a failed alert must not
    crash the witness or mark the timer failed for an otherwise-good run."""
    if dry_run:
        print(f"[grove dry-run] would post to channel {ALERT_CHANNEL_ID}: {content}")
        return
    try:
        from core.grove_db import bus_send, get_connection, release_connection

        conn = get_connection()
        try:
            bus_send(
                conn,
                channel_id=ALERT_CHANNEL_ID,
                sender=SENDER,
                content=content,
                bus_type="EVENT",
                priority=2,
            )
        finally:
            release_connection(conn)
        print(f"[grove] alert posted to channel {ALERT_CHANNEL_ID}")
    except Exception as exc:  # noqa: BLE001 — alerting is best-effort
        print(f"[grove] alert post FAILED ({type(exc).__name__}: {exc})", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="W8 canonical-reconstruction census witness")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="compute and report, but never post to Grove",
    )
    args = ap.parse_args()

    from sandbox.stone_soup.run import REPORTS_DIR, canonical_reconstruction_census

    try:
        recon = canonical_reconstruction_census()
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — DB unavailable = fail loudly
        print(
            f"W8 census FAILED to run ({type(exc).__name__}: {exc}) — is Postgres up?",
            file=sys.stderr,
        )
        return 1

    total = int(recon.get("canonical_total", 0))
    unsupported = int(recon.get("unsupported", 0))
    cost = (unsupported / total) if total else 0.0

    # Refresh the saved report the W8 evaluator reads when it is not run live.
    # Written verbatim (same shape run.py emits) so the evaluator parses it.
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "recon-canonical.json").write_text(
        json.dumps(recon, indent=2, default=str) + "\n", encoding="utf-8"
    )

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = (
        f"W8 census {stamp}: {total - unsupported}/{total} canonical atoms "
        f"reconstructable — cost {cost:.4f} (max {MAX_COST:.4f})"
    )
    print(line)

    if total and cost > MAX_COST:
        _post_grove(
            f"⚠️ W8 BREACH — {line}. {unsupported} canonical atom(s) have no "
            "provenance leg (FRANK ledger ∪ content.source_id ∪ provenance edge). "
            "Inspect recent ingests / run the Stone Soup backfill.",
            dry_run=args.dry_run,
        )
        return 0  # a witness reports; it does not fail the timer on a real breach
    print("W8 within tolerance — no alert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
