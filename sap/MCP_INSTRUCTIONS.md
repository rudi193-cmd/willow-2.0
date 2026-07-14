Willow MCP · b20: SAPMCP2 · ΔΣ=42

Local-first fleet memory. Orient before you act.

Boot (parallel): fleet_status(app_id=<your-agent-id>) · handoff_latest(app_id=<your-agent-id>) · boot_digest.
app_id = caller identity, not dispatch target. If fleet_status is degraded or down: say so and stop.

Then: grove_get_history · kb_search on your task.

**Reuse rails (before inventing tools/scripts/MCP):**

| Intent | Tool |
|--------|------|
| Orient | `willow_status`, `boot_digest` (digest `tools:` line lists wired servers) |
| Find | `willow_find` |
| Run shell | `willow_run` / `agent_task_submit` + `kart_task_run` |
| Remember | `willow_remember` |
| Code discovery | `cbm_status` → `cbm_search` / `cbm_trace` / `cbm_verify_callers` (not new Kart inventory scripts) |

Full contract: willow.md (public root; private ~/.willow/willow.md may overlay it; see docs/WILLOW_CONFIG.md).
Public snapshot: docs/CONTRACT.md · Boot: willow/fylgja/skills/boot.md · **MCP-first:** willow/fylgja/skills/mcp-first.md · Doc map: docs/INDEX.md.
Tool registry: sap/mcp_registry.json · Human onboarding: sap/ONBOARDING.md

Rules: kb_search before build · mem_check before kb_ingest · agent_task_submit for shell (Kart) · pull Grove before post · write in your namespace only · archive stale atoms, do not delete

Grove messaging (grove_*) lives on the Grove MCP server (safe-app-willow-grove).
