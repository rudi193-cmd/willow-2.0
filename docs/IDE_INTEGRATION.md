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

**Cursor:** symlink MCP via install — canonical templates live under `willow/fylgja/config/`:

```bash
python3 -m willow.fylgja.install_project hanuman --ide all
# or cursor-only:
python3 -m willow.fylgja.install_project hanuman --ide cursor
```

Use an **absolute** path in unified MCP `args` when the IDE does not launch from repo root (template uses `{{REPO_ROOT}}`).

**Claude Code:** `install_project` symlinks `.claude/settings.json` and wires global hooks via `python3 -m willow.fylgja.install`.

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

Install: `python3 -m willow.fylgja.install_project <agent> --ide cursor` (symlinks `.cursor/hooks.json` → `willow/fylgja/config/cursor-hooks.json`).  
Runner: `willow/fylgja/bin/fylgja-hook` → `willow.fylgja.hook_runner` (legacy shims: `tools/run_cursor_hook.py`).

Debug: Cursor **Output → Hooks** channel.

---

## Tool namespaces

~160 tools are registered; the IDE should not show all of them.

**Profiles** (`WILLOW_MCP_PROFILE`, default `standard`): see [`MCP_TOOL_PROFILES.md`](MCP_TOOL_PROFILES.md).

| Profile | ~Visible | Purpose |
|---------|----------|---------|
| `minimal` | 10 | Boot |
| `core` | 38 | Daily |
| `standard` | 73 | Default |
| `full` | 160 | Everything |

Call **`fleet_tool_guide`** when unsure which tool to use (grouped catalog).

| Prefix | Domain |
|--------|--------|
| `kb_` `soil_` `fleet_` `handoff_` `ledger_` | Data lane |
| `agent_task_submit` `kart_task_run` | Exec lane (Kart) |
| `grove_` | Messaging |
| `mai_` | MarkdownAI |

---

## Env vars

| Variable | Default | Notes |
|----------|---------|-------|
| `WILLOW_HOME` | `~/github/.willow` | Canonical fleet config (`~/.willow` alias OK) |
| `WILLOW_AGENT_NAME` | `active-agent` or `hanuman` | Identity for handoff, Grove, MCP `app_id` |
| `GROVE_SENDER` / `GROVE_NAME` | same as agent | Set by `install_project` / `unified_mcp.sh` |
| `WILLOW_GROVE_ROOT` | `~/github/safe-app-willow-grove` | Grove repo (tools bundled in unified MCP) |
| `WILLOW_PG_DB` | `willow_20` | Postgres database name |
| `WILLOW_SAFE_ROOT` | `~/github/SAFE/Applications` | Installed app manifests — required for SAP gate |
| `WILLOW_AGENTS_ROOT` | `~/github/SAFE/Agents` | Agent manifests — required for agent authorization |
| `WILLOW_STORE_ROOT` | `$WILLOW_HOME/store` | SOIL store path |
| `WILLOW_MCP_PROFILE` | `standard` | Tool picker filter: `minimal` \| `core` \| `standard` \| `full` |

Path resolver: `willow/fylgja/willow_home.py` (`fleet_home`, `resolve_store_root`, …).

---

## Runtime parity (install + hooks)

| Surface | Install | Check |
|---------|---------|-------|
| Cursor | `./willow.sh agents install <id> --ide cursor` | `./willow.sh agents check --ide cursor` |
| Claude Code | `./willow.sh agents install <id> --ide claude` | `./willow.sh agents check --ide claude` |
| Codex CLI | `./willow.sh agents install <id> --ide codex` | `./willow.sh agents check --ide codex` |
| Gemini CLI | Manual MCP fragment (see `GEMINI.md`) | — |

Use `--ide <surface>` for the runtime you actually use. `--ide all` is **strict**: every IDE surface must be installed — it fails on Cursor-only machines missing Claude/Codex globals.

`install_project` re-renders MCP JSON (including `GROVE_SENDER` / `GROVE_NAME`) and exports
`$WILLOW_HOME/mcp/willow-2.0.mcp.json` on every install.

Layout audit: `bash scripts/audit_canonical_home.sh`

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
