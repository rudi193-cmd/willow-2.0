# Public Ready v1

b17: PUBRDY · ΔΣ=42

**Audience:** random GitHub clone · **Install:** Docker · **Hero moment:** *"It remembered."*

## Golden path

```bash
git clone https://github.com/rudi193-cmd/willow-2.0.git
cd willow-2.0
python willow-launcher.py
```

Within five minutes: browser opens → Concierge greeting → user asks a seeded question → Willow answers from local memory with an honest demo banner.

**Postgres:** the launcher reuses an existing local `willow_20` when reachable (Docker creds or peer auth). If not, it starts `willow-db` via Docker on port 5432, or **55432** when 5432 is already taken (common on developer machines with system Postgres).

## What v1 is

- Local-first memory demo in the browser (`core/public_serve.py`)
- Docker Postgres (`docker compose up -d willow-db`) — no bundled `pg_ctl`
- Retrieval-first chat: *"Here's what I have about that…"* (no Ollama required)
- Honest framing: **demo memory** until the user builds their own
- **Isolation:** public chat searches only `PUBDEMO*` seed atoms — never operator fleet memory, even when reusing an existing `willow_20` database

## What v1 is not

- Full fleet / IDE / MCP onboarding in the launcher (graduate path documented in Concierge copy)
- Bundled Postgres binaries (`postgres_mgr.py`) — deferred
- React/Gradio dashboard — static HTML only
- Rewriting `willow.md` as marketing (README + this doc carry the pitch)

## Components

| Piece | Role |
|-------|------|
| `willow-launcher.py` | Docker health → minimal setup → demo seed → `public_serve` → open browser |
| `core/public_demo.py` | Demo atom pack, first-run flag, retrieval reply formatter |
| `core/public_serve.py` | Loopback HTTP: `/` chat UI, `POST /api/chat` |
| `TRUST.md` | What leaves the machine (nothing by default) |
| `docker-compose.yml` | `willow-db` pgvector image (already shipped #490) |

## Hero test (pass/fail)

A stranger with Docker + Python 3.11+ runs the golden path and receives a memory-grounded answer to:

> What did we decide about the public launch tag?

Expected: cites seeded atom about `v1.0.0-public`.

## Security (shipped)

P0/P1 hardening merged 2026-06-23 (PR #490): `sap/security_middleware.py`, `core/safe_ops.py`, grove PG user fix.

## Deferred

- `core/postgres_mgr.py` / `willow/binaries/`
- `pglite` evaluation
- `requirements.lock` (Phase B — track in SECURITY_AUDIT R14)
- Academy wiki pillars
- sqlite in-memory demo mode

## Graduate path

After the demo: `bash setup.sh --public` → connect Cursor/Claude MCP → real atoms replace demo-only context.

See also: [`PUBLIC_REMOTE_BOOT.md`](PUBLIC_REMOTE_BOOT.md) · [`TRUST.md`](../TRUST.md)
