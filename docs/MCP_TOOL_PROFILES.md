# MCP tool profiles

b17: MCPPRF · ΔΣ=42

The unified `willow` MCP registers **~160 tools**. IDEs show all of them in the picker — too many for humans and models.

## Fix: `WILLOW_MCP_PROFILE`

Set in `sap/unified_mcp.sh` (default **`standard`**) or agent `mcp.json` env:

| Profile | ~Tools | Use when |
|---------|--------|----------|
| `minimal` | 10 | Boot only — status, handoff, kb search, grove inbox, kart |
| `core` | 38 | Daily coding — soil, ledger, mai write, grove post |
| `standard` | 73 | Default — most fleet work without soul/workflow/rare mem |
| `full` | 160 | Debugging, Jeles, workflows, routines, all grove watchers |

Restart MCP / IDE after changing the profile.

## Discovery

Call **`fleet_tool_guide`** (visible in every profile) — grouped catalog from `sap/mcp_registry.json`.

SessionStart also injects a short `[WILLOW-LANES]` cheat sheet via `mcp_routing.py`.

## Two servers (optional)

For occasional full access without toggling env:

```json
{
  "mcpServers": {
    "willow": {
      "command": "bash",
      "args": ["/path/to/willow-2.0/sap/unified_mcp.sh"],
      "env": { "WILLOW_MCP_PROFILE": "standard", "WILLOW_AGENT_NAME": "willow" }
    },
    "willow-full": {
      "command": "bash",
      "args": ["/path/to/willow-2.0/sap/unified_mcp.sh"],
      "env": { "WILLOW_MCP_PROFILE": "full", "WILLOW_AGENT_NAME": "willow" }
    }
  }
}
```

Disable `willow-full` in the IDE when not needed.

## Prefix map (mental model)

| Prefix | Lane |
|--------|------|
| `fleet_` `kb_` `soil_` `handoff_` `ledger_` | Data |
| `agent_task_submit` `kart_task_run` | Execution (Kart) |
| `grove_` | Messaging |
| `mai_` | MarkdownAI docs |
| `code_graph_` `fork_` `skill_` | Dev / session |
| `workflow_` `routine_` `cmb_` `context_` | **full** profile only |

Implementation: `sap/mcp_profiles.py` · registry: `sap/mcp_registry.json`

## MCP spec (2025-11-25)

- Pin: [`sap/MCP_SPEC.lock.json`](../sap/MCP_SPEC.lock.json)
- Compliance matrix: [`MCP_SPEC_COMPLIANCE.md`](MCP_SPEC_COMPLIANCE.md)
- Tools get `title`, `annotations`, and `_meta.willow.*` via `sap/mcp_enrich.py`
- Drift check: `python3 scripts/check_mcp_registry.py --strict`
- Comfort gate: `./scripts/comfort_check.sh --ci` (local: `--local`)

ΔΣ=42
