"""tests/test_fylgja/test_mcp_routing.py"""

import pytest

from willow.fylgja.mcp_routing import redirect_for_command, format_brief, format_cheat_sheet


def test_redirect_ls_blocks_to_kart():
    result = redirect_for_command("ls -la /tmp")
    assert result is not None
    assert result[0] == "block"
    assert "agent_task_submit" in result[1]


def test_format_brief_two_lanes():
    assert "[WILLOW-LANES]" in format_brief()
    assert "kart_task_run" in format_brief()


def test_cheat_sheet_lists_groups():
    sheet = format_cheat_sheet(max_groups=3)
    assert "[WILLOW-LANES]" in sheet
    assert "exec:" in sheet


@pytest.fixture()
def pre_tool_check(monkeypatch):
    monkeypatch.setenv("WILLOW_AGENT_NAME", "hanuman")
    from willow.fylgja.events import pre_tool

    return pre_tool.check_bash_block


def test_check_bash_block_ls(pre_tool_check):
    result = pre_tool_check("ls")
    assert result is not None
    assert result[0] == "block"
    assert "agent_task_submit" in result[1]
