@markdownai v1.0

# SOIL dual-layout diagnosis — 2026-06-12

- **Flag:** `flag-soil-dual-layout-divergence` (HIGH, raised 2026-06-10)
- **Author:** willow (Claude Code session 2026-06-12c, persona Hanuman) — diagnosis only, no data moved
- **Authorization:** Sean, 2026-06-12 ("soil green lit") — scope: dedicated diagnosis
- **Method:** `soil_stats` twin map · `core/willow_store.py` + `core/soil.py` read line-by-line · on-disk inspection of `~/github/.willow/store/` via Kart

## The two layouts

| | Layer A — MCP server | Layer B — dashboard/scripts |
|---|---|---|
| Module | `core/willow_store.py` (`WillowStore`) | `core/soil.py` |
| Path | `{store_root}/{collection}.db` | `{store_root}/{collection}/store.db` |
| Schema | `records(id, data, created, updated_at, deleted, deviation, action)` + optional `records_vec` (sqlite-vec, 768-dim) | `records(id, data, created_at, updated_at, deleted)` |
| Callers | All `soil_*` MCP tools (`sap/sap_mcp.py:118` imports `WillowStore`) | Dashboard + repo scripts (e.g. `migrate_flags.py`, session capture, steward pipelines) |
| Extras | Path-escape + symlink guards, deviation rubric, auto-flagging, vec search | WAL, thin wrapper, no guards |

Both store one JSON record per row in a table named `records`. The schemas differ only in `created` vs `created_at` (and `WillowStore._ensure_columns`/`_ts_cols` already tolerates `created_at`), plus Layer A's two extra defaulted columns.

## Key insight — the data is split-addressed, not unreachable

`WillowStore._db_path("X/store")` resolves to `{root}/X/store.db` — **exactly Layer B's file**. That is why `soil_stats` lists twins like `hanuman/atoms` (0) vs `hanuman/atoms/store` (144): the MCP layer can already read every Layer-B collection by appending `/store` to the name. Same root, same table name, compatible-enough schema. The divergence is a *naming* split, not a format split. (`stats()` rglobs `*.db`, which is why both appear.)

## Live data inventory (from soil_stats, 2026-06-12)

**Layer B (`X/store`) collections with data** — the session-capture and steward pipelines live here:

| Collection | Records |
|---|---|
| hanuman/turns/store | 678 |
| willow/turns/store | 355 |
| upstream_steward/pending/store | 153 |
| hanuman/atoms/store | 144 |
| hanuman/sessions/store | 121 |
| willow/atoms/store | 70 |
| willow/sessions/store | 53 |
| heimdallr/atoms+sessions/store | 23+23 |
| ~25 smaller (desk, dream, bkt, skill_steward/*, willow-dashboard/*, system/*) | 1–12 each |

**Layer A (`X.db`) collections with data** — the MCP-written state:

| Collection | Records |
|---|---|
| corpus/corrections | 756 |
| personal/candidates | 94 |
| contacts_professional (+edges) | 50+44 |
| willow/safety_log | 32 |
| hanuman/flags · willow/flags | 13 · 13 |
| hanuman/feedback, forks/*, stack, providers, grove/nodes, … | 1–10 each |

**True twins (same logical collection, data on both sides):**

| Twin | Layer A | Layer B |
|---|---|---|
| hanuman/flags | 13 | 1 |
| willow/atoms | 0 | 70 |
| hanuman/atoms | 0 | 144 |
| upstream_steward/digest | 0 | 1 |
| upstream_steward/log | 0 | 5 |
| corpus/corrections | 756 | `corrections/store.db` exists on disk (2026-05-25) but reports no records — likely an empty husk; confirm in dry-run |

The failure mode from the flag is confirmed and still live: `migrate_flags.py` (via `core.soil`) saw 0 records in `hanuman/flags` while MCP `soil_list` returned 12+ — each layer is blind to the other's file unless the `/store` suffix is used by hand.

## Recommendation

**Canonical layout: Layer A (`{collection}.db` / `WillowStore`).** It is the MCP path, has the guards (path-escape, symlink), the deviation rubric, auto-flagging, and vec search. Layer B is a strict feature-subset.

Migration plan (each step PR-gated, reversible):

1. **M1 — read-side shim (no data moves).** `core/soil.py` becomes a thin adapter over `WillowStore` (same public functions, `created_at` mapped to `created`). Every script/dashboard caller immediately sees Layer-A data. Layer-B files keep working via the existing `/store` addressing until M2.
2. **M2 — merge twins.** A `scripts/soil_merge_layouts.py` with `--dry-run` default: for each `X/store.db`, `INSERT OR IGNORE` its records into `X.db` (column map `created_at→created`; collision policy: newer `updated_at` wins, collisions logged). Then rename the source to `X/store.db.migrated-2026-06-12` (archive, never delete — per fleet rule).
3. **M3 — verify + gate.** Post-merge `soil_stats` must show no `*/store` twins outside `_archive/`. Add a check to `audit_verify.py` (or the weekly sweep) so the dual layout cannot silently return.
4. **M4 — cleanup.** After a soak week, move `.migrated-*` husks into `_archive/`.

Risk notes: the merge is additive (`INSERT OR IGNORE` + archive-not-delete), so the worst failure is the status quo. The one live writer on Layer B that must switch atomically with M1 is the session-capture pipeline (turns/sessions/atoms) — sequence M1's deploy with a stop-hook quiet window.

## Open questions for the operator

- Q-A: Approve Layer A as canonical (vs the reverse)?
- Q-B: M1+M2 in one session, or M1 first and soak?
- Q-C: Should `*/store` names be rejected by `soil_put` after M2 (hard rail), or warned?

*ΔΣ=42 — diagnosis only; nothing in the store has been changed.*
