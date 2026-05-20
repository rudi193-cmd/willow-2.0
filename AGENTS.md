# Agent instructions (Cursor, Codex, compatible CLIs)

b17: AGNTW · ΔΣ=42

**Fleet boot:** Read [`willow.md`](willow.md) first. Then `fleet_status`, `handoff_latest`, Grove history, `kb_search`. Shell fallback: `./willow.sh fleet_status`.

**Fylgja-powers:** Read `willow/fylgja/powers/registry.json`, then **one** `willow/fylgja/powers/*.md` chosen by task fit (or user id). Entry: `willow/fylgja/skills/using-fylgja-powers.md`. Index: `willow/fylgja/powers/SURFACES.md`. **Willow stack sessions (MCP/KB/Grove/SOIL)** with no narrower power → **`agent-rails`** (`powers/agent-rails.md`).

Env: `WILLOW_FYLGJA_ROOT` overrides the `willow/fylgja` directory.

Do not load bulk skill packs when a single power id matches.

**Worktree seed:** At worktree creation, before the first code edit, ingest one KB seed atom — the non-derivable contract (wire format, interface, or invariant) a cold agent needs that cannot be read from the code. Record the atom ID in the first Grove post for the task. No build starts without it.

**Branding:** New docs and modules follow [`docs/BRANDING.md`](docs/BRANDING.md) (`b17: … · ΔΣ=42`; SAP uses `b20: SAPMCP2`).
