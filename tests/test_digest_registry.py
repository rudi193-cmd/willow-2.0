"""Boot digest section registry and mcp_inventory provider."""
from __future__ import annotations

import json

import willow.fylgja.boot_digest as boot_digest_mod
from willow.fylgja.boot_digest import build_boot_digest, render_lines
from willow.fylgja.digest_registry import load_registry_config, pluggable_sections


def test_digest_sections_registry_has_mcp_inventory():
    cfg = load_registry_config()
    sections = cfg.get("sections") or []
    ids = [s["id"] for s in sections if isinstance(s, dict)]
    assert "mcp_inventory" in ids
    plug = pluggable_sections()
    assert any(p["id"] == "mcp_inventory" for p in plug)


def test_digest_renders_mcp_inventory_lines(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / ".cursor").mkdir()
    (repo / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"willow": {"command": "bash"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        boot_digest_mod,
        "fetch_latest_handoff",
        lambda agent, *, project="", workspace="": {"error": "none"},
    )

    digest = build_boot_digest(
        "testagent",
        workspace=str(repo),
        repo_root=str(repo),
        include_attention=False,
    )
    inv = (digest.get("sections") or {}).get("mcp_inventory") or {}
    assert "willow" in (inv.get("mcp_servers") or [])

    lines = render_lines(digest)
    text = "\n".join(lines)
    assert "tools: servers=willow" in text
    assert "reuse:" in text
    assert "code: cbm_status" in text
