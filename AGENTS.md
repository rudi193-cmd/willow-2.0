# Agent instructions (Cursor, Codex, compatible CLIs)

b17: AGNTW · ΔΣ=42

**Contract:** [`willow.md`](willow.md) — read first. **Boot:** [`willow/fylgja/skills/boot.md`](willow/fylgja/skills/boot.md) (`/boot`).

| Need | Doc |
|------|-----|
| Doc map (humans + agents) | [`docs/INDEX.md`](docs/INDEX.md) |
| Public contract snapshot | [`docs/CONTRACT.md`](docs/CONTRACT.md) |
| MCP tools (annotated registry) | [`sap/mcp_registry.json`](sap/mcp_registry.json) |
| MCP onboarding (thin) | [`sap/ONBOARDING.md`](sap/ONBOARDING.md) |
| Agent identity / IDE wiring | [`docs/AGENT_IDENTITY.md`](docs/AGENT_IDENTITY.md) |
| Powers router | [`willow/fylgja/powers/registry.json`](willow/fylgja/powers/registry.json) |
| Open backlog (not blockers) | [`docs/OPEN_WORK.md`](docs/OPEN_WORK.md) |

**IDE:** `./willow agents active <id>` then `./willow agents install <id> --ide all` · check: `./willow agents check`

**Claude Code hooks:** `python3 -m willow.fylgja.install`

Do not duplicate boot steps or tool tables here — they drift. Change `willow.md` or `boot.md` instead.

*ΔΣ=42*
