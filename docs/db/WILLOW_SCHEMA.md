# Willow / public schema reference

**b17:** WILSC · ΔΣ=42  

**Authoritative source:** `core/pg_bridge.py` (`_SCHEMA` + `_MIGRATIONS` + `_INDEXES`). This document summarizes **operator-relevant** tables; drift should be fixed in code first, then this file.

> **Note:** `safe-app-willow-grove/schema.sql` includes a **stub** `willow.routing_decisions` for standalone installs. The **rich** `routing_decisions` / `knowledge` shapes are created by **`pg_bridge`** in a full Willow install. Prefer introspection on your live DB when in doubt.

## `public.knowledge` (KB)

| Column | Type | Purpose |
|--------|------|---------|
| `id` | TEXT PK | Atom id |
| `project` | TEXT | Domain / namespace |
| `valid_at` / `invalid_at` | TIMESTAMPTZ | Temporal validity |
| `summary` / `title` | TEXT | Human-facing |
| `content` | JSONB | Structured metadata |
| `weight`, `visit_count` | | Ranking signals |
| `embedding` | VECTOR(768) | If extension present |

## `public.tasks` (Kart queue)

| Column | Notes |
|--------|--------|
| `id` | TEXT PK in pg_bridge |
| `status` | pending / running / complete / … |
| `result` | JSONB |

(Standalone `schema.sql` may use BIGINT id — **converge on one bootstrap path** for production.)

## `public.routing_decisions`

Willow records model routing audibility (`prompt_hash`, `decision` JSONB, `session_id`, …).

## How to verify

```sql
SET search_path = public;
\d knowledge
SELECT COUNT(*) FROM tasks WHERE status IN ('pending','running');
SELECT id, created_at FROM routing_decisions ORDER BY created_at DESC LIMIT 20;
```

## Receipts

- `core/pg_bridge.py` — DDL
- `wiki/how-kb-atoms-work.md` — KB semantics
