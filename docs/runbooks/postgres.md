# Runbook — Postgres (Willow)

b17: RBPGW · ΔΣ=42

Shared notes also live in `safe-app-willow-grove/docs/runbooks/postgres.md` when that repo is checked out beside this one.

**Willow 2.0 default database:** `willow_20` (not `willow_19`).

---

## Quick health

```bash
./willow.sh fleet_status
pg_isready
psql -d willow_20 -c 'SELECT 1'
```

```sql
SET search_path = public;
SELECT COUNT(*) AS live_atoms FROM knowledge WHERE invalid_at IS NULL;
SELECT status, COUNT(*) FROM tasks GROUP BY 1;
```

---

## When MCP says KB is empty

1. Confirm env: `echo $WILLOW_PG_DB` → `willow_20`  
2. `./willow.sh fleet_status` — is `postgres` a dict, not `not_connected`?  
3. Check `~/.willow/pg_failure.flag` for the last init error  
4. `psql -d willow_20 -c 'SELECT count(*) FROM knowledge WHERE invalid_at IS NULL'`

If Postgres is up but counts are low, the KB may simply be empty on a fresh install — run `seed.py` or ingest atoms.

Historical silent-fail incident (fixed 2026-04-22): [`../../archive/docs/gaps/GAP-001-postgres-bridge-broken.md`](../../archive/docs/gaps/GAP-001-postgres-bridge-broken.md)

---

## Code

- `core/pg_bridge.py` — KB bridge  
- `core/bridge_factory.py` — connect selection  

*ΔΣ=42*
