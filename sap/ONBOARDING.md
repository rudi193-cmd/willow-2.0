# Willow MCP — Onboarding

b20: SAPMCP2 · ΔΣ=42

**Two surfaces — do not duplicate:**

| Surface | File | Audience |
|---------|------|----------|
| MCP server `instructions` | [`MCP_INSTRUCTIONS.md`](MCP_INSTRUCTIONS.md) | IDE injects this at connect (keep minimal) |
| Human/agent doc | this file | Repo readers — links to full contract |

Full fleet contract: [`willow.md`](../willow.md) (private **willow-config**; public snapshot: [`../docs/CONTRACT.md`](../docs/CONTRACT.md)).  
Boot sequence: [`willow/fylgja/skills/boot.md`](../willow/fylgja/skills/boot.md).

## Orient (parallel)

```
fleet_status(app_id=<your-agent-id>)
handoff_latest(app_id=<your-agent-id>)
```

`app_id` = your agent name (caller identity), not a dispatch target. If `fleet_status` is degraded or down: report and **stop**.

Then: Grove inbox/history · `kb_search` on your task.

Shell fallback: `./willow.sh fleet_status` · `./willow.sh handoff_latest`

## Tools

**Registry (source of truth):** [`mcp_registry.json`](mcp_registry.json) — grouped prefixes, 80+ tools.

**Profiles (reduce IDE noise):** [`../docs/MCP_TOOL_PROFILES.md`](../docs/MCP_TOOL_PROFILES.md)

Grove messaging (`grove_*`) lives on the **Grove MCP** server (`safe-app-willow-grove`).

## Rules (one line each)

- `kb_search` before design; `mem_check` before `kb_ingest`
- Pull Grove history before non-trivial posts
- Shell work → `agent_task_submit` (Kart), not raw Bash when MCP is up
- Write in your namespace only; archive stale atoms, do not delete

*ΔΣ=42*
