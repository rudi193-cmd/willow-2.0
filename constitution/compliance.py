"""constitution.compliance — the empty-room test harness.

    law     (CONSTITUTION.md, a Trace ID)
      -> muscle  (a deterministic gate in willow-2.0)
        -> probe   (attempt the forbidden act, assert refusal)
          -> verdict (held / breached, recorded to the FRANK ledger)

Each ``constitution/cases/*.py`` supplies one probe returning a :class:`Verdict`.
The kernel "held" for a clause iff every adversarial :class:`Attempt` against it
was refused; a single un-refused attempt is a breach and a P0.

Stdlib-only by policy. The muscle these probes guard (e.g. ``core.egress_authority``)
refuses to import willow-mcp across the repo boundary, and its witness lives under
the same discipline. The probe does not write its own ledger record: it reports a
verdict, and a separate orchestrator (MCP-side, or a timer) records it. The witness
is not the actor (§0.1) — a probe that recorded its own passing would be the very
self-attestation the constitution forbids.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Attempt:
    """One adversarial move: a forbidden act and whether the gate refused it."""

    name: str
    forbidden_act: str  # what an attacker tried to do
    refused: bool  # did the gate deny it?
    observed: str  # the gate's own reason / the observed outcome

    @property
    def held(self) -> bool:
        """The invariant held for this move iff the forbidden act was refused."""
        return self.refused


@dataclass
class Verdict:
    """The result of one compliance probe against one constitutional clause."""

    trace_id: str  # e.g. "CONST-0-3"
    clause: str  # human-readable summary of the invariant under test
    attempts: list[Attempt] = field(default_factory=list)
    checked_at: str = ""

    def record(self, attempt: Attempt) -> Attempt:
        self.attempts.append(attempt)
        return attempt

    @property
    def held(self) -> bool:
        """Held iff there was at least one attempt and every one was refused.

        The "at least one" guard is deliberate: a probe that made no attempt has
        not shown the kernel holds — it has shown nothing, which is not a pass.
        """
        return bool(self.attempts) and all(a.held for a in self.attempts)

    @property
    def breaches(self) -> list[str]:
        return [a.name for a in self.attempts if not a.held]

    def finalize(self) -> "Verdict":
        self.checked_at = datetime.now(timezone.utc).isoformat()
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["held"] = self.held
        d["breaches"] = self.breaches
        return d
