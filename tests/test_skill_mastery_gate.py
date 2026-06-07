# b17: SKMS1  ΔΣ=42
"""Gate coverage for the skill_mastery MCP tool.

History: a pre-wiring version of this test (in scratch/) proved the gate is
fail-closed — skill_mastery was DENIED before being registered in gate.py
(commit d7a0da7). Now that it is wired into PERMISSION_GROUPS["skill_read"],
this is the regression lock: skill_mastery must be permitted for skill_read
holders, AND the gate must stay fail-closed for any tool that is NOT registered.

Mirrors tests/test_sap_gate.py (import sap.core.gate directly, patch globals).
"""
import asyncio
import json
import os
from pathlib import Path

# gate.py reads WILLOW_SAFE_ROOT at import time; be self-sufficient.
os.environ.setdefault("WILLOW_SAFE_ROOT", "/tmp/willow-test-safe")

from sap.core import gate

TOOL = "skill_mastery"
BOGUS = "definitely_not_a_registered_tool"


def _seed_agent(root: Path, perms: list, app_id: str = "willow-test") -> str:
    d = root / app_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "safe-app-manifest.json").write_text(json.dumps({"permissions": perms}))
    return app_id


# ── registration lock ────────────────────────────────────────────────────────

def test_skill_mastery_registered_in_skill_read():
    assert TOOL in gate.PERMISSION_GROUPS["skill_read"]


# ── permitted(): registered tool allowed, unregistered still denied ──────────

class TestPermitted:
    def test_registered_tool_allowed_for_skill_read_holder(self, tmp_path, monkeypatch):
        app_id = _seed_agent(tmp_path, ["skill_read"])
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)
        # now wired → allowed
        assert gate.permitted(app_id, TOOL) is True
        # control: the gate is STILL fail-closed for an unregistered tool, even
        # for this same authorized agent
        assert gate.permitted(app_id, BOGUS) is False

    def test_denied_without_skill_read_permission(self, tmp_path, monkeypatch):
        app_id = _seed_agent(tmp_path, ["postgres_read"])  # different group
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)
        assert gate.permitted(app_id, TOOL) is False

    def test_fail_closed_without_manifest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)   # empty dir
        monkeypatch.setattr(gate, "SAFE_ROOT", tmp_path)
        monkeypatch.setattr(gate, "PROFESSOR_ROOT", tmp_path)
        assert gate.permitted("ghost-agent", TOOL) is False


# ── end-to-end: @sap_gate() still denies an UNREGISTERED tool ─────────────────

class TestGateWrapperFailClosed:
    """Same isolation as the original pre-wiring proof (policy ok, rate limit
    skipped, PGP simulated-pass) — so a not_permitted response can only mean the
    tool is unregistered. Uses a bogus tool to show the property still holds for
    an agent that legitimately holds skill_read."""

    def test_unregistered_tool_returns_not_permitted(self, tmp_path, monkeypatch):
        import sap.middleware as m

        app_id = _seed_agent(tmp_path, ["skill_read"])
        monkeypatch.setattr(gate, "AGENTS_ROOT", tmp_path)
        monkeypatch.setenv("WILLOW_MOCK_POLICY", "[]")
        monkeypatch.setenv("WILLOW_AGENT_NAME", app_id)
        monkeypatch.setattr(m, "_GLEIPNIR", None)
        monkeypatch.setattr(m, "sap_authorized", lambda a: True)

        @m.sap_gate()
        async def definitely_not_a_registered_tool(app_id: str) -> dict:
            return {"ok": True}  # must NOT be reached

        resp = asyncio.run(definitely_not_a_registered_tool(app_id))
        assert resp == {"error": "not_permitted", "app_id": app_id, "tool": BOGUS}
