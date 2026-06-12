"""Tests for scripts/audit_verify.py — the definition-of-done harness."""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

import audit_verify as av  # noqa: E402


def test_no_gated_regressions():
    """Every gated (shipped Phase 0/1) finding must verify CLOSED on the tree."""
    results = av.run_all()
    regressed = [r for r in results if r["gate"] and r["state"] != av.CLOSED]
    assert not regressed, (
        "gated findings not closed: "
        + ", ".join(f"{r['id']}={r['state']} ({r['evidence']})" for r in regressed)
    )


def test_main_passes_on_current_tree():
    assert av.main(["--quiet"]) == 0


def test_reports_full_finding_set():
    ids = {r["id"] for r in av.run_all()}
    assert {"S1", "S2", "S4", "GAP-A", "GAP-B", "S11", "S3", "S15", "V1", "V2", "V3"} <= ids


def test_states_are_valid():
    valid = {av.CLOSED, av.OPEN, av.DEFERRED, av.ERROR}
    assert all(r["state"] in valid for r in av.run_all())
