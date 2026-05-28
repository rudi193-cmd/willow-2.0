@markdownai v1.0

# Fylgja powers — where it lives

b17: FYLSF · ΔΣ=42

Canonical tree: `willow/fylgja/` under **`${WILLOW_ROOT}`** (default `~/github/willow-2.0` or your clone).

Override: **`WILLOW_FYLGJA_ROOT`** must contain `powers/` and `skills/`.

| Surface | Path |
|--------|------|
| Registry | `willow/fylgja/powers/registry.json` |
| Power bodies | `willow/fylgja/powers/*.md` |
| Entry skill | `willow/fylgja/skills/power.md` |
| Fleet boot | [`willow.md`](../../willow.md) (repo root) |
| Personas | `willow/fylgja/personas/` |
| `AGENTS.md` / `GEMINI.md` | Repo root pointers |
| Cursor rule | `.cursor/rules/fylgja-powers.mdc` (not rewritten this pass) |
| Claude commands | `.claude/commands/` (not rewritten this pass) |

**MCP analogy:** `registry.json` = `tools/list`; each `powers/*.md` = one `tools/call` body.

**Grove analogy:** registry = channel index; power file = fetch one message when the task matches.

**Default power for Willow stack work:** `agent-rails`. **Bounded initiative off default branch:** `overseer`.

*ΔΣ=42*
