Willow MCP · b20: SAPMCP2 · ΔΣ=42

Local-first fleet memory. Orient before you act.

Boot (parallel): fleet_status(app_id=<your-agent-id>) · handoff_latest(app_id=<your-agent-id>).
app_id = caller identity, not dispatch target. If fleet_status is degraded or down: say so and stop.

Then: grove_get_history · kb_search on your task.

Full contract: willow.md (symlink → willow-config; see docs/WILLOW_CONFIG.md).
Public snapshot: docs/CONTRACT.md · Boot steps: willow/fylgja/skills/boot.md · Doc map: docs/INDEX.md.
Tool registry: sap/mcp_registry.json · Human onboarding: sap/ONBOARDING.md

Rules: kb_search before build · mem_check before kb_ingest · agent_task_submit for shell (Kart) · pull Grove before post · write in your namespace only · archive stale atoms, do not delete

Grove messaging (grove_*) lives on the Grove MCP server (safe-app-willow-grove).
