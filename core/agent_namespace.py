"""Per-agent SOIL/KB namespace helpers — no shared hanuman bucket."""
from __future__ import annotations

from core.agent_identity import require_agent_name


def agent_name(explicit: str = "") -> str:
    return explicit.strip() or require_agent_name()


def soil_collection(suffix: str, *, agent: str = "") -> str:
    """e.g. heimdallr/kb_read_log — never hardcode hanuman."""
    name = agent_name(agent)
    return f"{name}/{suffix.lstrip('/')}"
