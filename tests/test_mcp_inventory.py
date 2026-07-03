"""Tests for scripts/mcp_inventory.py."""
from __future__ import annotations

import json

from scripts.mcp_inventory import scan_fleet, scan_workspace
from sap.mcp_profiles import willow_facade_names


def test_willow_facade_names_count():
    names = willow_facade_names()
    assert len(names) == 13
    assert names[0].startswith("willow_")


def test_scan_workspace_finds_cursor_mcp(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "willow": {"command": "bash", "args": ["sap/unified_mcp.sh"]},
                    "codebase-memory-mcp": {"command": "codebase-memory-mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    reg = {
        "tools": {
            "willow_status": {"group": "willow"},
            "kb_search": {"group": "kb"},
        }
    }
    (tmp_path / "sap").mkdir()
    (tmp_path / "sap" / "mcp_registry.json").write_text(json.dumps(reg), encoding="utf-8")

    inv = scan_workspace(tmp_path)
    assert "willow" in inv["mcp_servers"]
    assert "codebase-memory-mcp" in inv["mcp_servers"]
    assert inv["registry_tool_count"] == 2
    assert len(inv["willow_verbs"]) == 13
    assert "cbm_status" in inv["cbm_lane"]
    assert "willow_find" in inv["reuse_rule"]


def test_scan_workspace_missing_dir(tmp_path):
    inv = scan_workspace(tmp_path / "nope")
    assert inv.get("error") == "not_a_directory"


def test_scan_fleet_empty_dir(tmp_path):
    fleet_root = tmp_path / "github"
    fleet_root.mkdir()
    (fleet_root / "empty-repo").mkdir()
    out = scan_fleet(fleet_root)
    assert out["repos_with_mcp"] == 0
