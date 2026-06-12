"""Guard: the bitemporal repair must target exactly what the audit flags.

If the audit's violation predicates and the repair's selection predicates ever
drift apart, the repair would fix the wrong rows (or miss some) while the audit
keeps reporting OK/violations against a different definition. This test pins
them together at the source-text level — no DB needed.
"""
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


def test_repair_selection_matches_audit_predicates():
    repair = _read("scripts/repair_bitemporal.py")
    audit = _read("scripts/audit_bitemporal.py")
    # Direction A: superseded without invalid_at
    assert "tier='superseded' AND invalid_at IS NULL" in repair
    assert "tier='superseded' AND invalid_at IS NULL" in audit
    # Direction B: invalid_at without superseded tier
    assert "invalid_at IS NOT NULL AND tier <> 'superseded'" in repair
    assert "invalid_at IS NOT NULL AND tier <> 'superseded'" in audit


def test_repair_is_supersede_not_delete():
    repair = _read("scripts/repair_bitemporal.py")
    # never deletes knowledge rows
    assert "DELETE FROM knowledge" not in repair
    # A sets invalid_at from the supersession moment, B sets the tier
    assert "SET invalid_at = COALESCE(updated_at, now())" in repair
    assert "SET tier = 'superseded'" in repair


def test_repair_records_ledger_before_mutating():
    repair = _read("scripts/repair_bitemporal.py")
    ledger_pos = repair.index("ledger_append")
    update_pos = repair.index("UPDATE knowledge SET invalid_at")
    assert ledger_pos < update_pos, "ledger must be written before the UPDATE"
