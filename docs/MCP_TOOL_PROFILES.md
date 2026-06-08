# MCP tool profiles

b17: MCPPRF · ΔΣ=42

The unified `willow` MCP registers **~160 tools**. IDEs show all of them in the picker — too many for humans and models.

## Start Here: Facade Tools

Agents should reach for the `willow_*` facade first. These tools route to the older backend lanes while keeping the visible choice small.

| Facade | Use when |
|--------|----------|
| `willow_status` | You need health, identity, app, or diagnostic status. |
| `willow_find` | You need to find knowledge, state, messages, sessions, code, handoffs, or sources. |
| `willow_remember` | You need to save an observation, note, task, context, journal entry, or decision. |
| `willow_run` | You need to submit, run, list, or inspect Kart work. |
| `willow_delegate` | You need to route or dispatch work to another agent. |
| `willow_work` | You need to create, inspect, list, or log a bounded work unit. |
| `willow_message` | You need to read, search, or send Grove messages. |
| `willow_app` | You need SAFE app status or registration visibility. |
| `willow_external` | You need cited external lookup or source-trail verification. |
| `willow_code` | You need code graph search or file suggestions. |

Backend tools remain available for precise subsystem work; they are not the default starting point.

## Fix: `WILLOW_MCP_PROFILE`

Set in `sap/unified_mcp.sh` (default **`core`**) or agent `mcp.json` env:

| Profile | ~Tools | Use when |
|---------|--------|----------|
| `minimal` | <25 | Facade + boot primitives — status, find, remember, run |
| `core` | ~55 | Daily coding — facade + soil, ledger, mai write, Grove basics |
| `standard` | 73 | Broader fleet work without soul/workflow/rare mem |
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
| `willow_` | Canonical facade — start here |
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
