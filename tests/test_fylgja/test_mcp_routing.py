"""tests/test_fylgja/test_mcp_routing.py"""

import pytest

from willow.fylgja.mcp_routing import redirect_for_command, format_brief, format_cheat_sheet


def test_redirect_ls_blocks_to_kart():
    result = redirect_for_command("ls -la /tmp")
    assert result is not None
    assert result[0] == "block"
    assert "willow_run" in result[1]


def test_redirect_git_inspect_allowed():
    assert redirect_for_command("git status -sb") is None
    assert redirect_for_command("git log --oneline -5") is None


def test_redirect_git_mutations_blocked():
    result = redirect_for_command("git commit -m 'x'")
    assert result is not None
    assert result[0] == "block"
    assert "willow_run" in result[1]


def test_redirect_gh_inspect_allowed():
    assert redirect_for_command("gh pr view 440") is None


def test_redirect_gh_mutations_blocked():
    result = redirect_for_command("gh pr create --title x")
    assert result is not None
    assert result[0] == "block"
    assert "willow_run" in result[1]


def test_redirect_grep_routes_to_available_tools():
    result = redirect_for_command("grep -rn foo willow/")
    assert result is not None
    assert result[0] == "block"
    # Must NOT point at native Grep/Glob — absent under the Willow MCP profile,
    # which sends agents to a tool the session lacks and they bounce to Bash.
    assert "Grep(" not in result[1]
    assert "Glob(" not in result[1]
    # Must name lanes that always exist when this redirect fires.
    assert "willow_find" in result[1] or "code_graph_search" in result[1]
    assert "willow_run" in result[1] or "agent_task_submit" in result[1]


def test_redirect_find_routes_to_available_tools():
    result = redirect_for_command("find . -name '*.py'")
    assert result is not None
    assert result[0] == "block"
    assert "Glob(" not in result[1]
    assert "code_graph_search" in result[1] or "willow_find" in result[1]
    assert "willow_run" in result[1] or "agent_task_submit" in result[1]


def test_no_redirect_names_native_grep_or_glob():
    """Regression: no BASH_TO_MCP hint may steer to native Grep/Glob — they are
    not in the Willow MCP profile this redirect runs under."""
    from willow.fylgja.mcp_routing import BASH_TO_MCP

    for _pattern, _decision, hint in BASH_TO_MCP:
        assert "Grep(" not in hint, hint
        assert "Glob(" not in hint, hint


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
    assert "willow_run" in result[1]
