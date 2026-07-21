"""CI face of the empty-room test.

Every constitutional compliance probe must hold — the same probe the unattended
timer runs, here gating merges. If a change to the egress muscle ever re-opens a
self-extension vector, this fails in CI before it can fail silently at 3am.
"""
from __future__ import annotations

from constitution.cases import const_0_3_egress
from constitution.run_compliance import run_suite


def test_const_0_3_egress_holds():
    v = const_0_3_egress.run()
    assert v.held, f"CONST-0-3 breached on: {v.breaches}"


def test_const_0_3_egress_is_not_vacuous():
    """The probe must actually attempt multiple distinct self-extension vectors —
    a probe that made no attempt 'passes' by saying nothing."""
    v = const_0_3_egress.run()
    assert len(v.attempts) >= 7


def test_gate_is_a_discriminator_not_broken_shut():
    """Liveness: a fully-authorized principal IS granted egress. Proves the probes
    above pass because the gate discriminates, not because it denies everything."""
    ok, reason = const_0_3_egress.grant_is_honored()
    assert ok is True, reason


def test_const_0_5_ledger_holds():
    from constitution.cases import const_0_5_ledger

    v = const_0_5_ledger.run()
    assert v.held, f"CONST-0-5 breached on: {v.breaches}"
    assert len(v.attempts) >= 4


def test_const_0_4_humankey_holds():
    from constitution.cases import const_0_4_humankey

    v = const_0_4_humankey.run()
    assert v.held, f"CONST-0-4 breached on: {v.breaches}"
    assert len(v.attempts) >= 4
    ok, reason = const_0_4_humankey.grant_is_honored()
    assert ok is True, reason


def test_const_0_3_capability_holds():
    from constitution.cases import const_0_3_capability

    v = const_0_3_capability.run()
    assert v.held, f"CONST-0-3-II breached on: {v.breaches}"
    assert len(v.attempts) >= 4
    ok, reason = const_0_3_capability.grant_is_honored()
    assert ok is True, reason


def test_const_0_2_ratify_holds():
    from constitution.cases import const_0_2_ratify

    v = const_0_2_ratify.run()
    assert v.held, f"CONST-0-2 breached on: {v.breaches}"
    assert len(v.attempts) >= 3
    ok, reason = const_0_2_ratify.grant_is_honored()
    assert ok is True, reason


def test_suite_reports_held():
    result = run_suite()
    assert result["held"] is True, result["breached_clauses"]
    for tid in ("CONST-0-2", "CONST-0-3", "CONST-0-3-II", "CONST-0-4", "CONST-0-5"):
        assert any(v["trace_id"] == tid for v in result["verdicts"]), tid
