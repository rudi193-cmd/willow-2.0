@markdownai v1.0

# RH Test Harness

Test whether Willow can distinguish canon from noise in Rendereason's APO/RH math corpus
without manual curation — and produce the same KB synthesis from both a clean (curated)
and dirty (raw dump) folder.

## What this tests

**Willow's discernment:** given data dumped in any order, does the system promote canon,
invalidate deprecated iterations, and arrive at a coherent KB on its own?

**Ground truth:** Rendereason's hand-curated clean folder. A passing dirty run converges
to the same top-results on all probe queries.

## Two runs

| Run ID | Folder | Description |
|--------|--------|-------------|
| `clean` | TBD — Rendereason curated | Hand-cleaned, no deprecated iterations |
| `dirty` | TBD — raw dump | Full folder including dead ends and noise |

## Steps

### 1. Dry-run manifest (no Willow required)

```bash
# Inspect what will be ingested — prints chunk manifest as JSON
python -m sandbox.rh_harness.ingest --folder /path/to/clean --run-id clean --dry-run
python -m sandbox.rh_harness.ingest --folder /path/to/dirty --run-id dirty --dry-run
```

### 2. Ingest

```bash
python -m sandbox.rh_harness.ingest --folder /path/to/clean --run-id clean
python -m sandbox.rh_harness.ingest --folder /path/to/dirty --run-id dirty
```

### 3. Compare

```bash
python -m sandbox.rh_harness.compare > results/comparison.md
```

## Probe queries

Five queries are run against both KB states:

1. **Canonical RH path** — should surface current proof strategy, not dead ends
2. **Weil conjecture status** — should surface current mapping state
3. **APO vocabulary** — should preserve custom terms, not flatten them
4. **Lean 4 verification** — machine-checked proof state
5. **Noise probe** — deprecated material should NOT rank high in dirty run

## Flags to watch (from Rendereason's known concerns)

- Noise amplification — bad iterations bleeding into top results
- Custom vocab flattening — APO terms merged with generic math vocabulary
- Long dependency chains — topics requiring prior context to be valid
- Deprecated non-canon surfacing alongside current canon

## Files

| File | Purpose |
|------|---------|
| `ingest.py` | Walk folder → chunk → call Willow `kb_ingest` |
| `willow_shim.py` | Thin CLI wrapper for Willow MCP tools |
| `compare.py` | Probe both runs, render side-by-side markdown table |
