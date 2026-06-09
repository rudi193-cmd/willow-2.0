# SAP — Willow MCP server

b20: SAPMCP2 · ΔΣ=42

Branding: [`../docs/BRANDING.md`](../docs/BRANDING.md)

The Sovereign Application Protocol gate and MCP surface. Exposes KB, SOIL, fleet health, tasks, handoffs, and inference to any MCP client.

---

## Connect

**Canonical launcher** (sets venv, paths, DB):

```json
{
  "mcpServers": {
    "willow": {
      "command": "bash",
      "args": ["sap/unified_mcp.sh"],
      "env": {
        "WILLOW_AGENT_NAME": "your_agent",
        "WILLOW_PG_DB": "willow_20"
      }
    }
  }
}
```

Copy from [`.mcp.json.example`](../.mcp.json.example) at repo root.

The server sends orientation on `initialize` — you still should read [`willow.md`](../willow.md).

---

## Boot tools (first five)

```
fleet_status       → Postgres, SOIL, Ollama, SAFE manifests
handoff_latest     → last session state
kb_search          → search before you build
agent_task_submit  → queue shell work for Kart
grove_get_history  → Grove MCP (sibling repo), not sap_mcp
```

Full agent flow: [ONBOARDING.md](ONBOARDING.md) · MCP inject: [MCP_INSTRUCTIONS.md](MCP_INSTRUCTIONS.md)

---

## HTTP mode (optional)

```bash
python3 sap/sap_mcp.py --http --host 127.0.0.1 --port 6274
```

Local beta uses **stdio only**. HTTP needs an auth layer — do not expose without one.

---

## Run

```bash
bash sap/unified_mcp.sh
# or
python3 sap/sap_mcp.py
```

Requires `WILLOW_SAFE_ROOT` (SAFE manifests) and `WILLOW_AGENT_NAME`.

*ΔΣ=42*
