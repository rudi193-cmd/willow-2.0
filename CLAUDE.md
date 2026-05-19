See [willow.md](willow.md) — canonical fleet entry point for all runtimes.

Boot: call `fleet_status` + `handoff_latest` in parallel before responding to anything.
If `fleet_status` returns degraded: surface it and stop.

Fallbacks when MCP tools are not available yet:

- Use `./willow.sh fleet_status` for the same boot health summary at the shell.
- Use `./willow.sh handoff_latest` for the latest session handoff.
- Refresh or restart the MCP servers after `.cursor/mcp.json`, `sap/willow_mcp.sh`, or `sap/markdownai_mcp.sh` changes.
