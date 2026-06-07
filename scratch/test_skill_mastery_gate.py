"""SCRATCH — verify sap_gate is fail-closed for an UNREGISTERED tool.

Goal (requested before any main-code change): prove that `skill_mastery`,
*before* it is added to PERMISSION_GROUPS in sap/core/gate.py, is DENIED by the
gate — i.e. the gate defaults to deny, so a tool you forget to register can
never be called. The denial surfaces as the 403-equivalent security error
`{"error": "not_permitted", ...}` (sap/middleware.py:387).

Mirrors:
  - tests/test_sap_gate.py — import sap.core.gate directly, patch module globals.
  - tests/test_s_tier_tools.py — exercise the gate decision (`permitted`) and the
    middleware response directly rather than the full IDE/MCP stack.

scratch/, not tests/ — pytest testpaths=["tests"], so CI does not collect this.
Run by hand:  python -m pytest scratch/test_skill_mastery_gate.py -v
"""
import asyncio
import json
import os
from pathlib import Path

# gate.py reads WILLOW_SAFE_ROOT at import time and raises if it is unset.
os.environ.setdefault("WILLOW_SAFE_ROOT", "/tmp/willow-scratch-safe")

import pytest
from sap.core import gate

TOOL = "skill_mastery"


def _seed_agent(root: Path, perms: list, app_id: str = "willow-test") -> str:
    """Create a SAFE agent dir under `root` with a manifest granting `perms`."""
    d = root / app_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "safe-app-manifest.json").write_text(json.dumps({"permissions": perms}))
    return app_id


# ── precondition: the tool really is unregistered ────────────────────────────

def test_skill_mastery_absent_from_every_permission_group():
    """If this fails, skill_mastery was already added — the negative test is moot."""
    everywhere = set()
    for group in gate.PERMISSION_GROUPS.values():
        everywhere |= set(group)
    assert TOOL not in everywhere
    # the group it WOULD eventually join grants only today's skill tools
    assert gate.PERMISSION_GROUPS["skill_read"] == frozenset({"skill_list", "skill_load"})


# ── gate decision: permitted() is fail-closed ────────────────────────────────

class TestPermittedDenies:
    def test_unregistered_tool_denied_for_otherwise_authorized_agent(self, tmp_path, monkeypatch):
        app_id = _seed_agent(tmp_path, ["skill_read"])
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)
        # DENIED: skill_mastery is in no group this agent holds
        assert gate.permitted(app_id, TOOL) is False
        # CONTROL: the same agent IS authorized for the registered skill tools,
        # so the denial above is specifically the missing ACL entry — not a
        # blanket "agent unknown".
        assert gate.permitted(app_id, "skill_list") is True

    def test_denied_when_agent_has_no_manifest(self, tmp_path, monkeypatch):
        # fail-closed: no SAFE folder anywhere → deny
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)   # empty dir
        monkeypatch.setattr(gate, "SAFE_ROOT", tmp_path)
        monkeypatch.setattr(gate, "PROFESSOR_ROOT", tmp_path)
        assert gate.permitted("ghost-agent", TOOL) is False


# ── end-to-end: the @sap_gate() wrapper returns the 403-equivalent ───────────

class TestGateWrapperReturnsNotPermitted:
    """Drive the real sap_gate decorator. We isolate the per-tool ACL as the ONLY
    gate that can fail (policy → ok, rate limit skipped, PGP simulated-pass), so a
    `not_permitted` response can only mean: skill_mastery is unregistered."""

    def test_calling_skill_mastery_returns_not_permitted(self, tmp_path, monkeypatch):
        import sap.middleware as m

        app_id = _seed_agent(tmp_path, ["skill_read"])
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)
        monkeypatch.setenv("WILLOW_MOCK_POLICY", "[]")            # policy → ok
        monkeypatch.setenv("WILLOW_AGENT_NAME", app_id)          # identity bind → ok
        monkeypatch.setattr(m, "_GLEIPNIR", None)                # skip rate limit
        monkeypatch.setattr(m, "sap_authorized", lambda a: True)  # simulate PGP pass
        # m.sap_permitted stays REAL (= gate.permitted) → the ACL truly decides.

        @m.sap_gate()
        async def skill_mastery(app_id: str, skill_id: str = "") -> dict:
            return {"ok": True, "skill_id": skill_id}  # must NOT be reached

        resp = asyncio.run(skill_mastery(app_id, skill_id="willow/babysit"))
        assert resp == {"error": "not_permitted", "app_id": app_id, "tool": "skill_mastery"}

    def test_registered_tool_passes_acl_same_agent(self, tmp_path, monkeypatch):
        """Control: the identical setup ALLOWS a registered tool (skill_list)
        through the ACL — proving the deny above is the missing registration,
        not a misconfigured harness. (Asserted at the gate-decision layer to
        avoid the wrapper's post-dispatch result-scan dependencies.)"""
        import sap.middleware as m  # noqa: F401  (same import surface as above)

        app_id = _seed_agent(tmp_path, ["skill_read"])
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)
        assert gate.permitted(app_id, "skill_list") is True
        assert gate.permitted(app_id, TOOL) is False
