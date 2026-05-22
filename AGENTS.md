# Agent instructions (Cursor, Codex, compatible CLIs)

b17: AGNTW · ΔΣ=42

**Fleet boot:** Read [`willow.md`](willow.md) first. Then `fleet_status`, `handoff_latest`, Grove history, `kb_search`. Shell fallback: `./willow.sh fleet_status`.

**Cursor:** `python3 -m willow.fylgja.install_cursor` wires Fylgja hooks to `.cursor/hooks.json`. MCP: `.cursor/mcp.json` → `.willow/mcp.json` (per-machine agent). Use agent name as MCP `app_id`, not `willow-2.0`.

**Claude Code:** `python3 -m willow.fylgja.install` wires hooks to `~/.claude/settings.json`.

**Fylgja-powers:** Read `willow/fylgja/powers/registry.json`, then **one** `willow/fylgja/powers/*.md` chosen by task fit (or user id). Entry: `willow/fylgja/skills/using-fylgja-powers.md`. Index: `willow/fylgja/powers/SURFACES.md`. **Willow stack sessions (MCP/KB/Grove/SOIL)** with no narrower power → **`agent-rails`** (`powers/agent-rails.md`).

Env: `WILLOW_FYLGJA_ROOT` overrides the `willow/fylgja` directory.

Do not load bulk skill packs when a single power id matches.

**Worktree seed:** At worktree creation, before the first code edit, ingest one KB seed atom — the non-derivable contract (wire format, interface, or invariant) a cold agent needs that cannot be read from the code. Record the atom ID in the first Grove post for the task. No build starts without it.

***Default 7-step boot path:***
Run at the beginning of every session, no matter the users first prompt. The only exceptions are if: the user appears in a state of a emergency, or, if user explicitly states not to run startup. 

1. Read `willow.md` via `markdownai-read_file`.
2. Establish local operating context: agent, namespace, repo root, branch, and a compact repo diff summary.
3. Call `fleet_status(app_id=<your-agent-id>)` — agent ID is your own name (e.g. `hanuman`), not `"willow"`.
4. Call `handoff_latest(app_id=<your-agent-id>, agent=<your-agent-id>)`.
5. Call `grove_get_history` for the agent channel/inbox.
6. Call `kb_search` on the current task/topic.
7. If any required base is degraded, surface it and stop; otherwise proceed to act.

If `fleet_status` returns degraded: surface it and stop.

**safe-app-willow-grove Branding:** New docs and modules follow [`docs/BRANDING.md`](docs/BRANDING.md) (`b17: … · ΔΣ=42`; SAP uses `b20: SAPMCP2`).
