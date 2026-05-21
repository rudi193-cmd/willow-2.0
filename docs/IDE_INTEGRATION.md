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
        "WILLOW_PG_DB": "willow_20",
        "WILLOW_SAFE_ROOT": "/path/to/SAFE/Applications",
        "WILLOW_AGENTS_ROOT": "/path/to/SAFE/Agents"
      }
    }
  }
}
```

**Cursor:** symlink or copy MCP config into the project:

```bash
ln -sf ../.willow/mcp.json .cursor/mcp.json   # per-machine agent in ~/.willow/mcp.json
python3 -m willow.fylgja.install_cursor       # Fylgja hooks → .cursor/hooks.json
```

Use an **absolute** path in `args` — Cursor may not launch MCP from the repo root.

**Claude Code:** repo `.mcp.json` + `python3 -m willow.fylgja.install` (writes `~/.claude/settings.json` hooks).

Agents read [`willow.md`](../willow.md) via `mai_read_file` first.

Restart the IDE after changing MCP config, hooks, or `sap/unified_mcp.sh`.

---

## Cursor hooks (Fylgja parity)

| Cursor event | Fylgja module | Purpose |
|--------------|---------------|---------|
| `sessionStart` | `session_start` | Anchor, handoff boundary, hardware, postgres probe |
| `beforeSubmitPrompt` | `prompt_submit` | Turn log, dispatch inbox, build-continue |
| `beforeShellExecution` | `pre_tool` | Bash safety + canon guards |
| `beforeMCPExecution` | `pre_tool` | MCP write-path guards |
| `stop` | `stop` | Session composite, affect tagging |

Install: `python3 -m willow.fylgja.install_cursor` (writes `.cursor/hooks.json` — gitignored, machine-local).  
Adapter: `tools/run_cursor_hook.py` (translates Cursor JSON ↔ Claude hook output).

Debug: Cursor **Output → Hooks** channel.

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
| `WILLOW_GROVE_ROOT` | `~/github/safe-app-willow-grove` | Path to grove repo (grove tools bundled in unified MCP) |
| `WILLOW_PG_DB` | `willow_20` | Postgres database name |
| `WILLOW_SAFE_ROOT` | `~/SAFE/Applications` | Installed app manifests — required for SAP gate |
| `WILLOW_AGENTS_ROOT` | `~/SAFE/Agents` | Agent manifests — required for agent authorization |
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
