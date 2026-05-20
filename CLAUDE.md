# Claude Code — Willow 2.0

b17: CLDE2 · ΔΣ=42

See [willow.md](willow.md) — canonical fleet entry point for all runtimes.

Default 7-step boot path:

1. Read `willow.md` via `markdownai-read_file`.
2. Establish local operating context: agent, namespace, repo root, branch, and a compact repo diff summary.
3. Call `fleet_status`.
4. Call `handoff_latest`.
5. Call `grove_get_history` for the agent channel/inbox.
6. Call `kb_search` on the current task/topic.
7. If any required base is degraded, surface it and stop; otherwise proceed to act.

If `fleet_status` returns degraded: surface it and stop.

Fallbacks when MCP tools are not available yet:

- Use `./willow.sh fleet_status` for the same boot health summary at the shell.
- Use `./willow.sh handoff_latest` for the latest session handoff.
- Use `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json` only as a cache/fallback when MCP is unavailable.
- Use `/startup` only for degraded boot, stale context, or deeper continuity recovery.
- Refresh or restart the MCP servers after `.cursor/mcp.json`, `sap/willow_mcp.sh`, or `sap/markdownai_mcp.sh` changes.
