# Canonical Architecture Reference — Willow (willow-1.9)

**b17:** CARW1 · ΔΣ=42  

This **CAR** covers the **Willow system layer** in this repo: Postgres public schema (KB, tasks, routing, dispatch), core bridges, and how they complement **Grove** in `safe-app-willow-grove`.

## Scope

**In scope:** `pg_bridge` schema, knowledge/task models, routing decisions, scripts that index markdown into `public.knowledge`, coordination with Ollama/SOIL as described in `TECHNICAL_SPEC.md`.

**Out of scope:** `grove.messages` row-level contracts — see **Grove repo** [`docs/contracts/MESSAGE_ENVELOPE.md`](../../safe-app-willow-grove/docs/contracts/MESSAGE_ENVELOPE.md) and [`docs/db/GROVE_SCHEMA.md`](../../safe-app-willow-grove/docs/db/GROVE_SCHEMA.md).

## Cross-repo bridge

Read [`safe-app-willow-grove/docs/CROSS_REPO_BRIDGE.md`](../../safe-app-willow-grove/docs/CROSS_REPO_BRIDGE.md) for the single-DB `willow_20` split of responsibilities.

## Receipts

| Source | Role |
|--------|------|
| `core/pg_bridge.py` | Authoritative `CREATE TABLE` for `public.knowledge`, `tasks`, `routing_decisions`, etc. |
| `docs/TECHNICAL_SPEC.md` | Long-form Willow architecture |

## How to verify (knowledge)

```sql
SET search_path = public;
SELECT COUNT(*) FROM knowledge;
SELECT id, project, left(coalesce(summary,''), 60) AS s FROM knowledge ORDER BY created_at DESC LIMIT 5;
```

## Related

- DB reference: [`db/WILLOW_SCHEMA.md`](db/WILLOW_SCHEMA.md)
- ADR index: [`adrs/README.md`](adrs/README.md)
