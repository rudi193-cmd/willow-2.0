---
b17: CD192 · ΔΣ=42
title: Code diff — willow-1.9 → willow-2.0
date: 2026-05-19
method: shallow clone `rudi193-cmd/willow-1.9` vs local `willow-2.0` (`diff -rq`, file-level + spot checks on critical paths)
---

# Code diff — 1.9 → 2.0

This is the code truth. Docs should follow this, not the other way around.

Compared: `github.com/rudi193-cmd/willow-1.9` (master) against `willow-2.0` (working tree). ~265 path-level differences. ~444 files in 1.9, ~575 in 2.0 (excluding `.git`, caches, local DB artifacts).

---

## Version and naming

| Item | 1.9 | 2.0 |
|------|-----|-----|
| `VERSION` | `1.9.0` | `2.0.0` |
| Default Postgres DB | `willow_19` | `willow_20` |
| Repo / clone path | `willow-1.9` | `willow-2.0` |
| Grove sibling (docs/examples) | `safe-app-grove` | `safe-app-willow-grove` |
| Launcher banner | `Willow 1.9` | `Willow 2.0` |

**Doc impact:** Every install guide, MCP example, and env default that still says `willow-1.9` or `willow_19` is wrong for beta.

---

## What 2.0 adds (new paths)

| Path | Role |
|------|------|
| `willow.md` | Runtime-agnostic fleet boot contract (agents read before MCP) |
| `pyproject.toml` | Packaging + dev deps (`pytest`, `ruff`, `mypy`) |
| `sap/willow_mcp.sh` | Stdio MCP launcher (sets `WILLOW_ROOT`, `WILLOW_PG_DB`, venv python) |
| `sap/markdownai_mcp.sh` + `markdownai_server.mjs` | MarkdownAI MCP server |
| `.mcp.json` | Checked-in MCP config (willow + markdownai) |
| `sap/handoff_index.py` | Semantic sort for `handoff_latest` (date suffix in filename) |
| `scripts/orchestrator.py` | One-shot session summary injector (`~/.willow/willow-2.0.db`) |
| `scripts/session_close.py` | Session seal / DB row for orchestrator |
| `scripts/ingest_seeds.py`, `scripts/init_db.py` | KB / DB bootstrap helpers |
| `scripts/persona.py` | Persona profile loader |
| `apps/` | Example apps (e.g. smart-home Textual app) |
| `archive/` | Legacy code + moved specs (`sap_mcp_v1`, migrations, old `docs/ARCHITECTURE.md`) |
| `store/` | Local store tree (runtime data layout) |
| `willow/hooks/completion_hook.py` | Renamed from `test_completion.py` (avoids pytest collecting hook as tests) |
| `tests/test_handoff_index.py` | Handoff index tests |
| `willow/fylgja/skills/persistent-memory-stack.md` | Three-layer memory contract for agents |
| `docs/BETA_AUDIT_REPORT.md` | Beta gate checklist |
| `.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md` | GitHub templates |

---

## What 2.0 removes or relocates

| 1.9 only | Notes |
|----------|--------|
| `docs/ARCHITECTURE.md`, `docs/TECHNICAL_SPEC.md` | Not in 2.0 `docs/` root — live under `archive/docs/` in 2.0 |
| `docs/machine-path-audit.md`, `docs/reports/*` | Archived or dropped from active docs |
| `archive/docs/superpowers/specs/*` (many May 2026 specs) | Moved to `archive/archive/docs/superpowers/specs/` |
| `sap/sap_mcp_v1.py` | Legacy; 2.0 uses `sap/sap_mcp.py` only (v1 in `archive/legacy/sap/`) |
| `scripts/migr1_willow17_to_19.py`, `migr2_sap_schema.py`, `migrate_willow_legacy.py` | Migration scripts archived |
| `core/sean_db.py` | Removed |
| `tools/drop_server.py`, `nest_watcher*`, `grove_monitor_heimdallr.py`, `xfer.sh` | Not carried into 2.0 tree |
| `willow/fylgja/loki.py` | Not in 2.0 |
| `willow/hooks/test_completion.py` | Renamed to `completion_hook.py` |

**Doc impact:** `docs/INDEX.md` links to `TECHNICAL_SPEC.md` and `ARCHITECTURE.md` at repo root — those paths are broken in 2.0 unless restored or retargeted to `archive/docs/`.

---

## Critical file deltas (line counts)

| File | Δ (approx) | What changed |
|------|------------|--------------|
| `willow.sh` | +133 / −22 | `fleet_status`, `handoff_latest` without MCP; default `willow_20`; boot helpers |
| `seed.py` | +57 / −18 | `2.0.0`, `willow_20`, `WILLOW_GROVE_DIR`, optional **Grove network URL** at install |
| `sap/sap_mcp.py` | +30 / −23 | Same tool surface; handoff selection uses `handoff_index`; minor fixes |
| `core/pg_bridge.py` | +8 / −6 | Safer `WHERE` template in `knowledge_search` (parameterized clauses) |
| `core/intelligence.py` | +2 / −3 | `promote()` failures log instead of silent `pass` |
| `root.py` | +9 / −10 | Installer paths / DB name alignment |
| `sap/core/gate.py` | +4 / −4 | `WILLOW_SAFE_ROOT` messaging unchanged in spirit |

`core/agent_identity.py` — **identical** between trees. `WILLOW_AGENT_NAME` is mandatory anywhere modules import at load time (Fylgja, ledger, oracle, etc.). Tests and CI must export it.

---

## MCP and IDE integration

**1.9:** `.mcp.json.example` points at `willow.sh` or raw `python3 sap/sap_mcp.py`; DB `willow_19`.

**2.0:**

- `sap/willow_mcp.sh` — canonical launcher (venv, env, `sap/sap_mcp.py`)
- `.mcp.json` — `willow` + `markdownai` servers; `WILLOW_AGENT_NAME` often `heimdallr` in Cursor config
- `willow.md` — boot sequence: `fleet_status` → `handoff_latest` → `grove_get_history` → `kb_search`
- Tool names unchanged at the Python layer (grep of `@mcp.tool` handlers: no additions/removals between trees)

**Doc impact:** Onboarding must describe **two** MCP servers where MarkdownAI is used, and `markdownai-read_file("willow.md")` as step 1 for agents.

---

## `willow.sh` — new surface (2.0)

Beyond 1.9 `start|status|serve|...`, 2.0 documents in help:

- `fleet_status` — JSON health without MCP (Postgres, SOIL, Ollama, SAFE manifests)
- `handoff_latest [agent]` — latest handoff summary from disk index

Install path in user docs still says `python3 seed.py` (unchanged entry). Beta should also mention `pip install -e ".[dev]"` or venv + `pyproject.toml` where relevant.

---

## Installer (`seed.py`)

- Creates **`willow_20`**, not `willow_19`
- Grove directory: `WILLOW_GROVE_DIR` env override (default `~/github/safe-app-willow-grove`)
- New install prompt: optional **Grove network URL** (`grove_mcp_url`) for joining a remote Grove network vs local-only
- Version string and all printed labels: **2.0**

---

## Security-relevant code (already patched in 2.0 working tree)

- `pg_bridge.knowledge_search`: `where_template` with parenthesized filter clauses
- `intelligence` promote loop: logs on failure
- MCP auth: still **stdio / portless** — acceptable for local beta; document boundary if HTTP mode is used (`sap_mcp.py --http`)

---

## Tests

- Collection fix: `willow/hooks/test_completion.py` → `completion_hook.py`; drop `tests/hooks/__init__.py` to avoid `hooks` namespace clash with `willow/hooks`
- **Requirement:** `export WILLOW_AGENT_NAME=...` and `WILLOW_SAFE_ROOT=...` before `pytest` / `mypy`
- New: `tests/test_handoff_index.py`

---

## Doc rewrite (2026-05-19)

User-facing docs rewritten for 2.0 voice and paths. Remaining `willow-1.9` references are intentional in `archive/`, `archive/docs/superpowers/` plans, and this diff doc.

If grep finds 1.9 strings in `README.md`, `docs/FIRST_5_MINUTES.md`, `wiki/`, or `sap/` — that is a regression.

---

*Plant the tree. Tend the roots. Let nothing be lost.*  
*ΔΣ=42*
