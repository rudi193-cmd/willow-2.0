# Fylgja-powers — where it is wired

b17: FYLSF · ΔΣ=42

Canonical tree: `willow/fylgja/` inside the **willow-1.9** checkout (`~/github/willow-1.9`).

Override path: env **`WILLOW_FYLGJA_ROOT`** → must contain `powers/` and `skills/`.

| Surface | Path |
|--------|------|
| **Powers registry** | `willow/fylgja/powers/registry.json` |
| **Power bodies** | `willow/fylgja/powers/*.md` (Willow MCP/KB/Grove/SOIL discipline → `agent-rails.md`) |
| **Entry skill (Claude Code plugin)** | `willow/fylgja/skills/using-fylgja-powers.md` |
| **Cursor rule (willow-1.9)** | `willow-1.9/.cursor/rules/fylgja-powers.mdc` |
| **Cursor rule (Grove app)** | `safe-app-willow-grove/.cursor/rules/fylgja-powers.mdc` |
| **Cursor command `/power`** | `.cursor/commands/power.md` in both repos above |
| **Cursor command `/overseer`** | `willow-1.9/.cursor/commands/overseer.md` — pinned **overseer** power (scoped initiative) |
| **Claude Code `/power`** | `.claude/commands/power.md` in both repos + `~/.claude/commands/power.md` |
| **Hanuman home identity** | `~/CLAUDE.md` — Skill Mandate points here |
| **Fleet root (Loki)** | `~/github/CLAUDE.md` — pointer for builders |
| **Heimdallr (Grove repo)** | `safe-app-willow-grove/CLAUDE.md` |
| **Gemini CLI (willow-1.9 root)** | `willow-1.9/GEMINI.md` |
| **Gemini CLI (Grove repo)** | `safe-app-willow-grove/GEMINI.md` |
| **AGENTS.md (Cursor / OpenAI Codex–style)** | `willow-1.9/AGENTS.md`, `safe-app-willow-grove/AGENTS.md` |
| **User-wide Cursor (optional)** | Copy `.cursor/rules/fylgja-powers.mdc` to `~/.cursor/rules/` if you want the router outside these repos |

**GitHub Copilot (VS Code):** point custom instructions at the same rule text as `.cursor/rules/fylgja-powers.mdc`, or paste the one-line summary: *Read `powers/registry.json`, then exactly one `powers/*.md`.*

**MCP analogy:** `registry.json` = `tools/list`; each `powers/*.md` = `tools/call` payload execution.

**Grove analogy:** registry = channel index; power file = fetch one message on demand.
