# b17: 9FB73  ΔΣ=42
from __future__ import annotations
import re

_MCP_RE = re.compile(r"^mcp__(.+?)__(.+)$")


def normalize_tool_name(raw: str) -> str:
    """
    mcp__grove__grove_send_message          → grove.grove_send_message
    mcp__claude_ai_Grove__grove_send_message → grove.grove_send_message
    mcp__user_grove__grove_send_message     → grove.grove_send_message
    Unknown prefixes: best-effort, never raise.
    """
    m = _MCP_RE.match(raw)
    if m:
        provider, tool = m.group(1), m.group(2)
        namespace = provider.split("_")[-1].lower()
        return f"{namespace}.{tool}"
    return raw.replace("__", ".")
