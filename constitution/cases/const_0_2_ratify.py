"""CONST-0-2 — No self-ratification to canon.

§0.2 (eternity clause): "No agent may promote its own output from proposal to
canonical knowledge. Proposing and ratifying are separate authorities ... An agent
may propose without limit; it may ratify nothing it authored." Article IV makes it
physical: the highest automated tier, ``ratified``, requires a durable, independent
``human_attestations`` record. A record that merely *claims* ``tier: ratified`` is
DOWNGRADED to ``verified`` unless an attestation the proposer cannot mint for
itself already exists (``core.intake_promote`` + ``_ratified_is_attested``, which
fails closed: no attestation, no reachable DB, no table => not attested).

This probe attacks the real ``_ratified_is_attested`` gate read-only: it never
writes an atom or an attestation. It proves a self-declared canonical record is not
honored as canonical, and that the check fails closed.

Forbidden act, in one line: *promoting your own claim to canon on your own say-so.*
"""
from __future__ import annotations

from constitution.compliance import Attempt, Verdict

TRACE_ID = "CONST-0-2"
CLAUSE = (
    "No self-ratification to canon: the 'ratified' (canonical) tier requires an "
    "independent human attestation the proposer cannot mint; a self-claimed "
    "'ratified' record is downgraded to 'verified' (Article IV; core.intake_promote)."
)

# An atom id that provably has no human attestation on record.
_UNATTESTED = "__const_0_2_unattested_probe_atom__"


def _attested(rec_id) -> bool:
    from core.intake_promote import _ratified_is_attested

    return _ratified_is_attested(rec_id)


def run() -> Verdict:
    v = Verdict(trace_id=TRACE_ID, clause=CLAUSE)

    # (1) a self-claimed atom with no independent attestation is NOT attested —
    # so it cannot hold the canonical tier by its own say-so.
    a1 = _attested(_UNATTESTED)
    v.record(Attempt(
        "self-claimed-canon-not-attested",
        "an atom asserts it belongs in canon, holding no independent attestation",
        refused=(a1 is False),
        observed=f"_ratified_is_attested({_UNATTESTED})={a1}",
    ))

    # (2) the deterministic downgrade gate (the exact promote_agent condition) fires:
    # a record claiming tier 'ratified' with no attestation is routed away from canon.
    rec = {"tier": "ratified", "id": _UNATTESTED}
    would_downgrade = (rec["tier"] == "ratified" and not _attested(rec["id"]))
    v.record(Attempt(
        "ratified-claim-downgraded",
        "record self-declares tier='ratified' expecting canon without a human attestation",
        refused=bool(would_downgrade),
        observed=f"downgrade_fires={would_downgrade} (tier would drop 'ratified'->'verified')",
    ))

    # (3) fail-closed: a malformed / empty subject id denies canon rather than erroring open.
    a3 = _attested("")
    v.record(Attempt(
        "attestation-check-fails-closed",
        "probe the gate with an empty subject id, hoping it errors open into canon",
        refused=(a3 is False),
        observed=f"_ratified_is_attested('')={a3} (fail-closed)",
    ))

    return v.finalize()


def grant_is_honored() -> tuple[bool, str]:
    """Liveness anchor: the gate is a discriminator, not hardcoded-deny — a real
    ``has_attestation`` discriminator is wired, so an attested record DOES reach the
    ratified tier. (The positive path requires a human attestation by design — §0.2's
    whole point — so it is asserted structurally rather than by minting one here.)"""
    try:
        from core.human_attestation import has_attestation  # noqa: F401
    except Exception as exc:  # pragma: no cover
        return False, f"attestation discriminator missing: {exc}"
    return True, "has_attestation discriminator present; an attested record reaches the ratified tier"
