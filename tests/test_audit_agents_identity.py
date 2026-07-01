"""#602 — the _AUDIT_AGENTS Bash-block exemption in pre_tool.py must key off
WILLOW_AGENT_NAME (fleet identity, via require_agent_name()) and never off
persona state. "loki" is both a valid fleet agent name and a persona label
(willow/fylgja/personas/loki.md) -- a regression that ever read persona
instead of fleet identity here would silently grant the audit-agent Bash
exemption to any agent with persona=loki, regardless of its real identity.

This test locks the *source*, not just the current value: AGENT in
pre_tool.py must equal require_agent_name(), full stop -- it must not read
any persona file, persona env var, or persona SOIL state.
"""
import importlib
import inspect

from core.agent_identity import require_agent_name


def test_pre_tool_agent_is_sourced_from_require_agent_name(monkeypatch):
    monkeypatch.setenv("WILLOW_AGENT_NAME", "willow")
    import willow.fylgja.events.pre_tool as pre_tool
    importlib.reload(pre_tool)
    try:
        assert pre_tool.AGENT == require_agent_name() == "willow"
    finally:
        importlib.reload(pre_tool)


def test_pre_tool_agent_ignores_persona_label(monkeypatch):
    """Setting a persona-flavored env var must not affect AGENT resolution --
    only WILLOW_AGENT_NAME may. Regression guard for #602."""
    monkeypatch.setenv("WILLOW_AGENT_NAME", "hanuman")
    monkeypatch.setenv("WILLOW_2_0_ACTIVE_PERSONA", "loki")
    import willow.fylgja.events.pre_tool as pre_tool
    importlib.reload(pre_tool)
    try:
        assert pre_tool.AGENT == "hanuman"
        assert pre_tool.AGENT not in pre_tool._AUDIT_AGENTS
    finally:
        importlib.reload(pre_tool)


def test_check_bash_block_source_does_not_reference_persona():
    """Static guard: the module that defines _AUDIT_AGENTS must not import
    or reference persona resolution at all, so the exemption can never be
    keyed off anything but fleet identity."""
    import willow.fylgja.events.pre_tool as pre_tool
    src = inspect.getsource(pre_tool)
    assert "active_persona" not in src
    assert "willow-2.0-active-persona" not in src
