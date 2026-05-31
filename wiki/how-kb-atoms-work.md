# How KB atoms work

*Maintained synthesis · Willow 2.0 · 2026-05-31*

---

## What the KB is

`public.knowledge` in Postgres **`willow_20`** (SQLite on Termux).

The long-lived wall. Facts that must survive compression, restarts, and model swaps live here.

**Not** a session log. "Session started at 21:30" is noise. "Loki does not build — she audits" is an atom.

---

## Schema (core)

| Column | Role |
|--------|------|
| `id` | Stable id (e.g. hash prefix) |
| `title` | Short label |
| `summary` | The knowledge |
| `project` | Namespace (`hanuman`, `willow`, `sessions`, …) |
| `source_type` | `mcp`, `file`, `session`, `manual` |
| `category` | `general`, `code`, `decision`, … |
| `valid_at` / `invalid_at` | Bi-temporal — close, don't erase |
| `embedding` | `nomic-embed-text` when backfilled |
| `visit_count` | Retrieval weight |

---

## Domains (`project`)

| Domain | Holds |
|--------|--------|
| `hanuman` | Build patterns, session atoms |
| `willow` | Fleet-wide truth |
| `sessions` | Session RAG user messages |
| `docs` | Indexed markdown |
| `codebase` | Python signatures |
| `archived` | Stale — searchable, deprioritized |

---

## Write path

1. **`kb_search`** — always first  
2. **`kb_ingest`** — if new  
3. **`mem_check`** — gate may block duplicate/contradiction  

Force only when human says so.

CLI helpers exist; MCP is canonical.

---

## Search

- Keyword: title/summary ILIKE  
- Semantic: embedding neighbors when backfill complete  
- Temporal: `kb_at` — what was true at time T  

---

## Synthesis gap

RAG returns fragments. Wiki + handoffs compound. The KB holds atoms; something must still **integrate** them into decisions — that layer is human + agent discipline, not automatic yet.

*ΔΣ=42*
