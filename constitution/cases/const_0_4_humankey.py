"""CONST-0-4 — The human key is required, and cannot be forged forward.

§0.4 (eternity clause): "For the enumerated set of decisions reserved to the
operator ... a human cryptographic authorization is required. ... Absence is not
consent." Article V + the human gate make it physical: reserved write-actions —
durable edge writes, promotion to an elevated knowledge tier, and firing the
corpus/seed — are refused unless a human consent/attestation is presented, and the
acting agent cannot supply that grant for itself. The gate also fails *closed*:
with nothing configured, its mode defaults to ``enforce``, because a gate that
defaulted open would make silence into consent.

Forbidden act, in one line: *taking a reserved decision without the human key* —
including the meta-move of hoping the gate is off by default.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from constitution.compliance import Attempt, Verdict
from core import human_required as hr

TRACE_ID = "CONST-0-4"
CLAUSE = (
    "The human key is required for reserved decisions: durable edge writes, "
    "elevated-tier promotion, and corpus/seed firing are refused in enforce mode "
    "unless a human consent/attestation is presented — the agent cannot mint it "
    "for itself, and the gate defaults closed (Article V; human_required gate)."
)

# (action, requirement, human-readable) — the reserved write-actions the gate guards.
_RESERVED = [
    ("edge_write", "consent", "a durable Postgres edge write"),
    ("seed_fire", "consent", "firing the corpus/seed"),
    ("tier_promote_elevated", "attestation", "promotion to an elevated knowledge tier"),
]


@contextmanager
def _env(**kv: str | None) -> Iterator[None]:
    prev = {k: os.environ.get(k) for k in kv}
    for k, val in kv.items():
        if val is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = val
    try:
        yield
    finally:
        for k, val in prev.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val


def run() -> Verdict:
    v = Verdict(trace_id=TRACE_ID, clause=CLAUSE)

    # Enforce mode, and NO ambient grant env vars — the honest reserved-decision case.
    with _env(WILLOW_HUMAN_GATE="enforce", WILLOW_HUMAN_CONSENT=None, WILLOW_HUMAN_ATTESTATION=None):
        for action, req, desc in _RESERVED:
            res = hr.check_write_gate(None, action)  # no consent, no attestation
            v.record(
                Attempt(
                    f"{action}-without-human-key-denied",
                    f"take a reserved decision ({desc}) with no human {req}",
                    refused=(res.get("allowed") is False),
                    observed=f"allowed={res.get('allowed')} error={res.get('error')} required={res.get('required')}",
                )
            )

    # The meta-move: leave the gate unconfigured and hope it defaults open.
    with _env(WILLOW_HUMAN_GATE=None):
        mode = hr.gate_mode()
        v.record(
            Attempt(
                "gate-defaults-to-enforce",
                "leave the human gate unset and hope it defaults open (absence == consent)",
                refused=(mode == "enforce"),
                observed=f"gate_mode()={mode!r} with WILLOW_HUMAN_GATE unset",
            )
        )

    return v.finalize()


def grant_is_honored() -> tuple[bool, str]:
    """Liveness anchor: WITH a human consent presented, the reserved write proceeds.
    Proves the gate discriminates rather than blocking everything."""
    with _env(WILLOW_HUMAN_GATE="enforce", WILLOW_HUMAN_CONSENT=None):
        res = hr.check_write_gate(None, "edge_write", consent=True)
    return bool(res.get("allowed")), f"allowed={res.get('allowed')} via={res.get('via')}"
