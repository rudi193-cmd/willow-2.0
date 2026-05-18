# core/agent_identity.py — Agent identity gate. b17: AGID1  ΔΣ=42
import os


def require_agent_name() -> str:
    """Return WILLOW_AGENT_NAME or raise — no silent defaults."""
    name = os.environ.get("WILLOW_AGENT_NAME", "").strip()
    if not name:
        raise EnvironmentError(
            "WILLOW_AGENT_NAME is not set — "
            "you cannot be in this system without an agent identity."
        )
    return name
