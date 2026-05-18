# Gemini CLI — Willow 1.9

b17: GEMW1 · ΔΣ=42

## Fylgja powers (default behavioral router)

1. Read `willow/fylgja/powers/registry.json` (under this repo).
2. Pick one `powers[].id` by `description` (or user-supplied id).
3. Read exactly one `willow/fylgja/powers/<file>`. Follow it.

Entry doc: `willow/fylgja/skills/using-fylgja-powers.md` · Surface index: `willow/fylgja/powers/SURFACES.md`

Env override: `WILLOW_FYLGJA_ROOT` → directory containing `powers/` and `skills/`.

User instructions always win over this router.
