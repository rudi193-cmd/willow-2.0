# IDE integration — Unified MCP

b17: IDEMCP · ΔΣ=42

Willow 2.0 runs MCP over **stdio** by default. A single server (`unified_mcp.sh`) exposes
willow, grove, and markdownai tools — no separate servers to configure.

---

## Canonical config (Cursor / Claude Code)

Copy [`.mcp.json.example`](../.mcp.json.example) → `.mcp.json`:

```json
{
  "mcpServers": {
    "willow": {
      "command": "bash",
      "args": ["/path/to/willow-2.0/sap/unified_mcp.sh"],
      "env": {
        "WILLOW_AGENT_NAME": "your_agent",
        "WILLOW_GROVE_ROOT": "/path/to/safe-app-willow-grove",
        "WILLOW_PG_DB": "willow_20"
      }
    }
  }
}
```

Agents read [`willow.md`](../willow.md) via `mai_read_file` first.

Restart the IDE after changing MCP config or `sap/unified_mcp.sh`.

---

## Tool namespaces

| Prefix | Domain | Count |
|--------|--------|-------|
| `kb_` `soil_` `fleet_` `agent_` `fork_` `skill_` `mem_` `index_` `ledger_` `handoff_` `soul_` `nest_` `infer_` `task_` | Willow — KB, tasks, fleet, handoff | ~77 |
| `grove_` | Messaging — channels, bus, inbox, flags | 17 |
| `mai_` | MarkdownAI — render, phases, macros, directives | 9 |

---

## Env vars

| Variable | Default | Notes |
|----------|---------|-------|
| `WILLOW_AGENT_NAME` | `agent` | Sets identity for handoff + grove |
| `WILLOW_GROVE_ROOT` | `~/github/safe-app-willow-grove` | Path to grove repo |
| `WILLOW_PG_DB` | `willow_20` | Postgres database name |
| `WILLOW_STORE_ROOT` | `~/.willow/store` | SOIL store path |

---

## HTTP mode (advanced)

```bash
python3 sap/unified_mcp.py --http --host 127.0.0.1 --port 6274
```

**Beta boundary:** local stdio only. Do not expose HTTP to LAN/Internet without an auth layer.

### systemd (optional)

```bash
systemctl --user enable willow-mcp.service
systemctl --user start willow-mcp.service
```

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
| Grove tools error | `WILLOW_GROVE_ROOT` points to grove repo; grove package importable |
| mai_ tools error | File path correct; `@markdownai` header present |
| Stale server | Restart after `sap/unified_mcp.py` edits |

*ΔΣ=42*
