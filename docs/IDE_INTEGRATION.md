# IDE integration — Unified MCP

b17: IDEMCP · ΔΣ=42

Willow 2.0 runs MCP over **stdio** by default. A single server (`unified_mcp.sh`) exposes
willow, grove, and markdownai tools — no separate servers to configure.

---

## Fast Path

Install exactly the surface you use:

```bash
./willow.sh agents active <agent>
./willow.sh agents install <agent> --ide <cursor|claude|codex>
./willow.sh agents check --ide <cursor|claude|codex>
```

Restart the IDE after install. Agents should read [`willow.md`](../willow.md)
first, then check fleet health and handoff.

## Manual Config (Cursor / Claude Code)

Prefer the fast path above. Use manual config only when an IDE cannot consume the
generated files. Copy [`.mcp.json.example`](../.mcp.json.example) → `.mcp.json`:

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

**Cursor:** install via `./willow.sh agents install <agent> --ide cursor`. Committed
`.cursor/hooks.json`, `.cursor/mcp.json`, commands, and skills are real files for
remote agents; local install only symlinks ignored `settings.local.json`.
**Claude Code:** committed `.claude/settings.json` plus global hooks via
`python3 -m willow.fylgja.install` when `--ide claude` includes global wiring.

Use an **absolute** path in unified MCP `args` when the IDE does not launch from repo root (template uses `{{REPO_ROOT}}`).

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

`PostToolUse` (`post_tool`) is wired for **Claude Code** global hooks only. Cursor's
hook schema in this repo does not expose an equivalent post-tool event, so output
scanning runs on Claude sessions via `install_project --ide claude`.

Install: `./willow.sh agents install <agent> --ide cursor` — syncs committed
`.cursor/hooks.json` from canonical templates and symlinks only ignored
`.cursor/settings.local.json` into `$WILLOW_HOME/agents/<agent>/`.  
Runner: `willow/fylgja/bin/fylgja-hook` → `willow.fylgja.hook_runner` (legacy shims: `tools/run_cursor_hook.py`).

Debug: Cursor **Output → Hooks** channel.

---

## Remote Agents

Remote agents start from a clean git checkout. They do not have the operator's
private `~/github/.willow`, and symlinked discovery paths are not reliable. Any
surface a remote agent should discover must be committed as real files.

Tracked remote-safe surface:

| Surface | Path |
|---------|------|
| Cursor hooks | `.cursor/hooks.json` |
| Cursor permissions | `.cursor/permissions.json` |
| Cursor commands / skills / subagents | `.cursor/commands/`, `.cursor/skills/<skill>/SKILL.md`, `.cursor/agents/` |
| Claude commands / skills / agents | `.claude/commands/`, `.claude/skills/<skill>/SKILL.md`, `.claude/agents/` |
| Generic agent commands / skills / agents | `.agents/commands/`, `.agents/skills/<skill>/SKILL.md`, `.agents/agents/` |
| Codex commands / skills / agents | `.codex/commands/`, `.codex/skills/<skill>/SKILL.md`, `.codex/agents/` |

After editing canonical Fylgja skills, commands, or hook templates, refresh the
vendored remote surface:

```bash
python3 scripts/sync_remote_cursor_surface.py
pytest tests/test_fylgja/test_remote_surface.py
```

Local private config still belongs in `~/github/.willow`; it is runtime state,
not remote discovery state.

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
| `WILLOW_HOME` | private `~/github/.willow` or public `.willow/generated` | Fleet home selected by `link_fleet_home`; `~/.willow` alias OK on operator machines |
| `WILLOW_AGENT_NAME` | `active-agent` or `hanuman` | Identity for handoff, Grove, MCP `app_id` |
| `GROVE_SENDER` / `GROVE_NAME` | same as agent | Set by `install_project` / `unified_mcp.sh` |
| `WILLOW_GROVE_ROOT` | `~/github/safe-app-willow-grove` | Grove repo (tools bundled in unified MCP) |
| `WILLOW_PG_DB` | `willow_20` | Postgres database name |
| `WILLOW_SAFE_ROOT` | `~/github/SAFE/Applications` | Installed app manifests — required for SAP gate |
| `WILLOW_AGENTS_ROOT` | `~/github/SAFE/Agents` | Agent manifests — required for agent authorization |
| `WILLOW_STORE_ROOT` | `$WILLOW_HOME/store` | SOIL store path |
| `WILLOW_MCP_PROFILE` | `standard` | Tool picker filter: `minimal` \| `core` \| `standard` \| `full` |
| `WILLOW_TRUE_HOTRELOAD` | *(unset)* | Operator opt-in: set to `1` for generation-swap reload (`fleet_reload` `target="code"` or chained from `target="all"`). Local `.cursor/mcp.json` only unless fleet opts in publicly (ADR-20260704). |

Path resolver: `willow/fylgja/willow_home.py` (`fleet_home`, `resolve_store_root`, …).

---

## After code merge (MCP hot reload)

1. `fleet_reload(target="all")` — whitelist modules + Kart bounce.
2. If `code_version.stale` is still true and you have `WILLOW_TRUE_HOTRELOAD=1` locally,
   step 1 auto-chains generation-swap; or call `fleet_reload(target="code")` explicitly.
3. If still stale or reload errors: `fleet_restart` then reconnect MCP:
   - **Claude Code:** `/mcp`
   - **Cursor:** Settings → MCP → toggle willow off/on

See `/restart-server` and [`runbooks/mcp.md`](runbooks/mcp.md).

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
| Stale server | `fleet_reload(target="all")`; with local `WILLOW_TRUE_HOTRELOAD=1`, chains generation-swap; else `fleet_restart` + MCP reconnect |

*ΔΣ=42*
