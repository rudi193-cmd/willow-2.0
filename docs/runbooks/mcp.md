# Runbook — Willow MCP ecosystem

**b17:** RBM1W · ΔΣ=42  

Full Willow MCP tool surface lives in the fleet configuration (Claude Code / IDE). **Grove MCP** (messages) is implemented in `safe-app-willow-grove` — see [`grove/mcp_local.py`](../../../safe-app-willow-grove/grove/mcp_local.py) and that repo’s [`docs/runbooks/mcp.md`](../../../safe-app-willow-grove/docs/runbooks/mcp.md).

## When debugging “tools don’t see KB”

- Confirm Postgres connectivity to `willow_19`
- Use `willow_knowledge_search` (fleet) — not duplicated here
