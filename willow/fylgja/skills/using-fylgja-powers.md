---
name: using-fylgja-powers
description: Low-token skill router — registry like MCP tools/list; load one power body per need (Grove-style pull)
---

# Using Fylgja Powers

b17: FYLPR · ΔΣ=42

## Model

| Idea | Here |
|------|------|
| MCP `tools/list` | `willow/fylgja/powers/registry.json` — read **only** this until you need a body |
| MCP `tools/call` | `Read` **one** file: `willow/fylgja/powers/<file>` from the matched entry |
| Grove | Registry = channel index; power `.md` = message fetch on notify (your notify = task fit) |

## Rule

- **No** “invoke every skill at 1% probability.” Match task → **one** power; escalate only if the power says so.
- **Priority:** Sean’s explicit instructions → one loaded power → defaults.

## Willow fleet default

If the turn touches **Willow MCP, KB, Grove, or SOIL** and no narrower power clearly fits (`debug`, `tdd`, `plan`, …), load **`agent-rails`** — session discipline (parallel cold reads, external knowledge, write gates, coordination). See `powers/agent-rails.md`.

If Sean is spinning a **bounded initiative** that must not land on default branch until ratified merge, load **`overseer`** — worktree-first + evidence trail. See `powers/overseer.md`.

## Flow

1. Open `registry.json`; pick the single best `id` by `description`.
2. `Read` that entry’s `file` under `powers/`. Follow it; don’t load other powers unless the user or that file requires it.
3. Longer prose lives in `willow/fylgja/skills/*.md` — use only when you need detail **after** the power checklist.

## Optional

Post **ledger edits** to Grove `#architecture` / KB atoms — don’t paste fleet policy into session context.

## Surfaces (all)

See **`powers/SURFACES.md`** — Cursor rules, Cursor `/power`, Claude Code `/power` (repo + `~/.claude/commands`), `CLAUDE.md` (home + Grove + github root), `GEMINI.md`, `AGENTS.md`, Copilot note.
