# IDE integration — SAP MCP

b17: IDEMCP · ΔΣ=42

Willow 2.0 runs MCP over **stdio** by default. HTTP is optional and needs auth if exposed.

---

## Canonical config (Cursor / Claude Code)

Copy [`.mcp.json.example`](../.mcp.json.example) → `.mcp.json`:

```json
{
  "mcpServers": {
    "markdownai": {
      "command": "bash",
      "args": ["sap/markdownai_mcp.sh"]
    },
    "willow": {
      "command": "bash",
      "args": ["sap/willow_mcp.sh"],
      "env": {
        "WILLOW_AGENT_NAME": "your_agent",
        "WILLOW_PG_DB": "willow_20"
      }
    },
    "grove": {
      "command": "bash",
      "args": ["sap/grove_mcp.sh"],
      "env": {
        "WILLOW_GROVE_ROOT": "/path/to/safe-app-willow-grove",
        "WILLOW_AGENT_NAME": "your_agent",
        "WILLOW_PG_DB": "willow_20"
      }
    }
  }
}
```

Agents read [`willow.md`](../willow.md) via MarkdownAI first.

Restart the IDE after changing MCP config or `sap/willow_mcp.sh`.

---

## HTTP mode (advanced)

```bash
python3 sap/sap_mcp.py --http --host 127.0.0.1 --port 6274
```

Default URL: `http://127.0.0.1:6274/mcp` (streamable HTTP — check `sap_mcp.py --help`).

**Beta boundary:** local stdio only. Do not expose HTTP to LAN/Internet without an auth layer.

### systemd (optional)

```bash
systemctl --user enable willow-mcp.service
systemctl --user start willow-mcp.service
```

---

## Grove MCP (separate)

Grove is a separate repo (`safe-app-willow-grove`). It provides fleet messaging tools (`grove_send_message`, `grove_inbox`, `grove_get_history`, etc.) — not KB or task tools.

**Prerequisites:**

1. Clone `safe-app-willow-grove` alongside this repo.
2. Set `WILLOW_GROVE_ROOT` to its path (or let `grove_mcp.sh` default to `~/github/safe-app-willow-grove`).

**Launcher:** `sap/grove_mcp.sh` — uses this repo's `.venv-dev` Python and sets `PYTHONPATH` automatically. No separate install needed if `.venv-dev` already has the grove package.

**Env vars:**

| Variable | Default | Notes |
|----------|---------|-------|
| `WILLOW_GROVE_ROOT` | `~/github/safe-app-willow-grove` | Path to grove repo |
| `WILLOW_AGENT_NAME` | `hanuman` | Sets sender identity |
| `WILLOW_PG_DB` | `willow_20` | Shared Postgres DB |

Restart the IDE after adding or changing the grove entry.

---

## Boot without IDE

```bash
./willow.sh fleet_status
./willow.sh handoff_latest
```

Same truth MCP uses — useful when debugging "tools don't see KB."

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Tools empty | `WILLOW_SAFE_ROOT`, manifests under `~/SAFE/Applications` |
| KB empty | Postgres `willow_20`, `fleet_status` |
| Wrong handoff | `WILLOW_AGENT_NAME` matches handoff author |
| Stale server | Restart after `sap_mcp.py` edits |

*ΔΣ=42*
