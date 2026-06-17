"""
willow/flags.py — Live gap flagging.
b17: FLAG1  ΔΣ=42

Write flags to {agent}/flags without going through MCP (agent from WILLOW_AGENT_NAME).
Importable from hooks, shutdown, anywhere in the system.

Usage:
    from willow.flags import flag, clear_flag, list_flags

    flag("BOOT-SHOOT-IMPORTS",
         title="shoot.py has broken imports",
         bridge="root.py → shoot.py",
         gap="from seed import ... will crash",
         severity="major")

    clear_flag("BOOT-SHOOT-IMPORTS")
"""
import math
from core.agent_identity import require_agent_name
from core.store_port import get_store_port

_AGENT      = require_agent_name()
_COLLECTION = f"{_AGENT}/flags"

_SEVERITY_DEVIATION = {
    "routine":     0.0,
    "significant": math.pi / 4,   # ~0.785
    "major":       math.pi / 2,   # ~1.571
    "reversal":    math.pi,        # ~3.142
}


def flag(
    flag_id: str,
    title: str,
    bridge: str,
    gap: str,
    severity: str = "significant",
    file: str = "",
) -> str:
    """Write or overwrite a flag. Returns the flag_id."""
    store = get_store_port()
    deviation = _SEVERITY_DEVIATION.get(severity, math.pi / 4)
    store.put(
        _COLLECTION,
        {
            "id":       flag_id,
            "title":    title,
            "bridge":   bridge,
            "gap":      gap,
            "severity": severity,
            "file":     file,
        },
        record_id=flag_id,
        deviation=deviation,
    )
    return flag_id


def clear_flag(flag_id: str) -> bool:
    """Remove a flag by ID. Returns True if it existed."""
    store = get_store_port()
    return store.delete(_COLLECTION, flag_id)


def list_flags() -> list[dict]:
    """Return all active flags, sorted by severity (major first)."""
    store = get_store_port()
    order = {"reversal": 0, "major": 1, "significant": 2, "routine": 3}
    flags = [record.get("data", record) for record in store.list(_COLLECTION)]
    return sorted(flags, key=lambda f: order.get(f.get("severity", "routine"), 9))


def flag_ids() -> set[str]:
    """Return just the set of active flag IDs."""
    return {f["id"] for f in list_flags()}
