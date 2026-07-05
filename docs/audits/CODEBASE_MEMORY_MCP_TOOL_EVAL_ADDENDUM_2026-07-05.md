@markdownai v1.0

# codebase-memory-mcp Tool Evaluation — Addendum (July 2025 refresh)

**b17:** AUDIT · ΔΣ=42

**Date:** 2026-07-05
**Agent:** willow
**Mode:** read-only refresh
**Supersedes instrument metadata in:** `WILLOW_FLEET_STRUCTURAL_AUDIT_2026-06-15.md` (appendix), `KART_SCANNER_BWRAP_GAP_AUDIT_2026-06-15.md` (instrument line), SOIL `hanuman/tool_eval/codebase-memory-mcp`
**Scope:** Correct repository location, local clone, index receipts, and F-001..F-008 status against the **current** upstream tree — not a re-run of the full six-dimension fleet audit.

## Executive Summary

The June audit assumed a worktree at `willow-2.0/worktrees/upstream-codebase-memory-mcp` that **no longer exists** on disk. The canonical upstream project is **live and public** at [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) (not offline, not private, not archived; last push 2026-07-05). A fresh clone now lives at `~/github/codebase-memory-mcp`, **synced to `DeusData/main`** at `affa223` (2026-07-05). The installed binary is `v0.8.1` (2026-06-14). Willow's **`sap/cbm_facade.py` + `cbm_*` MCP tools** now implement the verification wrapper the June appendix called for; F-001..F-008 remain valid guardrails, not resolved upstream bugs.

## Repository status (corrected)

| Item | June 2026 audit | July 2026 refresh |
|------|-----------------|-------------------|
| **Canonical upstream** | Implicit / worktree path only | `https://github.com/DeusData/codebase-memory-mcp` |
| **Visibility** | Assumed available | **Public** (`archived: false`, `disabled: false`) |
| **Activity** | Indexed during active session | **Active** — commits on `main` through 2026-07-05; latest **release tag** still `v0.8.1` (2026-06-12) |
| **Local source (June)** | `worktrees/upstream-codebase-memory-mcp` | **Missing** — path does not exist |
| **Local source (now)** | — | `~/github/codebase-memory-mcp` @ `affa223` (synced with `DeusData/main`) |
| **Installed binary** | `~/.local/bin/codebase-memory-mcp` | Same path; reports **`codebase-memory-mcp 0.8.1`** |
| **Index cache** | `~/.cache/codebase-memory-mcp/*.db` | Same layout; project slugs unchanged |

**Fork sync:** Operator merged `upstream/main` on 2026-07-05; local clone matches `DeusData/main` at `affa223` (0 behind). For source audits, track **`upstream` → `DeusData/codebase-memory-mcp`**.

**Note on “moved”:** Upstream has always been under the **DeusData** org in GitHub API and in the binary's update URL. If an older bookmark pointed elsewhere (org rename, docs site, or a transient mirror), use the table above as canonical.

## Live inventory — graph indexes (refreshed)

| Project slug | Root path | Nodes | Edges | Mode | When |
|--------------|-----------|------:|------:|------|------|
| `home-sean-campbell-github-willow-2.0` | `~/github/willow-2.0` | 17,832 | 57,737 | cache (spot-check session) | 2026-07-05 |
| `home-sean-campbell-github-codebase-memory-mcp` | `~/github/codebase-memory-mcp` | 11,080 | 40,775 | **moderate** (pre-sync index) | 2026-07-05 |

June willow-2.0 figures were **14,498 / 47,007** — growth reflects codebase change + index mode, not a different product. **Re-index** `codebase-memory-mcp` after sync if auditing post-`affa223` source.

## Willow mitigation — shipped since June

The June appendix proposed a custom facade. **Delivered:**

| Layer (June design map) | July status | Implementation |
|-------------------------|-------------|----------------|
| Stability wrapper (F-003) | **Shipped** | `sap/cbm_facade.py` — `_prepare_cypher`, `_clamp`, `QUERY_TIMEOUT_S`, CLI subprocess with timeout |
| Alias-aware verification (F-004/F-007) | **Shipped** | `cbm_verify_callers`, `cbm_reconcile`; grep cross-check |
| Curated bounded access | **Shipped** | `cbm_search`, `cbm_trace`, `cbm_query` via Willow MCP (`tests/test_cbm_facade.py`) |
| Supervised transport | **Open** | Still stdio; crash still requires IDE `/mcp` reconnect |
| Reconcile with `code_graph_*` | **Policy** | Boot digest + handoffs: **`cbm_*` is the code-discovery lane**; native `code_graph_*` secondary |

**Operational rule (unchanged):** graph = discovery; grep/source = measurement.

## F-001..F-008 — spot re-verification (2026-07-05)

| ID | June verdict | Re-check | Status |
|----|--------------|----------|--------|
| F-001 | Cypher subset rejects `coalesce()` in WHERE | `query_graph` with `coalesce(f.transitive_loop_depth,0)` → `unexpected operator at pos 33` | **Still open** → [#874](https://github.com/DeusData/codebase-memory-mcp/issues/874) |
| F-002 | No `<-` arrows / pattern predicates | Not re-run (parser unchanged in source) | **Assumed open** |
| F-003 | Unbounded aggregate can kill stdio server | Not re-run (would disrupt session); facade blocks forbidden Cypher | **Mitigated in Willow; open upstream** |
| F-004 | Aliased imports miss CALLS edges | `pre_tool.py`: `scan_bash as _scan_bash` → production callers invisible to `trace_path` | **Still open** → [#875](https://github.com/DeusData/codebase-memory-mcp/issues/875) |
| F-005 | DISTINCT+ORDER BY+LIMIT truncates silently | See **F-005 recheck** below | **Verified open** → [#873](https://github.com/DeusData/codebase-memory-mcp/issues/873) (refs [#237](https://github.com/DeusData/codebase-memory-mcp/issues/237)) |
| F-006 | Architecture folds test traffic | Not re-run; overlaps [#725](https://github.com/DeusData/codebase-memory-mcp/issues/725) | **Assumed open** |
| F-007 | Common-name fan-in collapse | Not re-run; overlaps [#725](https://github.com/DeusData/codebase-memory-mcp/issues/725) / [#606](https://github.com/DeusData/codebase-memory-mcp/issues/606) | **Still open** |
| F-008 | Recursion flags are artifacts | See **F-008 recheck** below | **Verified open** → [#876](https://github.com/DeusData/codebase-memory-mcp/issues/876) (refs [#599](https://github.com/DeusData/codebase-memory-mcp/issues/599)) |

**Conclusion:** The June tool-evaluation appendix remains **methodologically valid**. Treat **`cbm_*` + verify_callers** as the supported audit path — not raw `codebase-memory-mcp_*` without bounds.

### F-005 recheck (2026-07-05, binary v0.8.1, project `home-sean-campbell-github-willow-2.0`)

Ground truth: **5** distinct node labels (`count(DISTINCT n.label)`).

| Query | Rows | Correct? |
|-------|------|----------|
| `MATCH (n) RETURN DISTINCT n.label AS label ORDER BY label LIMIT 30` | 2 (Section, Variable) | **No** |
| `MATCH (n:Function) RETURN DISTINCT n.file_path AS path ORDER BY path LIMIT 5` | 1 | **No** |
| `MATCH (n) WITH DISTINCT n.label AS label RETURN label ORDER BY label LIMIT 20` | 5 | **Yes** (workaround) |
| `MATCH (n:Function) WITH DISTINCT n.file_path AS path RETURN path ORDER BY path LIMIT 5` | 5 | **Yes** (workaround) |

[#237](https://github.com/DeusData/codebase-memory-mcp/issues/237) was closed 2026-05-31; filed [#873](https://github.com/DeusData/codebase-memory-mcp/issues/873) for the remaining `RETURN DISTINCT … ORDER BY … LIMIT` shape on v0.8.1.

### F-008 recheck (2026-07-05, same index)

**14** functions flagged `unguarded_recursion=true`. Representative false positives (source read confirms no self-call):

| Function | Flags | Actual callee |
|----------|-------|---------------|
| `core.soil.get` | `unguarded_recursion`, `self_recursive` | `_get_store().get(...)` |
| `core.soil.put` | same | `_get_store().put(...)` |
| `core.gleipnir.check` | `unguarded_recursion`, `recursive` | `_default.check(...)` |
| `willow.nuke.execute` | `recursive=true` (not unguarded) | loops + I/O only — no self-call |

[#599](https://github.com/DeusData/codebase-memory-mcp/issues/599) addressed `super()` / `axios.get`-style cases; filed [#876](https://github.com/DeusData/codebase-memory-mcp/issues/876) for delegation/store patterns.

## Upstream issues filed (2026-07-05)

| Willow ID | GitHub issue | Notes |
|-----------|--------------|-------|
| F-001 | [#874](https://github.com/DeusData/codebase-memory-mcp/issues/874) | `coalesce()` in WHERE |
| F-004 | [#875](https://github.com/DeusData/codebase-memory-mcp/issues/875) | Python `import … as` → CALLS / trace_path |
| F-005 | [#873](https://github.com/DeusData/codebase-memory-mcp/issues/873) | `RETURN DISTINCT … ORDER BY … LIMIT`; refs #237 |
| F-008 | [#876](https://github.com/DeusData/codebase-memory-mcp/issues/876) | delegation/store recursion false positives; refs #599 |

## Source layout (from indexed clone)

Pure **C** static binary. Primary seams for auditors:

| Path | Role |
|------|------|
| `src/main.c` | Entry — MCP stdio server loop |
| `src/mcp/mcp.c` | All `handle_*` tool handlers (`index_repository`, `search_graph`, `trace_path`, `query_graph`, …) |
| `internal/cbm/` | Store, Cypher, sqlite writer, call extraction |
| `src/pipeline/` | Indexing passes (tree-sitter + Hybrid LSP) |
| `tests/test_*.c` | Large integration surface (README claims 5600+ tests) |

Self-index via CBM works once the clone is indexed (`home-sean-campbell-github-codebase-memory-mcp`).

## Resolution / Follow-up

| Action | Owner | Target |
|--------|-------|--------|
| `git fetch upstream && merge` on `~/github/codebase-memory-mcp` | operator | **done** (2026-07-05, `affa223`) |
| Re-index CBM after sync (`index_repository` full or moderate) | willow | when next auditing CBM source |
| File F-001 / F-004 / F-005 / F-008 upstream | willow | **done** — #873–#876 |
| Replace stale SOIL `worktree` path | willow | done in this refresh |
| Full six-dimension fleet re-audit | builder | only if authorized — out of scope here |

## Receipts

| Type | Ref |
|------|-----|
| June audits | `docs/audits/WILLOW_FLEET_STRUCTURAL_AUDIT_2026-06-15.md`, `KART_SCANNER_BWRAP_GAP_AUDIT_2026-06-15.md` |
| This addendum | `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md` |
| Upstream | `DeusData/codebase-memory-mcp` @ `affa223` (2026-07-05) |
| Upstream issues | [#873](https://github.com/DeusData/codebase-memory-mcp/issues/873), [#874](https://github.com/DeusData/codebase-memory-mcp/issues/874), [#875](https://github.com/DeusData/codebase-memory-mcp/issues/875), [#876](https://github.com/DeusData/codebase-memory-mcp/issues/876) |
| Local clone | `~/github/codebase-memory-mcp` @ `affa223` (synced with upstream) |
| Binary | `~/.local/bin/codebase-memory-mcp` → `0.8.1` |
| Willow facade | `sap/cbm_facade.py`, `tests/test_cbm_facade.py`, `sap/sap_mcp.py` (`cbm_*`) |
| SOIL | `hanuman/tool_eval/codebase-memory-mcp` (updated 2026-07-05) |
| Tools | `codebase-memory-mcp` (`list_projects`, `index_repository`, `index_status`, `query_graph`, `get_code_snippet`, `get_architecture`); `cbm_verify_callers` |

---

*b17: AUDIT · ΔΣ=42*

## Agent Notes for Human

- Upstream is **not dead** — the gap was a missing/stale local clone and a fork frozen mid-June.
- June structural findings (inversion of care, pg_bridge, grove_listen) are **unchanged** by this addendum; only the **CBM instrument appendix** is refreshed.
- F-005/F-008 spot re-checks downgraded from “assumed” to **verified open** on v0.8.1; four issues filed upstream.

## Human Notes to Agent

<!-- operator writes here after review -->

-
