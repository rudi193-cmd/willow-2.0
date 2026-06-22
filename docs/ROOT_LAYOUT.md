# Repository root layout

b17: ROOTL · ΔΣ=42

The repo root is intentionally thin. Headers and seals: [`BRANDING.md`](BRANDING.md). Only install and dashboard entry points live here.

## Root (keep here)

| File | Purpose |
|------|---------|
| `willow.sh` | MCP launcher, `fleet_status`, `handoff_latest`, Grove serve |
| `willow.md` | Public boot contract tracked in this repo; private `~/.willow/willow.md` is an optional overlay |
| `root.py` | Idempotent install (Sleipnir) |
| `seed.py` | First-run / environment seed |
| `shoot.py` | Onboarding TUI |
| `app.py` | Grove Textual dashboard |
| `pyproject.toml` | Package metadata and dev tools |
| `README.md`, `LICENSE`, agent stubs | Human + agent entry docs |

## `core/` — runtime libraries

Postgres bridge, SOIL, Grove DB layer, fleet manager, kart worker:

- `core/pg_bridge.py`, `core/willow_store.py`
- `core/grove_db.py`, `core/grove_reader.py`, `core/grove_serve.py`, …
- `core/fleet.py`, `core/kart_worker.py`, `core/soil.py`

## `scripts/` — CLI utilities

One-off or operator tools (`ingest_seeds.py`, `session_close.py`, `orchestrator.py`, …). Run from repo root:

```bash
python3 scripts/session_close.py
```

## `benchmarks/` — benchmark and research atlas

Tracked benchmark artifacts plus repo-safe pointers to local continuations.
Each sidecar keeps its refresh script, machine-readable report, readable chart,
and any SQLite database required for continuation.

| File | Purpose |
| --- | --- |
| `benchmarks/README.md` | Human-facing atlas grouped by benchmark family |
| `benchmarks/catalog.json` | Machine-readable registry with visibility fields |
| `benchmarks/sidecars/` | Focused sidecar datasets (e.g. cartographer CBM prompt) |

Local-only benchmark harness (`$NEST/claude_benchmarks.db`, session reports)
is catalogued in `catalog.json` with `local_pointer` visibility — not copied
into the repo.

## `sap/` — MCP server

`sap/sap_mcp.py` via `sap/unified_mcp.sh` for daily IDE use. `sap/willow_mcp.sh`
remains the Willow-only launcher.

## `willow/` — hooks, Fylgja, routing, memory

Not to be confused with the repo name.

## `grove/` — dashboard apps package

Textual panes and MCP-local helpers (imports `core.grove_*`).

## Local-only (gitignored)

- `gaps.db` — local gap tracker SQLite
- `.mcp.json`, `.venv-dev/`, `.pytest_cache/`

*ΔΣ=42*
