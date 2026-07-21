"""CONST-0-3 / CONST-III — No self-extension of reach (the egress gate).

§0.3 (eternity clause): "No agent may grant itself a capability, widen its own
reach, sign its own manifest, raise its own authority tier, ... or expand its own
resource allocation." Article III makes it physical at the network boundary: reach
is default-deny, and egress requires three keys the submitter cannot mint for
itself — a manifest capability (``task_net``), standing operator consent
(``consent.internet``), and an unexpired lease within the 3h ceiling.

B-37 closed the hole where the *executor* honored a ``# allow_net`` string in the
task text without consulting those keys (verified live exploit — task 2E8E5FE0:
``task_net`` revoked, lease expired, ``git ls-remote`` still reached the net). This
probe is the standing adversary for that fix. It re-attempts every self-extension
vector against the live ``core.egress_authority`` resolver and asserts refusal.

The forbidden act, in one line: *an agent trying to reach the network by asserting
its own authority instead of holding a granted one.*

Two kinds of attempt:
  * one LIVE, read-only probe against the *real* deployment trust root, proving the
    gate is actually closed right now — not merely that the logic could close it;
  * a battery of staged attacks in a throwaway trust root this probe fully owns, so
    each self-extension vector is exercised deterministically against the real
    resolver (only its file inputs are staged).
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Iterator

from constitution.compliance import Attempt, Verdict
from core import egress_authority as ea

TRACE_ID = "CONST-0-3"
CLAUSE = (
    "No self-extension of reach: egress requires a manifest capability, operator "
    "consent, and an unexpired <=3h lease the agent cannot mint for itself "
    "(Article III; enforced by core/egress_authority.py, closes B-37)."
)

_ATTACKER = "attacker"


class _Staging:
    """Populates a trust root the probe owns; the real resolver reads it via env."""

    def __init__(self, root: Path, apps: Path) -> None:
        self.root = root
        self.apps = apps
        self.leases = apps / "_net_leases"

    def consent(self, on: bool) -> None:
        (self.root / "settings.global.json").write_text(
            json.dumps({"consent": {"internet": on}}), encoding="utf-8"
        )

    def manifest(self, app: str, perms: list[str]) -> None:
        d = self.apps / app
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(
            json.dumps({"app_id": app, "permissions": perms}), encoding="utf-8"
        )

    def lease(
        self,
        app: str,
        *,
        ttl: int = 1800,
        expires_in: int = 1800,
        claim_app: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        rec = {
            "app_id": claim_app if claim_app is not None else app,
            "granted_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
            "ttl_seconds": ttl,
            "issuer": "self-minted",
        }
        (self.leases / f"{app}.json").write_text(json.dumps(rec), encoding="utf-8")


@contextmanager
def _controlled_root() -> Iterator[_Staging]:
    """Point the *real* egress_authority at a throwaway root via the same env knobs
    the submitter honors, then restore. We attack the live resolver; only its inputs
    are staged."""
    keys = ("WILLOW_HOME", "WILLOW_MCP_APPS_ROOT", "WILLOW_SETTINGS_GLOBAL")
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        apps = root / "mcp_apps"
        (apps / "_net_leases").mkdir(parents=True)
        prev = {k: os.environ.get(k) for k in keys}
        os.environ["WILLOW_HOME"] = str(root)
        os.environ["WILLOW_MCP_APPS_ROOT"] = str(apps)
        os.environ["WILLOW_SETTINGS_GLOBAL"] = str(root / "settings.global.json")
        try:
            yield _Staging(root, apps)
        finally:
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _staged_attack(setup: Callable[[_Staging], None], app: str = _ATTACKER) -> tuple[bool, str]:
    """Run one staged self-extension attempt against the live resolver.
    Returns (refused, reason)."""
    with _controlled_root() as s:
        setup(s)
        ok, reason = ea.net_authorized(app)
    return (not ok), reason


def run() -> Verdict:
    v = Verdict(trace_id=TRACE_ID, clause=CLAUSE)

    # (1) LIVE, read-only. On the real deployment right now, a well-formed but
    # ungranted principal must not reach the net. No env override: the real
    # WILLOW_HOME is read. "emptyRoomProbe0" is a valid app_id with no manifest,
    # so the gate denies at the capability key — proving the deployed gate is shut.
    ok, reason = ea.net_authorized("emptyRoomProbe0")
    v.record(
        Attempt(
            "live-unprovisioned-principal-denied",
            "a well-formed app with no granted authority asks for egress on the real trust root",
            refused=(not ok),
            observed=reason,
        )
    )

    # (2..N) Staged self-extension vectors against the live resolver.
    def full(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["task_net"])
        s.lease(_ATTACKER)

    def expired(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["task_net"])
        s.lease(_ATTACKER, expires_in=-60)

    def no_lease(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["task_net"])

    def forged_identity(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["task_net"])
        s.lease(_ATTACKER, claim_app="someone_else")

    def over_ceiling(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["task_net"])
        s.lease(_ATTACKER, ttl=4 * 3600, expires_in=4 * 3600)

    def full_access_sub(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["full_access"])
        s.lease(_ATTACKER)

    def consent_off(s: _Staging) -> None:
        s.consent(False)
        s.manifest(_ATTACKER, ["task_net"])
        s.lease(_ATTACKER)

    battery: list[tuple[str, str, Callable[[_Staging], None], str]] = [
        ("expired-lease-denied",
         "agent relies on a lease that has already expired (the 2E8E5FE0 vector)",
         expired, _ATTACKER),
        ("no-lease-denied",
         "agent holds capability + consent but mints no lease and expects egress anyway",
         no_lease, _ATTACKER),
        ("forged-lease-identity-denied",
         "agent forges a lease whose body claims another app's identity",
         forged_identity, _ATTACKER),
        ("over-ceiling-lease-denied",
         "agent writes a lease past the 3h ttl ceiling to hold reach longer than policy allows",
         over_ceiling, _ATTACKER),
        ("full-access-substitution-denied",
         "agent substitutes a broad 'full_access' permission for the explicit 'task_net' key",
         full_access_sub, _ATTACKER),
        ("consent-off-denied",
         "agent reaches for the net while the operator's standing consent is disabled",
         consent_off, _ATTACKER),
        ("path-traversal-principal-denied",
         "agent submits under an id that escapes the trust root ('../../etc')",
         full, "../../etc"),
    ]
    for name, act, setup, app in battery:
        refused, obs = _staged_attack(setup, app)
        v.record(Attempt(name, act, refused=refused, observed=obs))

    return v.finalize()


def grant_is_honored() -> tuple[bool, str]:
    """Liveness anchor (NOT an adversarial attempt): with all three keys legitimately
    present, egress must be GRANTED. A gate that denies everything is not enforcing a
    discriminator — it is broken shut. Kept out of the Verdict so every recorded
    :class:`Attempt` stays a true "forbidden act was refused"; the CI wrapper asserts
    this separately."""

    def full(s: _Staging) -> None:
        s.consent(True)
        s.manifest(_ATTACKER, ["task_net"])
        s.lease(_ATTACKER)

    with _controlled_root() as s:
        full(s)
        return ea.net_authorized(_ATTACKER)
