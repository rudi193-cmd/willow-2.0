# Git-shaped sandbox — full implementation spec

**b17:** GSSBX · ΔΣ=42  
**Status:** Implemented (reference)  
**Policy:** `docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md`  
**Code:** `sandbox/` package + `tests/test_sandbox/test_git_shaped.py`

---

## 1. Purpose

Deliver a **runnable contract** for the WLGSM policy:

- **States** and **allowed edges** match §2–§3 (plus repair arcs `checks→open`, `review→open`).
- **Illegal transitions** raise `GitShapedError` (same moral as “don’t merge without review”).
- **Persistence** is a JSON file so CI and laptops run without SOIL.
- **§4 gate** is a small dataclass + CLI validator so new automation can be checked in shell scripts.

Future work: **bind** this model to real Willow (SOIL collection, MCP tools, Grove posts) without changing the state graph.

---

## 2. Module map

| Module | Responsibility |
|--------|----------------|
| `sandbox/model.py` | `ShapeState`, `ChangeRecord`, `Transition`, `allowed_targets`, `create_issue` |
| `sandbox/engine.py` | `advance()`, `preview_advance()`, `GitShapedError`; updates `updated_at` |
| `sandbox/store.py` | `JsonStore` — load/save, `delete`, `clear` |
| `sandbox/reporting.py` | `markdown_table`, `allowed_line`, `json_lines` |
| `sandbox/gate_form.py` | `NewFeatureGate` + `validate()` / `ok()` |
| `sandbox/cli.py` | `python -m sandbox` subcommands |
| `sandbox/__main__.py` | Entry shim |

---

## 3. State graph (implementation)

Same as policy diagram. Repair arcs:

- **`checks` → `open`:** CI failed; fix before re-entering checks.
- **`review` → `open`:** Maintainer requested changes.

Terminal: **`archived`**. No outbound edges.

---

## 4. JSON schema (`ChangeRecord`)

| Field | Type | Notes |
|-------|------|--------|
| `id` | string | `gs-` + 12 hex chars |
| `title` | string | PR-title analogue |
| `state` | string enum | `issue` … `archived` |
| `created_at` | string (ISO8601) | set on `issue-create` |
| `updated_at` | string (ISO8601) | updated on each `advance` |
| `subject` | string | optional human scope |
| `grove_channel` | string | reserved for fleet binding |
| `kb_seed_hint` | string | reserved (atom id or title) |
| `fork_id` | string | reserved |
| `flag_id` | string | optional link to SOIL flag id |
| `history` | array | `{at, from_state, to_state, actor, note}` |

---

## 5. CLI contract

| Command | Behavior |
|---------|----------|
| `init` | Ensure `data/` + empty JSON store |
| `issue-create` | New record at `issue`; optional `--grove`, `--kb-hint`, `--fork` |
| `advance` | One legal transition; `--dry-run` prints JSON preview, no write |
| `show` | Pretty JSON |
| `list` | TSV; `--long` timestamps + hints; `--json` full array |
| `allowed` | Human-readable next states + one per line |
| `report` | Markdown table for Grove / handoffs |
| `delete` | Drop one id |
| `reset --yes` | Clear store (flag required) |
| `gate-check` | Validates §4 four strings; exit 1 if any empty |

Global: `--data PATH` (default `sandbox/data/changes.json`).

---

## 6. Fleet binding (not implemented here)

| Sandbox | Willow (proposed) |
|---------|-------------------|
| `ChangeRecord` | SOIL `hanuman/gitshaped_changes` (or per-app collection) |
| `issue` | `store_put` flag or dispatch row |
| `draft` | `willow_fork_create` + worktree metadata on record |
| `open` | Grove post id + KB seed atom id written on record |
| `checks` | Kart task id(s), CI run URL, `memory_check` result hash |
| `review` | Sean / owner ack timestamp |
| `merged` | `willow_fork_merge` + merge commit sha |
| `release` | `willow_frank_ledger_write` id |
| `archived` | KB `domain=archived` + SOIL soft-delete |

**Idempotency:** `advance` should become a single SOIL `store_update` or transactional update when wired — today it is last-write-wins JSON.

---

## 7. CI

`tests/test_sandbox/test_git_shaped.py` covers:

- Linear path to `archived`
- Repair arc `checks→open`
- Illegal skip `draft→merged`
- Gate validation
- JSON roundtrip + `created_at` / `updated_at`
- `preview_advance` immutability on original
- `delete` / `clear`
- Markdown report

---

## 8. Rollout phases

1. **Done:** reference package + tests + CLI (this folder).  
2. **Next:** one SOIL collection + thin MCP tool wrapper (optional) that maps CRUD to `ChangeRecord`.  
3. **Later:** Grove template for “Open PR” posts + handoff line with `change_id`.

---

*When binding to production, keep this package’s tests as the golden graph — do not relax transitions without updating policy §3.*
