# Archive

**Not the install path.** Active docs live at repo root and in `docs/` + `wiki/`.

This tree holds legacy, historical, and superseded material — preserved, not curated for beta defaults.

## What Lives Here

- `docs/`: historical architecture, technical spec, reports, gap postmortems (`docs/gaps/`), and prior design/spec work
- `legacy/`: retired implementation surfaces kept for compatibility archaeology
- `scripts/`: one-off migration helpers and old schema movers
- `apps/`: archived app/session artifacts

## Index

The SQLite catalog for this directory is `archive/archive_index.db`.

It is meant to answer simple questions like:

```sql
SELECT path, bucket, kind
FROM archived_files
ORDER BY path;
```

```sql
SELECT bucket, COUNT(*)
FROM archived_files
GROUP BY bucket
ORDER BY bucket;
```

## Intent

Files in `archive/` are preserved, not curated for current defaults. Historical
references to `willow-1.9`, old worktree names, machine-specific paths, and
superseded install flows are acceptable here as part of the record.
