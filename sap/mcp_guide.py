"""fleet_tool_guide — MCP tool catalog (always visible)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sap.mcp_profiles import active_profile, format_tool_guide

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: "FastMCP") -> None:
    @mcp.tool()
    def fleet_tool_guide(group: str = "", profile: str = "") -> str:
        """
        List Willow MCP tools grouped by domain for the active profile.

        Use when unsure which tool to call — faster than scrolling 100+ tools in the IDE.
        Set WILLOW_MCP_PROFILE=full to expose every tool.

        Args:
            group: Optional filter (kb, soil, fleet, grove, mai, agent, …).
            profile: Override profile for this listing (minimal|core|standard|full).
        """
        prof = profile.strip().lower() if profile else active_profile()
        return format_tool_guide(profile=prof, group=group.strip().lower() or None)
