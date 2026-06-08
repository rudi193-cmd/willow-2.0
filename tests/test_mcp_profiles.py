"""Tests for sap.mcp_profiles tool visibility."""
from __future__ import annotations

import os


from sap import mcp_profiles as mp


def test_active_profile_default():
    os.environ.pop("WILLOW_MCP_PROFILE", None)
    assert mp.active_profile() == "standard"


def test_allows_tool_tiers():
    assert mp.allows_tool("willow_status", "minimal")
    assert mp.allows_tool("willow_find", "minimal")
    assert mp.allows_tool("willow_code", "core")
    assert not mp.allows_tool("willow_code", "minimal")
    assert mp.allows_tool("fleet_status", "minimal")
    assert mp.allows_tool("fleet_status", "core")
    assert not mp.allows_tool("workflow_run", "standard")
    assert mp.allows_tool("workflow_run", "full")
    assert mp.allows_tool("fleet_tool_guide", "minimal")


def test_filter_counts():
    names = [
        "willow_status",
        "willow_find",
        "willow_code",
        "fleet_status",
        "fleet_tool_guide",
        "workflow_run",
        "kb_search",
        "grove_send_message",
    ]
    assert len(mp.filter_tool_names(names, "minimal")) == 5
    assert "willow_code" not in mp.filter_tool_names(names, "minimal")
    assert "willow_code" in mp.filter_tool_names(names, "core")
    assert "workflow_run" not in mp.filter_tool_names(names, "standard")


def test_unified_list_tools_respects_profile(monkeypatch):
    import asyncio

    monkeypatch.setenv("WILLOW_MCP_PROFILE", "minimal")
    import sap.unified_mcp as unified

    tools = asyncio.run(unified.mcp.list_tools())
    names = {t.name for t in tools}
    assert "fleet_tool_guide" in names
    assert "willow_status" in names
    assert "willow_find" in names
    assert "willow_run" in names
    assert "fleet_status" in names
    assert "workflow_run" not in names
    assert len(names) <= 25


def test_tool_guide_prioritizes_facade():
    guide = mp.format_tool_guide(profile="minimal")
    assert "Start here: willow_status" in guide
    assert "## willow" in guide
    assert guide.index("## willow") < guide.index("## kb")
