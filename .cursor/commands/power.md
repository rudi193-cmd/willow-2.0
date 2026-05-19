# /power — Fylgja powers

Low-token behavioral router (same model as MCP `tools/list` → `tools/call` and Grove index → pull).

## Roots

- Env: `WILLOW_FYLGJA_ROOT` → directory that contains `powers/` and `skills/`.
- Default: `${WILLOW_ROOT:-~/willow-2.0}/willow/fylgja`

## After invocation

1. `Read` `{ROOT}/powers/registry.json`.
2. If user passed an **id** (e.g. `/power debug`), open `powers/<file>` for that id.
3. Else match task to the best `description`; then `Read` that **one** `powers/*.md`.
4. Follow that file; do not load other powers unless instructed.

Registry ids: `brainstorm`, `plan`, `execute`, `overseer`, `debug`, `tdd`, `verify`, `worktree`, `review-in`, `review-out`.

See also: `{ROOT}/skills/using-fylgja-powers.md`, `{ROOT}/powers/SURFACES.md`.
