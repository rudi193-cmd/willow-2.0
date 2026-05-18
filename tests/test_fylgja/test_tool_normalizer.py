# b17: F4FBE  ΔΣ=42
from willow.fylgja.hosts.tool_normalizer import normalize_tool_name


def test_t6a_grove_prefix():
    assert normalize_tool_name("mcp__grove__grove_send_message") == "grove.grove_send_message"


def test_t6b_claude_ai_prefix():
    assert normalize_tool_name("mcp__claude_ai_Grove__grove_send_message") == "grove.grove_send_message"


def test_t6c_unknown_passthrough():
    result = normalize_tool_name("some_unknown_tool")
    assert isinstance(result, str)
    assert result == "some_unknown_tool"


def test_t6c_double_underscore_fallback():
    result = normalize_tool_name("foo__bar")
    assert result == "foo.bar"
    assert isinstance(result, str)
