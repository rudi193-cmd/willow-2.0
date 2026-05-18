# Runbook — Postgres (Willow + Grove)

**b17:** RBPGW · ΔΣ=42  

See **shared** notes in `safe-app-willow-grove/docs/runbooks/postgres.md`. This file adds **Willow-specific** checks.

## Knowledge / task health

```sql
SET search_path = public;
SELECT status, COUNT(*) FROM tasks GROUP BY 1;
SELECT COUNT(*) AS knowledge_atoms FROM knowledge WHERE invalid_at IS NULL;
```

## Receipts

- `core/pg_bridge.py` — expected tables
