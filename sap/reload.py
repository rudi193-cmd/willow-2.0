"""Generation-swap hot reload for the unified Willow MCP server.

ADR-20260704-mcp-true-hot-reload: rebuild the whole tool registry from a
shadow import of the composition module, then atomically swap the live
FastMCP instance's tool manager. The live instance — and with it the
transport and the client session — never restarts. In-flight calls finish
on the generation they started on; any failure during the shadow import
rolls sys.modules back and leaves the old generation serving.

This module is deliberately free of sap/core imports at module level: it
must survive the very purge it performs (see _KEEP).
"""
from __future__ import annotations

import importlib
import logging
import os
import sys

logger = logging.getLogger("sap.reload")

# Everything the shadow import must see fresh. "willow" covers fylgja;
# third-party packages (mcp, psycopg2, …) are never purged.
DEFAULT_PURGE = ("sap", "core", "willow")

# Modules that survive the purge: this one (it is executing the reload).
_KEEP = frozenset({"sap.reload"})

COMPOSITION_MODULE = "sap.unified_mcp"
TOOLS_MODULE = "sap.sap_mcp"

# Singletons initialized by the running server's lifespan. The shadow
# generation's lifespan never runs, so these must be transplanted or the
# new tool bodies would see pg=None / store=None.
_CARRY_ATTRS = ("pg", "store")


def _purge_names(prefixes: tuple[str, ...]) -> list[str]:
    dotted = tuple(p + "." for p in prefixes)
    return [
        name
        for name in list(sys.modules)
        if name not in _KEEP and (name in prefixes or name.startswith(dotted))
    ]


def generation_reload(
    live_mcp,
    *,
    composition_module: str = COMPOSITION_MODULE,
    tools_module: str = TOOLS_MODULE,
    purge_prefixes: tuple[str, ...] = DEFAULT_PURGE,
) -> dict:
    """Shadow-import the composition module and swap the live tool manager.

    Returns {"status": "reloaded", ...} on success, {"status": "rollback", ...}
    with the old generation still serving on any failure.
    """
    if not hasattr(live_mcp, "_tool_manager"):
        return {
            "status": "error",
            "error": "fastmcp_internal_changed",
            "hint": "FastMCP no longer exposes _tool_manager — the generation swap "
                    "needs updating for this mcp SDK version; use fleet_restart.",
        }

    old_tools_mod = sys.modules.get(tools_module)
    snapshot: dict = {}
    for name in _purge_names(purge_prefixes):
        snapshot[name] = sys.modules.pop(name)

    os.environ["WILLOW_MCP_SHADOW"] = "1"
    try:
        importlib.invalidate_caches()
        comp = importlib.import_module(composition_module)
        new_mcp = comp.mcp
        if not hasattr(new_mcp, "_tool_manager"):
            raise RuntimeError("shadow composition has no _tool_manager")

        new_tools_mod = sys.modules.get(tools_module)
        carried: list[str] = []
        if old_tools_mod is not None and new_tools_mod is not None:
            for attr in _CARRY_ATTRS:
                if hasattr(old_tools_mod, attr):
                    setattr(new_tools_mod, attr, getattr(old_tools_mod, attr))
                    carried.append(attr)

        # Reuse the live thread pool: tool bodies resolve `_executor` as a
        # module attribute at call time, so rebinding both name-bound copies
        # keeps old and new generations on one pool instead of leaking one
        # ThreadPoolExecutor per reload.
        old_mw = snapshot.get("sap.middleware")
        new_mw = sys.modules.get("sap.middleware")
        old_executor = getattr(old_mw, "_executor", None) if old_mw else None
        if old_executor is not None and new_mw is not None:
            fresh = getattr(new_mw, "_executor", None)
            new_mw._executor = old_executor
            if new_tools_mod is not None and hasattr(new_tools_mod, "_executor"):
                new_tools_mod._executor = old_executor
            if fresh is not None and fresh is not old_executor:
                fresh.shutdown(wait=False)
            carried.append("_executor")

        tool_count = len(getattr(new_mcp._tool_manager, "_tools", {}) or {})

        # The atomic swap: one attribute assignment on the object that owns
        # the running transport. Old closures keep serving in-flight calls.
        live_mcp._tool_manager = new_mcp._tool_manager

        logger.info(
            "[w2] generation reload OK — %d tools, carried=%s, purged=%d",
            tool_count, carried, len(snapshot),
        )
        return {
            "status": "reloaded",
            "generation_tools": tool_count,
            "carried": carried,
            "purged_modules": len(snapshot),
        }
    except Exception as e:
        # Drop whatever the failed import managed to register, then restore
        # the old module graph verbatim — the old generation keeps serving.
        for name in _purge_names(purge_prefixes):
            if name not in snapshot:
                sys.modules.pop(name, None)
        sys.modules.update(snapshot)
        logger.exception("[w2] generation reload failed — old generation kept")
        return {
            "status": "rollback",
            "error": f"{type(e).__name__}: {e}",
            "hint": "old code still serving; fix the broken merge or fleet_restart",
        }
    finally:
        os.environ.pop("WILLOW_MCP_SHADOW", None)
