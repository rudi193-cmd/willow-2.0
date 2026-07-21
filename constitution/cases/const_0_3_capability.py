"""CONST-0-3 (Article II) — No self-extension of capability (the capability gate).

§0.3 forbids granting oneself a *capability* as well as widening one's *reach*.
The egress probe (const_0_3_egress) covers the reach half; this covers the
capability half (Article II): "an agent may invoke a capability only if it is
listed in the agent's [signed] manifest. Absence from the list is denial."

The deterministic muscle is ``sap.core.gate.permitted`` — it reads permissions[]
from the manifest, expands each via PERMISSION_GROUPS, and fails closed on a
missing folder or empty permissions. The load-bearing anti-self-grant property:
an unknown permission string is treated as a *literal tool name*, so a broad label
like "full_access" grants ONLY the literal tool "full_access" — never soil_delete.
A grand-sounding word cannot expand into powers it never enumerated.

Forbidden act: invoking a capability the manifest does not grant — or expecting a
broad label to conjure powers it never named.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from constitution.compliance import Attempt, Verdict

TRACE_ID = "CONST-0-3-II"
CLAUSE = (
    "No self-extension of capability: an agent may invoke only a tool its signed "
    "manifest grants; a missing folder or empty permissions denies all, and a "
    "broad label expands to only its literal tool, never the whole surface "
    "(Article II; enforced by sap.core.gate.permitted)."
)


def _import_gate():
    # gate raises at import if WILLOW_SAFE_ROOT is unset; hand it a throwaway so the
    # import succeeds — the real roots are overridden per-probe in _staged_gate.
    os.environ.setdefault("WILLOW_SAFE_ROOT", "/tmp/__willow_probe_safe_root__")
    from sap.core import gate

    return gate


@contextmanager
def _staged_gate() -> Iterator[tuple]:
    """Point the real gate at a throwaway roots tree and restore afterward. We
    attack the live ``permitted`` resolver; only the manifests it reads are staged."""
    gate = _import_gate()
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        agents = root / "Agents"
        apps = root / "Applications"
        agents.mkdir()
        apps.mkdir()
        saved = (
            gate.AGENTS_ROOT,
            gate.SAFE_ROOT,
            gate.PROFESSOR_ROOT,
            gate._DEV_SAFE_ROOT,
            gate.LOG_DIR,
        )
        gate.AGENTS_ROOT = agents
        gate.SAFE_ROOT = apps
        gate.PROFESSOR_ROOT = apps / "__none__"
        gate._DEV_SAFE_ROOT = None
        gate.LOG_DIR = root / "log"
        gate.LOG_DIR.mkdir(exist_ok=True)
        try:
            yield gate, agents
        finally:
            (gate.AGENTS_ROOT, gate.SAFE_ROOT, gate.PROFESSOR_ROOT,
             gate._DEV_SAFE_ROOT, gate.LOG_DIR) = saved


def _manifest(agents: Path, app: str, perms: list[str]) -> None:
    d = agents / app
    d.mkdir(parents=True, exist_ok=True)
    (d / "safe-app-manifest.json").write_text(
        json.dumps({"app_id": app, "permissions": perms}), encoding="utf-8"
    )


def run() -> Verdict:
    v = Verdict(trace_id=TRACE_ID, clause=CLAUSE)
    with _staged_gate() as (gate, agents):
        _manifest(agents, "attacker", ["full_access"])
        v.record(Attempt(
            "broad-label-does-not-expand-to-dangerous-tool",
            "agent lists 'full_access' and invokes soil_delete expecting it granted",
            refused=(gate.permitted("attacker", "soil_delete") is False),
            observed=f"permitted(attacker[full_access], soil_delete)={gate.permitted('attacker', 'soil_delete')}",
        ))

        _manifest(agents, "empty", [])
        v.record(Attempt(
            "empty-permissions-deny-all",
            "agent presents an empty permissions list and expects a tool call through",
            refused=(gate.permitted("empty", "soil_get") is False),
            observed=f"permitted(empty[], soil_get)={gate.permitted('empty', 'soil_get')}",
        ))

        v.record(Attempt(
            "unprovisioned-principal-has-no-capability",
            "well-formed app with no signed manifest folder invokes a tool",
            refused=(gate.permitted("emptyRoomProbe0", "soil_get") is False),
            observed=f"permitted(emptyRoomProbe0[no-folder], soil_get)={gate.permitted('emptyRoomProbe0', 'soil_get')}",
        ))

        v.record(Attempt(
            "path-traversal-app-id-denied",
            "agent submits under an id that escapes the agents root",
            refused=(gate.permitted("../../etc", "soil_get") is False),
            observed=f"permitted(../../etc, soil_get)={gate.permitted('../../etc', 'soil_get')}",
        ))
    return v.finalize()


def grant_is_honored() -> tuple[bool, str]:
    """Liveness anchor: a manifest that DOES grant a group can invoke that group's
    tools — the gate discriminates, it is not broken shut."""
    with _staged_gate() as (gate, agents):
        _manifest(agents, "worker", ["store_read"])  # store_read expands to soil_get
        ok = gate.permitted("worker", "soil_get")
    return bool(ok), f"permitted(worker[store_read], soil_get)={ok}"
