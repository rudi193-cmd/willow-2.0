"""tests/test_fylgja/test_mcp_routing.py"""

import pytest

from willow.fylgja.mcp_routing import redirect_for_command, format_brief, format_cheat_sheet


def test_redirect_ls_blocks_to_kart():
    result = redirect_for_command("ls -la /tmp")
    assert result is not None
    assert result[0] == "block"
    assert "agent_task_submit" in result[1]


def test_redirect_git_warns_to_kart():
    result = redirect_for_command("git status -sb")
    assert result is not None
    assert result[0] == "warn"
    assert "agent_task_submit" in result[1]


def test_redirect_gh_warns_to_kart():
    result = redirect_for_command("gh pr view 440")
    assert result is not None
    assert result[0] == "warn"
    assert "allow_net" in result[1].lower()


def test_redirect_grep_blocks_and_names_grep_tool():
    result = redirect_for_command("grep -rn foo willow/")
    assert result is not None
    assert result[0] == "block"
    assert "Grep(" in result[1]


def test_redirect_find_blocks_and_names_glob():
    result = redirect_for_command("find . -name '*.py'")
    assert result is not None
    assert result[0] == "block"
    assert "Glob(" in result[1]


def test_format_brief_two_lanes():
    assert "[WILLOW-LANES]" in format_brief()
    assert "willow_find" in format_brief()
    assert "willow_run" in format_brief()


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
