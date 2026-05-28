"""Tests for sap.mai.tools — mai_write_file and helpers."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from sap.mai import tools as mai_tools
from sap.mai import parser


def _list_mai_tools():
    from mcp.server.fastmcp import FastMCP

    m = FastMCP("test-mai")
    mai_tools.register(m)
    return asyncio.run(m.list_tools())


def test_mai_write_file_on_disk(tmp_path):
    path = tmp_path / "doc.md"
    content = "@markdownai v1.0\n\n# Test\n\nHello.\n"

    from mcp.server.fastmcp import FastMCP

    m = FastMCP("test-mai")
    mai_tools.register(m)
    result = asyncio.run(
        m.call_tool("mai_write_file", {"path": str(path), "content": content})
    )
    assert '"ok": true' in str(result[0]) or "ok': True" in str(result[0])
    assert path.read_text(encoding="utf-8") == content


def test_markdownai_detected_after_yaml_frontmatter():
    raw = "---\nagent: hanuman\ndate: 2026-05-28\n---\n\n@markdownai v1.0\n\n# Hi\n"
    assert mai_tools._is_markdownai_content(raw)
    body = mai_tools._markdownai_body(raw)
    assert body.startswith("@markdownai")


def test_mai_write_file_strips_header_guard(tmp_path):
    path = tmp_path / "keep.md"
    path.write_text("@markdownai v1.0\n\nOld\n", encoding="utf-8")
    bad = "plain markdown without header"
    assert mai_tools._is_markdownai_path(path)
    assert not mai_tools._is_markdownai_content(bad)


def test_registry_lists_ten_mai_tools():
    tools = _list_mai_tools()
    names = [t.name for t in tools if t.name.startswith("mai_")]
    assert "mai_write_file" in names
    assert "mai_read_file" in names
    assert len(names) == 10


def test_markdownai_write_block_reason():
    from willow.fylgja.events.pre_tool import _markdownai_write_block

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bifrost.md"
        p.write_text("@markdownai v1.0\n\n# X\n", encoding="utf-8")
        msg = _markdownai_write_block(
            "Write",
            {"file_path": str(p), "content": "# stripped\n"},
        )
        assert msg is not None
        assert "mai_write_file" in msg
