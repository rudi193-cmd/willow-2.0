# Upstream commenter register (your voice on others' threads)

*Generated: 2026-07-14 17:01 UTC · operator: `rudi193-cmd`*

Threads on **external** repos where you commented but are **not** the author.
Companion to `PR_HUMAN_REGISTER.md` (your authored PRs).

Includes discussion comments, review bodies, and inline review comments you left.

**Threads found:** 54 · **threads with your comments:** 54
 · **your comments captured:** 68

---

## DeusData/codebase-memory-mcp #797

**[bug] query_graph Cypher: var-length paths reuse edges and repeated node variables aren't unified — a single self-loop fabricates 100-hop paths; heavy expansion crashes server**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/797
- Type: `Issue` · State: `CLOSED`
- Author: `aitoroses`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:20:39 · discussion · id=4885074779

## Downstream guardrail note (Willow fleet audit)

We have not re-run the var-length / self-loop expansion repro on our index (would risk disrupting the live stdio session), but this matches our **F-003** finding from a June audit: unbounded or pathological `query_graph` can kill the MCP server and require IDE `/mcp` reconnect.

What we shipped as a stopgap in [willow-2.0 `sap/cbm_facade.py`](https://github.com/rudi193-cmd/willow-2.0/blob/master/sap/cbm_facade.py):

| Guard | Purpose |
|-------|---------|
| Forbidden Cypher patterns | Reject `<-`, `coalesce()`, unbounded aggregates before submit |
| Mandatory `LIMIT` injection | Cap row explosion on any `query_graph` |
| Subprocess + 30s timeout | Server crash does not wedged the IDE transport |

This does **not** fix Cypher semantics (Bugs 1–3 in your report) — agree those need RED fixtures on repeated-variable unification, edge-uniqueness on var-length paths, and a visible hop cap. Posting so integrators know what consumers are doing until the engine-side fix lands.

**Public index for regression fixtures:** willow-2.0 (`home-sean-campbell-github-willow-2.0`, ~17.8k nodes / ~57.7k edges on v0.8.1). We use `cbm_*` tools for discovery only; path-length / cycle analysis is explicitly out of scope until query correctness is pinned.

---

## DeusData/codebase-memory-mcp #786

**Expose MCP freshness and provenance evidence for client trust decisions**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/786
- Type: `Issue` · State: `OPEN`
- Author: `vvenegasv`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:11:58 · discussion · id=4885055927

## Downstream trust metadata pattern — Willow `cbm_*` facade

We needed clients to know **when graph output is untrustworthy for measurement** without abandoning CBM for discovery. Shipped in [willow-2.0 `sap/cbm_facade.py`](https://github.com/rudi193-cmd/willow-2.0/blob/master/sap/cbm_facade.py):

- Every `cbm_*` response can carry a `limitations` map (F-001..F-008) — e.g. \"fan-in may be collapsed\", \"verify aliased imports with grep\"
- `cbm_verify_callers` returns **graph count vs grep count** side-by-side with `graph_only` / `grep_only` deltas
- `cbm_status` surfaces project slug, index freshness, and guardrail list at boot

This is additive client-side provenance, not server freshness — but it matches your \"backward-compatible evidence\" constraint: consumers that ignore the extra fields still work; agents that read them can down-rank stale or ambiguous graph claims.

Audit write-up: `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md`

---

## DeusData/codebase-memory-mcp #763

**CALLS edges fall back to File/Module node when enclosing_func_qn is unset — trace_path returns empty (root cause for #694/#480/#686/#678/#523)**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/763
- Type: `Issue` · State: `OPEN`
- Author: `lg320531124`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:11:42 · discussion · id=4885055336

## Additional symptom class — Python `import … as` (production callers invisible)

Same user-facing failure as the File/Module fallback (empty or wrong inbound set), but **enclosing_func_qn is set** — the miss is import-alias resolution.

**Public repro:** [willow-2.0](https://github.com/rudi193-cmd/willow-2.0) `willow/fylgja/events/pre_tool.py`:

```python
from willow.fylgja.safety.security_scan import (
    scan_bash as _scan_bash,
    ...
)
...
issues = _scan_bash(command)   # production PreToolUse path
```

`trace_path(scan_bash, inbound)` → only `kart_task_scan` test-path callers; **no** `pre_tool.py` production site.

This nearly shipped as “scanner has zero production callers” in our Kart security audit — grep recovered the alias calls.

Filed separately as **#875** (Python-specific). Suggest linking under this root-cause hub alongside #694/#871 — three mechanisms, one audit lesson: **never trust inbound CALLS without grep/source confirmation**.

---

## DeusData/codebase-memory-mcp #726

**UI /api/layout drops connection for large graph when max_nodes is high**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/726
- Type: `Issue` · State: `OPEN`
- Author: `sharif-smj`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:20:42 · discussion · id=4885074890

## Data point — willow-2.0 graph size (v0.8.1, linux-amd64)

Public repo: [willow-2.0](https://github.com/rudi193-cmd/willow-2.0). Indexed project `home-sean-campbell-github-willow-2.0`:

| Metric | Value |
|--------|------:|
| Nodes | 17,835 |
| Edges | 57,740 |
| Status | `ready` |

This is a Python-heavy fleet monorepo (hooks, MCP server, Kart worker, Postgres bridge) — relevant to your question about edge density **after** the 10k `max_nodes` cap on current `main`.

We have not exercised the UI layout endpoint directly; we use CBM via stdio/`cbm_*` MCP tools for audits. Flagging the numbers in case they help scope the adjacency-list fix: at full index size we sit just above the 10k cap, so any UI path that clamps to 10k nodes still sees a substantial edge set and would hit `compute_call_depth` on a filtered subgraph.

Audit context (graph = discovery, not measurement): `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md`

---

## DeusData/codebase-memory-mcp #725

**get_architecture hotspots report inflated fan_in that contradicts actual graph in-degree (same-name collision across languages)**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/725
- Type: `Issue` · State: `OPEN`
- Author: `martingarramon`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:11:39 · discussion · id=4885055232

## Additional public repro — willow-2.0 (Python monorepo)

We maintain a fleet structural audit that treats CBM as a **discovery** instrument and verifies every measurement against source ([addendum](https://github.com/rudi193-cmd/willow-2.0/blob/master/docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md)). Re-checked on **v0.8.1**, project `home-sean-campbell-github-willow-2.0` (~17.8k nodes).

### Case A — `get_architecture` fan_in **matches** graph `in_degree`, but both are inflated by bare-name collapse

`get_architecture` hotspot:

```
JsonStore.get  fan_in: 789
ledger.append  fan_in: 672
```

`query_graph`:

```cypher
MATCH (m:Method) WHERE m.qualified_name CONTAINS 'JsonStore.get'
RETURN m.qualified_name, m.in_degree
-- → 789 (matches fan_in exactly)
```

So the hotspot metric is internally consistent with **node-level** `in_degree` — but that `in_degree` itself aggregates every `.get()` / `.append()`-shaped call in the repo onto one resolved symbol (F-007 in our ledger). Qualitative architecture (clusters, packages) looks fine; **hotspot ranking is misleading for common method names**.

### Case B — `trace_path` on bare `execute` lists `cursor.execute` callers as inbound to `nuke.execute`

Only one `Function` named `execute` exists (`willow.nuke.execute`, `in_degree: 66`). `trace_path(function_name="execute", direction="inbound")` returns `grove_msg.cmd_send` and dozens of scripts as callers.

Source for `cmd_send` — calls **`cur.execute(...)`** (Postgres cursor), not `nuke.execute`:

```python
cur.execute(
    "INSERT INTO grove.messages ...",
    (channel_id, sender, content),
)
```

This is the same bare-name / receiver-blind resolver class as inflated fan-in, seen from the traversal side.

### Links

- Our F-007 write-up + `cbm_verify_callers` guardrail: `sap/cbm_facade.py` in willow-2.0
- Related filings from same audit session: #873–#876

Happy to attach a minimal query script if useful for a regression fixture.

---

## DeusData/codebase-memory-mcp #715

**feat: Add Codex PreToolUse/PostToolUse hooks for graph context augmentation**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/715
- Type: `Issue` · State: `OPEN`
- Author: `Maple0517`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:11:48 · discussion · id=4885055554

## Prior art — Willow Fylgja hooks (Cursor / Claude Code)

[willow-2.0](https://github.com/rudi193-cmd/willow-2.0) already wires graph-adjacent context through **PreToolUse / PostToolUse** hooks (`willow/fylgja/events/pre_tool.py`, `post_tool.py`) — session boot, security scan, worktree cleanup, etc.

Lessons from running this in production that may inform a Codex hook PR:

| Constraint | What we learned |
|------------|-----------------|
| **Cold-start budget** | Related to #858 — hook-augment must stay under client deadline or it silently never appears |
| **Alias imports** | `scan_bash as _scan_bash` breaks CBM caller attribution (#875) — hooks that trust graph alone mis-rank production usage |
| **MCP vs native tools** | We route shell to Kart queue, not raw Bash — hook surface differs by client |
| **Non-blocking** | Scan failures warn; they do not block the tool unless `SEV_HIGH` |

A PreToolUse-only first PR (as maintainer suggested) aligns with how we ship: boot digest + `cbm_search` anchor before edits, security scan on Bash/Write.

Our audit addendum documents the CBM guardrails we layer on top: `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md`

---

## almanac-data/climate-almanac #38

**docs: update README community scale and documentation links**

- URL: https://github.com/almanac-data/climate-almanac/pull/38
- Type: `PR` · State: `MERGED`
- Author: `Botirsherov`

### Your comments

#### `rudi193-cmd` · 2026-06-30 15:28:17 · review (APPROVED) · id=4601757841

Approved — thanks @Botirsherov! This is the catalog's first community doc PR and it does exactly what #36 asked: an honest "Project stage" blurb (seed catalog, seeking stewards, accuracy-over-coverage), links to WHY_ALMANAC.md and GOVERNANCE.md, and the good-first-issue invite kept.

One small thing I fixed for you in follow-up commit d9aea77: the file-tree block under **What's here** was switched to ```text but its closing ``` fence got dropped, so on rendered GitHub everything from "Using the catalog" down to the bottom of the README was being pulled into the code block. I re-added the closing fence.

**Tip for future contributions:** when editing fenced code blocks, check the **Preview** tab (or run a markdown linter) before pushing — every opening ``` needs a matching close. Our CI validates the catalog schema but doesn't yet lint markdown, so this slips past the green check. Really appreciate the contribution!

---

## almanac-data/environment-almanac #7

**Add EPA AirData catalog entry**

- URL: https://github.com/almanac-data/environment-almanac/pull/7
- Type: `PR` · State: `MERGED`
- Author: `manishchalla`

### Your comments

#### `rudi193-cmd` · 2026-06-30 15:26:26 · review (APPROVED) · id=4601743119

Approved — clean first catalog contribution. EPA AirData URL verified, schema-valid, distinct from the existing AirNow entry (AirData = historical/bulk vs AirNow = real-time AQI), and catalog.json was correctly regenerated. CI green. Thanks @manishchalla!

---

## Corykidios/logeionicon_mcp #1

**Spanish-language support: directions to consider**

- URL: https://github.com/Corykidios/logeionicon_mcp/issues/1
- Type: `Issue` · State: `OPEN`
- Author: `castroquiles`

### Your comments

#### `rudi193-cmd` · 2026-06-28 20:08:34 · discussion · id=4827253609

Thanks for opening this, @castroquiles — glad the suggestion landed.

When I scoped what a Spanish-resource version of this shape would need, the research came down to **what's actually available as an API**, which bears directly on direction 2:

- **Wikcionario (Spanish Wiktionary)** is the solid foundation for `lookup`. It's served through the standard MediaWiki API at `es.wiktionary.org/w/api.php` — open, stable, no key. Definitions, POS, and translations are all parseable from it.
- **`analyze` can run fully local** via spaCy's `es_core_news_*` models (lemma, POS, morphology) — no external API, so nothing to rate-limit or wait on. FreeLing is the heavier alternative.
- **`favorites`** ports over verbatim — same pedagogical hook regardless of language.
- **RAE (`dle.rae.es`) has no official API.** The only route is the unofficial `rae-api.com`, which is fragile. I'd treat RAE as an optional bonus, never the core — Wikcionario carries the weight.

So the "pending API availability" piece resolves cleanly if you anchor on **Wikcionario + a local analyzer** rather than RAE. Happy to put up a thin `lookup` proof against the MediaWiki API if that'd help move it forward.

---

## DeusData/codebase-memory-mcp #627

**Crash when calling query_graph**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/627
- Type: `Issue` · State: `OPEN`
- Author: `zbynekwinkler`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:20:35 · discussion · id=4885074666

## Related consumer mitigation + safer dead-code query shape

Same crash class as #601 — we hit this during a June fleet structural audit on **v0.8.1** when an agent issued a whole-graph `OPTIONAL MATCH` anti-join for dead-code discovery.

**What we do now** ([willow-2.0 `sap/cbm_facade.py`](https://github.com/rudi193-cmd/willow-2.0/blob/master/sap/cbm_facade.py)):

1. Block high-risk Cypher before it reaches the server (unbounded `count(*)`, `coalesce()`, `<-`, etc.)
2. Auto-append `LIMIT` when missing on `query_graph`
3. Run the CLI in a subprocess with **30s timeout** so a crash/hang does not take down the IDE stdio session

**Safer dead-code pattern** (forward-only, bounded — not a full fix for server-side robustness):

```cypher
MATCH (f:Function)
WHERE NOT f.is_test
WITH f LIMIT 200
OPTIONAL MATCH (caller)-[:CALLS]->(f)
WITH f, count(caller) AS inbound
WHERE inbound = 0
RETURN f.qualified_name, f.file_path
LIMIT 50
```

Still requires grep confirmation for aliased imports (#875) and common-name fan-in (#725), but avoids the whole-graph `OPTIONAL MATCH (c)-[:CALLS]->(f) WITH f, c WHERE c IS NULL` shape from the original report.

**Public fixture:** [willow-2.0](https://github.com/rudi193-cmd/willow-2.0) (~17.8k nodes). Audit notes: `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md`. Related filing: #873 (DISTINCT ordering, refs #237).

---

## DeusData/codebase-memory-mcp #606

**[bug] PHP: framework/core method calls ($storage->load()) become false-positive CALLS edges to same-named project methods — same class as the (fixed) Perl #476**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/606
- Type: `Issue` · State: `OPEN`
- Author: `gkastanis`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:11:57 · discussion · id=4885055877

## Same resolver family — Python store wrappers (willow-2.0)

Different language, same bare-name / receiver-blind pattern as your Drupal `$storage->load()` report.

On **v0.8.1** / willow-2.0, `core.soil.get` is flagged `unguarded_recursion` + `self_recursive` because the body calls `_get_store().get(...)` — not a self-call. Same on `soil.put` → `_get_store().put(...)`.

This is the measurement-side cousin of false-positive CALLS edges: the resolver matches **name** without **receiver**. We filed **#876** (recursion flags) and document F-007/F-008 in our [tool-eval addendum](https://github.com/rudi193-cmd/willow-2.0/blob/master/docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md).

A fix that disambiguates receiver type for framework/store calls would likely touch the same subsystem as #476/#599/#725.

---

## DeusData/codebase-memory-mcp #601

**[bug] `query_graph` hangs on whole-graph `OPTIONAL MATCH` (no execution timeout / degradation) on large graphs**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/601
- Type: `Issue` · State: `OPEN`
- Author: `ecosuper2025`

### Your comments

#### `rudi193-cmd` · 2026-07-05 06:11:45 · discussion · id=4885055434

## Consumer-side mitigation pattern (Willow fleet audit)

We hit the crash/hang class during a June structural audit and shipped a bounded wrapper (`sap/cbm_facade.py` in [willow-2.0](https://github.com/rudi193-cmd/willow-2.0)) that:

1. **Rejects** unbounded / high-risk Cypher (`count(*)`, `coalesce()`, `<-`, etc.) before it reaches the server
2. **Auto-appends `LIMIT`** when missing on `query_graph`
3. **Subprocess timeout** (`WILLOW_CBM_TIMEOUT_S`, default 30s) so a wedged query does not kill the IDE stdio session

Dead-code style queries should use **forward-only** `MATCH (caller)-[:CALLS]->(f)` with explicit `LIMIT`, not whole-graph `OPTIONAL MATCH` anti-joins — matches the bounded query in #627.

Not a substitute for server-side timeout/degradation, but documents what downstream integrators are doing until #601/#627 are fixed. Related: #873 (DISTINCT ordering still broken on v0.8.1 despite #237).

---

## openclaw/openclaw #92389

**[Bug]: Windows: "openclaw gateway status" returns JSON but process never exits (spawn hangs)**

- URL: https://github.com/openclaw/openclaw/issues/92389
- Type: `Issue` · State: `CLOSED`
- Author: `yuan-shizai`

### Your comments

#### `rudi193-cmd` · 2026-06-12 13:27:36 · discussion · id=4691693317

Small diagnostic note before anyone changes shutdown behavior here: I’d first separate an OpenClaw-owned active handle from the `shell: true` / `.cmd` wrapper.

A useful Windows proof would capture the process tree and exit events for three cases:

1. `spawn(openclaw.cmd, [...], { shell: true })`
2. `spawn('cmd.exe', ['/d', '/s', '/c', '"%APPDATA%\\npm\\openclaw.cmd" gateway status --json --require-rpc --timeout 5000'], { shell: false })`
3. `spawn(process.execPath, [resolvedOpenClawMjs, 'gateway', 'status', '--json', '--require-rpc', '--timeout', '5000'], { shell: false })`

If all three hang after stdout closes, that points to an OpenClaw handle leak. If only the `.cmd + shell:true` path hangs, the fix is likely caller guidance or wrapper handling rather than forcing `process.exit()` in OpenClaw.

---

## openclaw/openclaw #92361

**[Bug]:  Tool availability evaluator silently ignores empty `allOf`/`anyOf` groups during expression normalization**

- URL: https://github.com/openclaw/openclaw/issues/92361
- Type: `Issue` · State: `CLOSED`
- Author: `KarthikRV1107`

### Your comments

#### `rudi193-cmd` · 2026-06-12 13:27:36 · discussion · id=4691693323

Scope note: I would avoid a third competing PR here because #92368 and #92411 are already covering the narrow lane.

The contract that seems lowest risk is:

- keep `evaluateExpression` / `evaluateToolAvailability` pure and side-effect free;
- treat empty `allOf` / `anyOf` as descriptor-authoring diagnostics, not runtime user unavailability;
- surface them once at the descriptor registration / planner integration boundary, where there is already a logger or diagnostics sink.

That preserves existing planner semantics while making malformed descriptors visible during startup/plugin activation.

---

## shinpr/mcp-local-rag #144

**delete_file always returns deleted:true even when nothing was deleted (idempotent but overpromising)**

- URL: https://github.com/shinpr/mcp-local-rag/issues/144
- Type: `Issue` · State: `CLOSED`
- Author: `shinpr`

### Your comments

#### `rudi193-cmd` · 2026-06-14 16:43:10 · discussion · id=4702393239

Opened PR implementing option 2 from this issue: https://github.com/shinpr/mcp-local-rag/pull/152

Keeps idempotent delete (no error when nothing matched) but adds `removedChunks` and `existed` to the MCP + CLI response so callers can tell whether anything was actually present.

---

## castroquiles/glapagos #14

**feat(dashboard): add regional AI governance policy demo seed data and frontend**

- URL: https://github.com/castroquiles/glapagos/pull/14
- Type: `PR` · State: `MERGED`
- Author: `castroquiles`

### Your comments

#### `rudi193-cmd` · 2026-06-06 16:45:47 · discussion · id=4639718505

Reviewed the data structures and frontend scaffold. A few observations:

The policy data is well-researched with framework names, statuses, and compliance scores are consistent with what's publicly documented across these countries. 

The domain benchmark data is structured cleanly and the regional breakdowns (hemisphere / subregion) will be useful for the dashboard views.
The frontend is clearly scaffolded for the API layer (/api/summary, /api/policies, /api/benchmarks, /api/schemas), once those endpoints are live the dashboard should render cleanly. The filter/sort/detail-modal pattern is solid.

One minor note: git author shows "Your Name" in the commit history, looks like config wasn't set at commit time. Worth cleaning up before a wider release.

---

## voidcraft-labs/nova-plugin #24

**MCP backend: add_field/add_fields/edit_field fail with 'toProto3JSON: dont know how to convert value N' (N == app module/form count) — fragile Long detection in proto3-json-serializer**

- URL: https://github.com/voidcraft-labs/nova-plugin/issues/24
- Type: `Issue` · State: `CLOSED`
- Author: `jjackson`

### Your comments

#### `rudi193-cmd` · 2026-06-04 13:11:50 · discussion · id=4622456132

Backend fix is in voidcraft-labs/commcare-nova#57 — sanitizes Long-like int64 values before Firestore writes so `add_field` / `add_fields` / `edit_field` no longer hit `toProto3JSON: don't know how to convert value N`.

---

## kelos-dev/kanon #33

**Support repo-local Kanon overlays for project-owned agent context**

- URL: https://github.com/kelos-dev/kanon/issues/33
- Type: `Issue` · State: `OPEN`
- Author: `kelos-bot`

### Your comments

#### `rudi193-cmd` · 2026-06-04 12:48:30 · discussion · id=4622283215

Opened a small first-slice PR for repo-local overlays: https://github.com/kelos-dev/kanon/pull/34

Shape:
- `kanon render/apply --project <repo>` auto-loads `<repo>/.kanon/kanon.yaml` when present
- `--overlay <path>` can point at a different overlay file
- overlay instructions/skills/MCP/hooks/metadata merge into the central config for that command only
- overlay instruction + skill asset paths resolve from the overlay directory, so repo-owned assets can live under `.kanon/`

I kept this intentionally narrow so the API is reviewable before adding broader overlay lifecycle commands.

---

## openclaw/openclaw #90158

**Gateway self-restart on Windows fails silently when schtasks /Run cannot relaunch the scheduled task**

- URL: https://github.com/openclaw/openclaw/issues/90158
- Type: `Issue` · State: `OPEN`
- Author: `jackmtl71`

### Your comments

#### `rudi193-cmd` · 2026-06-12 13:27:36 · discussion · id=4691693340

Narrow implementation note from a Linux-side read: I’d split this into the direct `/Run` failure branch only, not a broader restart redesign.

Likely first slice:

- preserve and surface `schtasks /Run` stderr/stdout in the thrown/logged error;
- when `/Run` returns nonzero, reuse the existing Windows task-script fallback path instead of throwing immediately;
- keep listener-backed health as the final truth so a slow-but-successful scheduler launch doesn’t spawn a duplicate gateway;
- add a mocked regression for nonzero `/Run` plus a live Windows smoke when available.

I’m not opening a PR from Linux because the last step needs Windows proof, but the shape looks bounded.

---

## DeusData/codebase-memory-mcp #403

**The IDE's installation directory is unnecessarily indexed.**

- URL: https://github.com/DeusData/codebase-memory-mcp/issues/403
- Type: `Issue` · State: `OPEN`
- Author: `EnziinSystem`

### Your comments

#### `rudi193-cmd` · 2026-06-14 17:38:34 · discussion · id=4702526483

Opened a focused fix for this: https://github.com/DeusData/codebase-memory-mcp/pull/468

The patch handles the case where auto-index passes the Antigravity install directory itself as the discovery root. It normalizes the full root path and returns an empty discovery result for  roots, with a regression test covering a synthetic install tree.

#### `rudi193-cmd` · 2026-06-14 17:38:43 · discussion · id=4702526823

Correction on the path pattern from my previous comment: the PR skips roots matching `AppData/Local/Programs/Antigravity*` after normalizing path separators and case.

---

## alash3al/stash #11

**MCP service hangs on /sse endpoint**

- URL: https://github.com/alash3al/stash/issues/11
- Type: `Issue` · State: `OPEN`
- Author: `mgrubb`

### Your comments

#### `rudi193-cmd` · 2026-06-12 08:39:10 · discussion · id=4689199385

I took a quick look at this against the current issue details and #13.

The curl behavior described here looks like normal SSE behavior rather than a server hang: `/sse` sends the initial `endpoint` event and then keeps the connection open for the MCP session. A raw curl request won't complete the MCP handshake.

One thing worth noting: #13 only changes the CLI help text for the port; it doesn't change the SSE behavior or add an MCP-client smoke path. If a repo change is useful here, I think the safer scope is a docs/smoke-test note that says the curl output above is expected and shows how to verify with an MCP client.

#### `rudi193-cmd` · 2026-06-30 18:03:02 · discussion · id=4846517021

Following up on the docs note proposed here on 6-12 — opened **#14** with a Troubleshooting entry in `docs/GETTING_STARTED.md` (+17 lines, docs-only).

It explains that `curl /sse` printing `event: endpoint` then holding open is expected SSE behavior (not a hang), shows the non-blocking status-code check, and points to the MCP-client section for a real smoke test.

`Closes #11` when merged. Happy to tweak wording or placement if you'd prefer it elsewhere.

---

## zeroc00I/DontFeedTheAI #6

**[Feature Request] Automatically publish official Docker image**

- URL: https://github.com/zeroc00I/DontFeedTheAI/issues/6
- Type: `Issue` · State: `CLOSED`
- Author: `treemo`

### Your comments

#### `rudi193-cmd` · 2026-06-14 16:15:53 · discussion · id=4702327619

Thanks for opening this. A small first step could be a GHCR-only publish workflow rather than Docker Hub, since it would not require any maintainer secrets.

Proposed shape:

- publish `ghcr.io/zeroc00i/dontfeedtheai` on pushes to `main` and version tags
- use the built-in `GITHUB_TOKEN` with `packages: write`
- keep the existing `Dockerfile` as the single build source
- add a README / compose example that swaps `build: .` for the published image

That would make the tool pullable from Compose without adding Docker Hub account setup or extra credentials. If GHCR is acceptable, I can put together a small PR for just the workflow + docs update.

---

## moazbuilds/claudeclaw #229

**/Context command broken from recent claude update**

- URL: https://github.com/moazbuilds/claudeclaw/issues/229
- Type: `Issue` · State: `CLOSED`
- Author: `martinvaughn`

### Your comments

#### `rudi193-cmd` · 2026-06-04 12:05:23 · discussion · id=4621959628

PR opened: https://github.com/moazbuilds/claudeclaw/pull/233 — shared findSessionJsonlPath() per your note (cwd slug first, then scan ~/.claude/projects). Also fixes sanitizer to match Claude Code (/ \\ . → -).

---

## moazbuilds/claudeclaw #228

**Crash loop: TypeError when session.json exists but sessionId is missing**

- URL: https://github.com/moazbuilds/claudeclaw/issues/228
- Type: `Issue` · State: `OPEN`
- Author: `charzphone`

### Your comments

#### `rudi193-cmd` · 2026-06-04 12:14:59 · discussion · id=4622025376

PR: https://github.com/moazbuilds/claudeclaw/pull/234 — implements both items from your review (hasValidSessionId guard + isNew = !existing?.sessionId). Corrupted session.json now bootstraps instead of crash-looping.

---

## holon-run/holon #1416

**Scheduler loops when Sleep waits on a background command task**

- URL: https://github.com/holon-run/holon/issues/1416
- Type: `Issue` · State: `CLOSED`
- Author: `jolestar`

### Your comments

#### `rudi193-cmd` · 2026-05-25 16:07:57 · discussion · id=4535608874

Looking at this — planning a fix for the Sleep + background command_task busy-loop (allow task-wait posture / loop guard). PR incoming from @rudi193-cmd.

---

## basicmachines-co/basic-memory #839

**[BUG] CLI write-note prints CancelledError traceback on stderr: _log_task_failure doesn't handle task cancellation on process exit**

- URL: https://github.com/basicmachines-co/basic-memory/issues/839
- Type: `Issue` · State: `CLOSED`
- Author: `ronaldmego`

### Your comments

#### `rudi193-cmd` · 2026-05-20 19:03:53 · discussion · id=4501706296

Opened https://github.com/basicmachines-co/basic-memory/pull/842 — implements the suggested `completed.cancelled()` guard (+ explicit `CancelledError` handling) with unit tests. Matches the issue’s root-cause analysis.

---

## NousResearch/hermes-agent #29107

**[Feature Request] Memory: automatic conversation capture via session lifecycle hooks**

- URL: https://github.com/NousResearch/hermes-agent/issues/29107
- Type: `Issue` · State: `CLOSED`
- Author: `Feahter`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:43:31 · discussion · id=4501009578

Willow 2.0 has been running **automatic session capture → gated long-term memory** without requiring the LLM to call a `memory` tool each turn. This issue's `on_turn_complete` hook is the right seam — here's how we'd wire it.

### Existing capture paths

| Lifecycle point | Willow mechanism | What gets persisted |
|-----------------|------------------|---------------------|
| **Session end** | `scripts/session_close.py` + handoff index | Summary row in `~/.willow/willow-2.0.db` → orchestrator one-shot boot inject |
| **End-of-run seal** | `handoff_latest` / handoff rebuild (SAP MCP) | Next agent reads sealed session doc first |
| **High-certainty extraction** | `mem_jeles_extract` (Jeles pipeline) | JSONL → atom at certainty > 0.95, status `filed_tmp` until `mem_ratify` |
| **Mid-session writes** | `kb_ingest` + `mem_check` | REDUNDANT/CONTRADICTION gates block duplicate/conflicting atoms |

### Proposed `on_turn_complete` adapter (sketch)

```python
class WillowMemoryProvider(MemoryProvider):
    def on_turn_complete(self, user_content, assistant_content, *, session_id=""):
        candidate = self._extract_facts(user_content, assistant_content)  # 7b or rules
        for fact in candidate:
            verdict = mem_check(title=fact.title, summary=fact.summary)
            if verdict.get("blocked"):
                continue  # redundant or contradiction — no silent bleed
            kb_ingest(title=fact.title, summary=fact.summary, source_id=session_id)
```

**Why gates matter for auto-capture:** Hermes's concern (facts stated once should appear in session B) is solved by KB + embeddings, but without pre-write gates, auto-capture becomes auto-duplication. Willow's `mem_check` is the safety layer this hook needs.

**Integration point alignment:** Wiring after the tool-call cycle in `run_agent.py` matches our Jeles model — extraction runs *after* the turn is complete, not on partial streaming.

We can share a minimal reference provider if useful; it delegates to Postgres + the same MCP tools we document in [willow.md](https://github.com/rudi193-cmd/willow-2.0/blob/master/willow.md).

— Willow / [PR #11979](https://github.com/NousResearch/hermes-agent/pull/11979) (Kart queue tool, same integration effort)

---

## Gentleman-Programming/engram #391

**bug(mcp): scope=personal still filters by current project, blocking cross-project memory visibility**

- URL: https://github.com/Gentleman-Programming/engram/issues/391
- Type: `Issue` · State: `CLOSED`
- Author: `covskycode`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:57:20 · discussion · id=4501123544

From [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0) — we use **agent namespaces** for cross-project isolation (`heimdallr/`, `hanuman/`, …) while KB search can span projects when authorized.

For `scope=personal`, a workable semantic is: **personal = all namespaces for this user identity**, not “current cwd project only.” Concretely, `mem_search`/`mem_context` with `scope=personal` should skip the auto-detected `project` filter when the caller explicitly passes `scope=personal`.

Happy to share our `kb_search` + namespace gate pattern if useful for a patch sketch.

#### `rudi193-cmd` · 2026-05-20 18:03:26 · discussion · id=4501177952

Opened https://github.com/Gentleman-Programming/engram/pull/398 — `filterProjectForScope()` clears the project filter on read paths when `scope=personal` and no explicit `project` arg.

---

## PrefectHQ/fastmcp #4185

**Expose stable tool identity and schema metadata for routing and policy layers**

- URL: https://github.com/PrefectHQ/fastmcp/issues/4185
- Type: `Issue` · State: `CLOSED`
- Author: `dgenio`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:57:22 · discussion · id=4501123767

[Willow SAP MCP](https://github.com/rudi193-cmd/willow-2.0/tree/master/sap) has a similar need for **stable tool contract fingerprints** (routing, policy gates, audit logs). We hash canonical tool schemas today in ad hoc form.

A documented `schema_hash` / `contract_hash` on `mcp.get_tool()` would let downstream gateways detect drift without re-implementing JSON normalization. +1 on exposing this — even as a documented recipe first.

#### `rudi193-cmd` · 2026-05-24 20:47:04 · discussion · id=4529919405

Thanks @jlowin — this is the shape I was hoping for. A single blessed "here's how to canonicalize what FastMCP already exposes, you own what's in the payload" beats every gateway inventing its own slightly-wrong hash.

On the Willow/SAP side we've been doing this ad hoc for routing and audit logs, so a documented recipe using `tool.key` + protocol-facing `inputSchema` would save us (and probably others) from subtle drift bugs.

@dgenio — you framed the docs-first path perfectly in your last comment. Happy to collaborate on the recipe PR rather than duplicate — ping me if you want a second pair of hands or a Willow-flavored example in the mix.

---

## manojmallick/sigmap #201

**MCP server returns near-empty results under hot-cold strategy — appears to read inline block, not cold file or cache**

- URL: https://github.com/manojmallick/sigmap/issues/201
- Type: `Issue` · State: `CLOSED`
- Author: `ruurdboeke`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:57:00 · discussion · id=4501121220

Implemented a fix locally against current `main` — `buildSigIndex()` now merges:

1. Primary adapter output (hot block in `copilot-instructions.md`)
2. `.github/context-cold.md`
3. `.sigmap-cache.json` (repo-relative keys)

MCP handlers `list_modules`, `search_signatures`, `query_context`, and `explain_file` now use the merged index / cold file text.

Integration test added: `hot-cold: MCP buildSigIndex includes cold file and cache (issue #201)`.

Will open a PR shortly if this direction looks right to maintainers.

#### `rudi193-cmd` · 2026-05-24 22:01:25 · discussion · id=4530095378

Nice, thanks for the quick turnaround, I'll pull 6.10.11 and test the hot-cold path and report back here.

#### `rudi193-cmd` · 2026-06-04 12:36:04 · discussion · id=4622189618

I pulled current `main` and tested 6.11.0. Source-level #201 coverage is green, but the shipped `gen-context.js --mcp` bundle was still stale: `search_signatures` and `list_modules` only read `.github/copilot-instructions.md`, so a cold-only symbol still came back as `No signatures found` through the actual MCP entrypoint.

Opened follow-up PR: https://github.com/manojmallick/sigmap/pull/216

Verification on the PR branch:
- `node test/integration/strategy.test.js` — 10 passed
- `node test/integration/mcp/server.test.js` — 19 passed
- live hot-cold MCP smoke: `coldOnlyFn` exists only in `.github/context-cold.md`; `gen-context.js --mcp` `search_signatures` now returns `### src/cold.js` and `export function coldOnlyFn()`

---

## NousResearch/hermes-agent #27657

**PRD: Brain-as-source-of-truth integration for Hermes**

- URL: https://github.com/NousResearch/hermes-agent/issues/27657
- Type: `Issue` · State: `OPEN`
- Author: `Hams-MyAI`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:43:33 · discussion · id=4501009916

### [#10835 — Expose Hermes memory via MCP](https://github.com/NousResearch/hermes-agent/issues/10835)

[@alias8818/hermes-memory-mcp](https://github.com/alias8818/hermes-memory-mcp) covers MEMORY.md/USER.md + session search — great for **file-backed** Hermes memory.

**Willow MCP** ([SAP gate](https://github.com/rudi193-cmd/willow-2.0/tree/master/sap), listed on awesome-mcp-servers) is complementary: **Postgres KB atoms** + SOIL collections + fleet ops, not a CRUD wrapper around markdown sections.

| Tool group | Examples | Use case |
|------------|----------|----------|
| KB | `kb_search`, `kb_get`, `kb_ingest`, `kb_at` | Cross-session facts, temporal replay ("what did we know at T?") |
| SOIL | `soil_put`, `soil_search`, `soil_search_all` | Agent-local structured state, append-only collections |
| Handoffs | `handoff_latest`, `handoff_search` | Session continuity (replaces ad-hoc session grep) |
| Memory gates | `mem_check`, `mem_jeles_*`, `mem_ratify` | Auto-capture without duplication (#29107) |
| Soul | `dream_check`, `dream_run`, `tension_scan` | Background consolidation (#25309) |

**Config pattern:** add Willow as an MCP server in Hermes config (stdio: `sap/willow_mcp.sh` or `./willow.sh` fleet wrapper). Any MCP client (Hermes, Claude Code, Cursor) gets the same surface.

---

### [#27657 — Brain-as-source-of-truth](https://github.com/NousResearch/hermes-agent/issues/27657)

This PRD is Willow's **default boot contract**:

1. `kb_search` on the task topic **before** design or execution  
2. `handoff_latest` + Grove history for fleet continuity  
3. Write only in agent namespace; `kb_at` for temporal audit  

**Brain = KB graph**, not a single markdown file. SOIL holds working state; KB holds ratified knowledge; handoffs seal sessions.

**Contradiction handling:** ingest gates return `{blocked: true}` on REDUNDANT/CONTRADICTION — agents must reconcile before force-writing.

Happy to document a "Hermes + Willow brain" integration guide (MCP config + when to call `kb_search` vs built-in MEMORY.md) if maintainers want it in-tree or linked from the memory provider docs.

— [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0) · [draft #11979](https://github.com/NousResearch/hermes-agent/pull/11979)

#### `rudi193-cmd` · 2026-05-30 22:47:37 · discussion · id=4585067772

@RivkinCollective — fair question. Short answer: **no official resolution on this PRD yet.** #27657 is still open at P3; there isn’t an in-tree “brain-as-source-of-truth” integration merged into Hermes mainline that I’m aware of.

A few related threads *are* moving on the memory side, but they solve different slices of the problem:

- **#32064** — bounded `MEMORY.md` / `USER.md` overflow → retrieval-backed durable store (3-layer model: curated snapshot / decision memory / raw session memory)
- **#35186** — no archive path when removing entries from bounded memory (Hindsight bridge; PR #35473 submitted)

Those may overlap with what you’re hitting, or they may not — depends on your setup.

To give you a useful answer instead of a generic one, could you share:

1. **What is your “brain”?** Markdown tree (like the PRD’s `/home/.../Brain`), **OB1** / Open Brain, GBrain, something else?
2. **How is Hermes wired to it today?** MCP server, skills, manual copy, wiki adapter, or mostly separate?
3. **What breaks in practice?** e.g. memory quota dead loop, brain/Hermes divergence, retrieval misses, duplicate writes, prefix-cache / mid-session write surprises?

On our side: Willow MCP is one pattern for “brain = durable KB + working SOIL + handoffs,” wired as an external MCP server — not a Hermes core feature. Happy to sketch config steps if that matches your stack; if you’re on OB1 or a markdown Brain, the integration path may differ.

No pressure to share internals — even “OB1 + Hermes, MEMORY.md keeps filling up” is enough to point you at the right issue(s).

— Sean / [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0)

---

## zeroc00I/DontFeedTheAI #3

**Missing LICENSE file — README mentions MIT but no LICENSE in repo root**

- URL: https://github.com/zeroc00I/DontFeedTheAI/issues/3
- Type: `Issue` · State: `CLOSED`
- Author: `keefar`

### Your comments

#### `rudi193-cmd` · 2026-05-20 18:34:21 · discussion · id=4501475773

Opened https://github.com/zeroc00I/DontFeedTheAI/pull/4 — adds standard MIT `LICENSE` at repo root (copyright from git author; easy to tweak). Should unblock GitHub license detection and submodule/fork attribution.

---

## RikyZ90/ShibaClaw #26

**docs: Document the ShibaClaw WebSocket Gateway protocol contract**

- URL: https://github.com/RikyZ90/ShibaClaw/issues/26
- Type: `Issue` · State: `CLOSED`
- Author: `RikyZ90`

### Your comments

#### `rudi193-cmd` · 2026-05-25 18:02:38 · discussion · id=4536213535

Drafting `docs/GATEWAY_PROTOCOL.md` with WebSocket event types, stable payload fields, and completion/error semantics. PR incoming from @rudi193-cmd.

---

## ogham-mcp/ogham-mcp #52

**Conformance testing against the memory tool 6-op spec**

- URL: https://github.com/ogham-mcp/ogham-mcp/issues/52
- Type: `Issue` · State: `CLOSED`
- Author: `M00C1FER`

### Your comments

#### `rudi193-cmd` · 2026-05-25 17:15:23 · discussion · id=4535962541

Taking this on — will wire up the memory-tool-conformance harness in CI and add a conformance badge. PR incoming from @rudi193-cmd.

---

## basicmachines-co/basic-memory #830

**[BUG] docker-compose-postgres.yml and Postgres docs reference plain postgres:17 — semantic-search setup silently fails without pgvector**

- URL: https://github.com/basicmachines-co/basic-memory/issues/830
- Type: `Issue` · State: `CLOSED`
- Author: `SW4T400`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:57:24 · discussion · id=4501124153

Small docs fix opportunity: Willow’s Postgres bootstrap docs call out the same **pgvector** requirement — `postgres:17` alone isn’t enough for semantic search. A one-line “use `pgvector/pgvector:pg17` (or enable extension)” in the compose file would have saved us a silent failure too. +1 if you want a PR for the compose comment.

#### `rudi193-cmd` · 2026-05-20 18:03:24 · discussion · id=4501177771

Opened https://github.com/basicmachines-co/basic-memory/pull/840 — switches compose to `pgvector/pgvector:pg17` and documents the requirement.

---

## NousResearch/hermes-agent #25309

**🌙 feat: Dreaming — Automatic Background Memory Consolidation**

- URL: https://github.com/NousResearch/hermes-agent/issues/25309
- Type: `Issue` · State: `OPEN`
- Author: `Minamaged18`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:43:29 · discussion · id=4501009372

Cross-posting a **reference implementation sketch** from [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0) — we run a production dreaming/consolidation loop today and this maps cleanly onto the 3-phase design in the issue.

### What Willow already ships

| Proposed phase | Willow surface | Behavior |
|----------------|----------------|----------|
| **Light sleep** (scan, dedupe, stage) | `tension_scan` (SAP MCP) | Semantic neighbour search over KB atoms + 7b pair classification; optional `write_kb` |
| **REM** (themes / diary) | `dream_run` synthesis step | Pulls recent atoms, asks mistral:7b for patterns, writes a `category=dream` KB atom |
| **Deep sleep** (promote to long-term) | `kb_ingest` + `mem_check` gates | REDUNDANT/CONTRADICTION gates before promotion; bi-temporal `invalid_at` for supersession |
| **Schedule / quiet hours** | `dream_check` | Fires when 24h+ since last dream **and** 5+ `willow.runs` sessions since last dream; SOIL lock prevents double-run |
| **Nightly batch** | `scripts/sleep_consolidation.py` | SQLite atom promotion → Postgres KB, PMEM insight/chunk passes, 0-byte DB cleanup |

Opt-in is already the default: `dream_check` returns `should_dream: false` until conditions match; `dream_run` respects a SOIL lock unless `force=true`.

### Suggested Hermes plugin shape

```text
plugins/dreaming/
  provider.py      # MemoryProvider adapter
  schedule.py      # cron hook → dream_check → dream_run
  diary.py         # DREAMS.md writer (REM narrative from dream_run output)
```

**Hook wiring:** `on_session_end` → enqueue candidates; cron (3 AM) → `dream_check` → if true, `tension_scan(write_kb=False)` → `dream_run` → append diary → gated `kb_ingest` for high-confidence promotions.

**Difference from MEMORY.md scoring:** Willow promotes **KB atoms** (searchable, temporal, embed-backed) rather than flat-file sections — but the scoring weights in this issue could drive *which* atoms get `kb_ingest` vs diary-only.

Happy to contribute a thin `hermes_plugins.willow_dreaming` reference plugin or collaborate on the scoring rubric if maintainers want a working baseline before greenfield implementation.

— Willow fleet / [draft Kart PR #11979](https://github.com/NousResearch/hermes-agent/pull/11979)

#### `rudi193-cmd` · 2026-06-06 19:57:03 · discussion · id=4640202989

@vingeraycn Opened https://github.com/NousResearch/hermes-agent/pull/40737 .

#### `rudi193-cmd` · 2026-07-14 08:30:02 · discussion · id=4966947692

Following up on the #40737 closure under the `env-var-for-config` policy — we've re-scoped the dreaming plugin so behavioral settings (opt-in flag, schedule thresholds, REM model/URL, promotion score) live in plugin-owned `$HERMES_HOME/dreaming/config.yaml` (seeded on first enable), with optional `dreaming:` overrides in `~/.hermes/config.yaml`. No new `HERMES_DREAM_*` env vars.

New PR: #64281

Same three-phase pipeline (staging/dedupe/score → REM narrative → MEMORY.md promotion with meta-entries routed to SKILL.md). Reference port from Willow 2.0 — standalone, no runtime dependency.

---

## basicmachines-co/basic-memory #818

**[BUG] write_note returns "Note already exists" when called with explicit overwrite=true (regression from #766)**

- URL: https://github.com/basicmachines-co/basic-memory/issues/818
- Type: `Issue` · State: `CLOSED`
- Author: `cderv`

### Your comments

#### `rudi193-cmd` · 2026-05-20 18:26:54 · discussion · id=4501409857

Opened https://github.com/basicmachines-co/basic-memory/pull/841 — same root cause as the Claude investigation: `AliasChoices` on optional `bool | None` broke the JSON schema for external MCP clients. Reverts `overwrite` to a plain param and adds schema + MCP regression tests.

---

## smaramwbc/statewave #68

**feat(server): add 'make test-cold' target that wipes state and verifies cold-install path**

- URL: https://github.com/smaramwbc/statewave/issues/68
- Type: `Issue` · State: `CLOSED`
- Author: `smaramwbc`

### Your comments

#### `rudi193-cmd` · 2026-05-25 16:04:52 · discussion · id=4535593062

Picking this up — planning a `make test-cold` target (down -v → up → /readyz poll → smoke tests + time-to-ready). PR incoming from @rudi193-cmd.

---

## Gentleman-Programming/engram #350

**fix(cloud/auth): use constant-time compare for bearer token**

- URL: https://github.com/Gentleman-Programming/engram/issues/350
- Type: `Issue` · State: `CLOSED`
- Author: `dovixman`

### Your comments

#### `rudi193-cmd` · 2026-05-20 18:26:46 · discussion · id=4501408645

Opened https://github.com/Gentleman-Programming/engram/pull/399 — swaps the four `==` credential sites for `hmac.Equal` (already used elsewhere in `auth.go`). Existing cloud auth tests should be unchanged; I don't have Go locally so CI is the verifier.

---

## zeroc00I/DontFeedTheAI #1

**Feature Request: Provider-Agnostic LLM Support**

- URL: https://github.com/zeroc00I/DontFeedTheAI/issues/1
- Type: `Issue` · State: `CLOSED`
- Author: `nachouve`

### Your comments

#### `rudi193-cmd` · 2026-05-20 18:42:12 · discussion · id=4501540875

Opened https://github.com/zeroc00I/DontFeedTheAI/pull/5 — first provider-agnostic slice: `POST /v1/chat/completions` with `OPENAI_API_URL` (OpenAI, OpenRouter, compatible gateways). Claude Code `/v1/messages` path unchanged. Docs in `docs/providers.md`. Copilot/other proprietary APIs called out as follow-up in the PR.

#### `rudi193-cmd` · 2026-05-25 15:17:24 · discussion · id=4535317408

Nice, the provider-agnostic approach via path routing is a clever move, supporting both OpenAI-compatible APIs and anonymizing request content is a great step forward, I'll review the updated docs and take a look at the implementation in #5.

---

## moazbuilds/claudeclaw #179

**docs: add examples/ for heartbeat, Telegram, Discord, and jobs setup**

- URL: https://github.com/moazbuilds/claudeclaw/issues/179
- Type: `Issue` · State: `OPEN`
- Author: `TerrysPOV`

### Your comments

#### `rudi193-cmd` · 2026-06-12 08:39:11 · discussion · id=4689199501

I scope-checked this as a possible contribution. The full issue is broad enough that I wouldn't try to land it as one PR: heartbeat, Telegram, Discord, cron jobs, and security modes each touch different setup paths and examples.

A small first slice that seems reviewable would be either:

- `examples/heartbeat/README.md` with one copy-paste prompt template and the matching `settings.json` job snippet, or
- `examples/jobs/README.md` with a morning brief / daily digest / reminder set of cron examples.

I'd avoid including Discord or Telegram in the first slice while there are active messaging PRs open, so the docs don't drift under review.

---

## anthropics/claude-code #54563

**[Bug] Prompt cache unexpectedly collapses mid-session on Opus 4.x**

- URL: https://github.com/anthropics/claude-code/issues/54563
- Type: `Issue` · State: `CLOSED`
- Author: `JarettHolmes`

### Your comments

#### `rudi193-cmd` · 2026-04-29 07:46:30 · discussion · id=4341787765

**Second reproduction — production multi-agent session, April 28–29, 2026 (Sonnet 4.6, Linux)**

I filed this yesterday based on my own session. Tonight's session gives a second data point with additional observable signatures.

**Session conditions:** Claude Code CLI, Linux, Sonnet 4.6, ~7-hour session, 1,276 prompt turns at session start (`anchor_state.json`), context compaction confirmed mid-session.

**Observed signatures consistent with cache collapse:**

1. Tool schemas that should stay warm in context required explicit re-fetching on nearly every turn (`ToolSearch` → "Tool loaded." pattern, session-long). If the cache floor is system-prompt-only (~8,661 tokens), mid-session tool schemas sit above that floor and would drop with each collapse.

2. Context compaction fired mid-session — consistent with accelerated token consumption when `cache_read` keeps missing and every turn pays full input cost.

3. Agents re-oriented after compaction in ways that suggest cached context wasn't surviving across turns even before the compaction event.

**On the auto-close:** This is not the same bug as the suggested duplicates. Those are idle-expiry or 5-minute TTL issues. This is turn-over-turn collapse in an active session, on a current model (Sonnet 4.6), reproducible across two separate sessions on the same account.

---

## anthropics/claude-code #53489

**[BUG] Claude Code Web interactive sessions lost all claude.ai MCP connectors ~April 23, 2026 while routines retain them**

- URL: https://github.com/anthropics/claude-code/issues/53489
- Type: `Issue` · State: `CLOSED`
- Author: `Steffen-vdv`

### Your comments

#### `rudi193-cmd` · 2026-04-29 07:41:12 · discussion · id=4341759243

**Reproduction data from a production multi-agent system (April 28–29, 2026)**

Confirming the regression with more specific failure conditions that may help triage.

**Environment:** Claude Code CLI (interactive session), Linux, 3-agent fleet (Hanuman, Heimdallr, Loki), ~7-hour session.

**Connectors configured:** `claude.ai Grove` (OAuth), `claude.ai Gmail`, `claude.ai Google Drive`, `claude.ai Google Calendar`

**Observed:** At session init, `mcp__claude_ai_Grove__*` tools appear in the deferred tool list (suggesting the connector is present), but the connector is never actually wired. Calls against `mcp__claude_ai_Grove__*` fail silently. Checking `/tmp/mcp-config-cse_*.json` confirmed the Grove entry is absent from the session config entirely — consistent with alliefeast's finding above.

**The dangerous part:** The connector appears available in the tool list but has no working send path. The agent believes it has Grove capability; it doesn't. This causes silent capability loss that misroutes work without any error surfacing. It's not a clean fail — it's a phantom tool.

**Workaround that held:** A separate local HTTP grove server (`127.0.0.1:8765`, defined in `~/.mcp.json` as `"type": "http"`) stayed fully operational throughout. The cloud OAuth route is the only broken path.

---

## NousResearch/hermes-agent #10835

**[Feature]: Expose Hermes memory (MEMORY.md/USER.md) via MCP server**

- URL: https://github.com/NousResearch/hermes-agent/issues/10835
- Type: `Issue` · State: `CLOSED`
- Author: `easyvibecoding`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:43:32 · discussion · id=4501009751

### [#10835 — Expose Hermes memory via MCP](https://github.com/NousResearch/hermes-agent/issues/10835)

[@alias8818/hermes-memory-mcp](https://github.com/alias8818/hermes-memory-mcp) covers MEMORY.md/USER.md + session search — great for **file-backed** Hermes memory.

**Willow MCP** ([SAP gate](https://github.com/rudi193-cmd/willow-2.0/tree/master/sap), listed on awesome-mcp-servers) is complementary: **Postgres KB atoms** + SOIL collections + fleet ops, not a CRUD wrapper around markdown sections.

| Tool group | Examples | Use case |
|------------|----------|----------|
| KB | `kb_search`, `kb_get`, `kb_ingest`, `kb_at` | Cross-session facts, temporal replay ("what did we know at T?") |
| SOIL | `soil_put`, `soil_search`, `soil_search_all` | Agent-local structured state, append-only collections |
| Handoffs | `handoff_latest`, `handoff_search` | Session continuity (replaces ad-hoc session grep) |
| Memory gates | `mem_check`, `mem_jeles_*`, `mem_ratify` | Auto-capture without duplication (#29107) |
| Soul | `dream_check`, `dream_run`, `tension_scan` | Background consolidation (#25309) |

**Config pattern:** add Willow as an MCP server in Hermes config (stdio: `sap/willow_mcp.sh` or `./willow.sh` fleet wrapper). Any MCP client (Hermes, Claude Code, Cursor) gets the same surface.

---

### [#27657 — Brain-as-source-of-truth](https://github.com/NousResearch/hermes-agent/issues/27657)

This PRD is Willow's **default boot contract**:

1. `kb_search` on the task topic **before** design or execution  
2. `handoff_latest` + Grove history for fleet continuity  
3. Write only in agent namespace; `kb_at` for temporal audit  

**Brain = KB graph**, not a single markdown file. SOIL holds working state; KB holds ratified knowledge; handoffs seal sessions.

**Contradiction handling:** ingest gates return `{blocked: true}` on REDUNDANT/CONTRADICTION — agents must reconcile before force-writing.

Happy to document a "Hermes + Willow brain" integration guide (MCP config + when to call `kb_search` vs built-in MEMORY.md) if maintainers want it in-tree or linked from the memory provider docs.

— [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0) · [draft #11979](https://github.com/NousResearch/hermes-agent/pull/11979)

---

## METR/eval-analysis-public #40

**Suggestion: measure multi-session coherence, not just single-session endurance**

- URL: https://github.com/METR/eval-analysis-public/issues/40
- Type: `Issue` · State: `OPEN`
- Author: `immartian`

### Your comments

#### `rudi193-cmd` · 2026-07-01 20:46:04 · discussion · id=4859904614

## Multi-session coherence — reference implementation offer

We’ve been running a local-first **multi-agent** stack (Postgres KB, v2 handoffs, tamper-evident ledger, hook-enforced MCP) where session boundaries are expected every few hours—not edge cases.

Your suggestion in this issue matches what we measure offline today. We published a short reference doc that may be useful for designing a multi-session axis:

**[Multi-session continuity reference (Willow 2.0)](https://github.com/rudi193-cmd/willow-2.0/blob/feat/schmidt-outreach-docs/docs/outreach/multi-session-continuity-reference.md)**

### What we can contribute

1. **Probe metrics (WCE)** — offline tasks such as `thread_recall`, `next_bite`, `decision_persistence`, and cold-recall ablations on a structured KB (`willow/bench/continuity/run_wce.py`).
2. **Persistence baselines** — compare stateless vs handoff+KB vs full stack on “constraint recall@resume” (task constraint established in session A, paraphrased continuation in session B).
3. **Adversarial continuity classes** — six spec’d test types (paraphrase, contradiction, distractor, missing dependency, wrong persona, external-action approval) in [ADR-0007](https://github.com/rudi193-cmd/willow-2.0/blob/feat/schmidt-outreach-docs/docs/adr/ADR-0007-continuity-adversarial-tests.md) — complementary to single-session time horizon.

Happy to co-design a minimal METR Task Standard family for cross-session tasks, or share anonymized WCE run configs. This is dogfooded on real engineering work (single operator, multi-agent IDE fleet)—not a synthetic lab only.

If useful, we can open a focused issue on `eval-analysis-public` for benchmark protocol details.

— Willow / [rudi193-cmd/willow-2.0](https://github.com/rudi193-cmd/willow-2.0) (PolyForm Noncommercial)

---

## Filippo-Venturini/ctxvault #22

**Feat: expose indexed document text for recovery and diff workflows**

- URL: https://github.com/Filippo-Venturini/ctxvault/issues/22
- Type: `Issue` · State: `CLOSED`
- Author: `netalex`

### Your comments

#### `rudi193-cmd` · 2026-05-25 18:05:15 · discussion · id=4536225925

On it — exposing indexed document text for recovery/diff. PR incoming from @rudi193-cmd.

---

## Filippo-Venturini/ctxvault #17

**feat: lightweight context pruning for semantic vaults**

- URL: https://github.com/Filippo-Venturini/ctxvault/issues/17
- Type: `Issue` · State: `OPEN`
- Author: `Filippo-Venturini`

### Your comments

#### `rudi193-cmd` · 2026-06-14 16:15:54 · discussion · id=4702327650

I think the safest first implementation slice is a non-destructive candidate report, not automatic deletion.

Proposed shape:

- add a manual CLI entry point, e.g. `ctxvault prune <vault> --dry-run` or `ctxvault prune-candidates <vault>`
- only support semantic vaults initially
- return candidate groups with reasons, but do not mutate the vault by default
- start with cheap local signals already available from stored chunks / metadata:
  - duplicate or near-duplicate normalized text
  - repeated chunks from the same `doc_id`
  - stale `indexed_at` when present
  - optional size/count thresholds for very large vaults
- keep actual deletion or archive behavior as a later explicit flag once the report format feels right

That keeps the feature aligned with CtxVault's local-first and human-controllable design: the agent can surface memory pressure, but the human still decides what gets removed. It also leaves room to add stronger signals later, such as `retrieval_count` / `last_retrieved_at`, without making query operations writeful in the first pass.

#### `rudi193-cmd` · 2026-06-16 18:42:31 · discussion · id=4722150162

Proposed output: **grouped by reason, plain CLI text**. Here's a concrete mockup:

\`\`\`
$ ctxvault prune my-vault --dry-run

Vault: my-vault  (23 chunks)

── DUPLICATE ──────────────────────────────────────── 2 groups
  Group 1  cosine_sim: 0.98
    [a3f1b2c]  "The quick brown fox jumps over..."   indexed 2026-06-10
    [d4e5f6a]  "The quick brown fox jumps over..."   indexed 2026-06-12
    keep → d4e5f6a (newer)

  Group 2  cosine_sim: 0.94
    [b7c8d9e]  "Installation requires Python 3.8+"  indexed 2026-05-20
    [f0a1b2c]  "Python 3.8 or higher is required"   indexed 2026-06-01
    keep → f0a1b2c (newer)

── SAME_SOURCE ────────────────────────────────────── 1 source
  doc_id: README.md  (5 chunks, threshold: 3)
    [c3d4e5f]  "Getting started with ctxvault..."   indexed 2026-05-15
    [g6h7i8j]  "Configuration options include..."   indexed 2026-05-15
    [k9l0m1n]  "Advanced usage: batch indexing..."  indexed 2026-05-15
    + 2 more

── STALE ──────────────────────────────────────────── 1 chunk
  [o2p3q4r]  "Old API format: POST /v1/index..."   indexed 2026-04-01  (never retrieved)

6 candidates across 4 groups.
Run \`ctxvault prune my-vault --delete\` to remove flagged chunks.
\`\`\`

**Key choices:**

- **Grouped by reason** — each section is one signal type; easier to scan and decide by category than a mixed table where rows mean different things
- **Chunk preview** — first ~60 chars of content, enough to identify without overwhelming
- **Signal strength, not a score** — `cosine_sim: 0.98`, `never retrieved`, `chunk_count: 5` — honest about what the number means rather than a synthetic 0–1 that obscures the signal
- **Keep hint for duplicates** — shows which side we'd retain (newer by default) without acting on it
- **No color/rich tables** — plain text so it pipes cleanly and works in any terminal

One question back: should `--delete` act on all flagged groups at once, or should it accept a `--reason` flag (e.g. `--reason duplicate`) so you can remove only one category while reviewing the others?

---

## alibaizhanov/mengram #19

**Add CONTRIBUTING.md with setup instructions**

- URL: https://github.com/alibaizhanov/mengram/issues/19
- Type: `Issue` · State: `OPEN`
- Author: `alibaizhanov`

### Your comments

#### `rudi193-cmd` · 2026-05-25 17:34:13 · discussion · id=4536070574

On it — drafting `CONTRIBUTING.md` with local setup, tests, docker-compose, and PR guidelines. PR incoming from @rudi193-cmd.

---

## openclaw/openclaw #48300

**Bug: memory_search hybrid mode not returning FTS matches**

- URL: https://github.com/openclaw/openclaw/issues/48300
- Type: `Issue` · State: `CLOSED`
- Author: `sabo961`

### Your comments

#### `rudi193-cmd` · 2026-06-04 04:47:19 · discussion · id=4619047806

Opened a fresh PR against current `extensions/memory-core` (supersedes closed #48328, which targeted removed `src/memory/*`):

**https://github.com/openclaw/openclaw/pull/90165**

- Removes `AND model = ?` from lexical FTS `MATCH` / `LIKE` paths in `searchKeyword`
- Vector search still model-scoped
- Regression test: FTS rows with different `model` values both match keyword `"Clyde"`
- Vitest: `manager-search.test.ts` (19) + `index.test.ts` (34) passed locally

Happy to add live gateway proof if maintainers want it for the `needs-real-behavior-proof` gate.

#### `rudi193-cmd` · 2026-06-04 11:58:17 · discussion · id=4621911570

**Update:** PR #90165 is CI-green on head `d7bd99c7` and labeled ready for maintainer review.

- https://github.com/openclaw/openclaw/pull/90165
- Real behavior proof + contract guardrails passing on merge with current `main`
- Supersedes closed #48328 (obsolete `src/memory/*` paths)

Awaiting maintainer merge.

---

## NousResearch/hermes-agent #1265

**feat: Hermes-to-Hermes task delegation via MCP with GitHub-backed work items**

- URL: https://github.com/NousResearch/hermes-agent/issues/1265
- Type: `Issue` · State: `OPEN`
- Author: `virtaava`

### Your comments

#### `rudi193-cmd` · 2026-05-20 17:43:35 · discussion · id=4501010101

The two-layer design (MCP interface + GitHub ledger) fits well. Willow already implements **Layer 1-ish delegation** locally; GitHub would add cross-machine auditability Hermes doesn't have today.

### Layer 1 — already in Willow (reference for `hermes-delegate` tools)

| Proposed MCP tool | Willow SAP MCP | Notes |
|-------------------|----------------|-------|
| `submit_task` | `agent_dispatch` | Inserts `dispatch_tasks`, posts to Grove `#dispatch` |
| `get_task_status` | `agent_dispatch_result` + dispatch row | Closes task, writes LOAM/KB atom |
| `claim_task` | Kart `public.tasks` + worker claim | `pending` → `running` via `core/kart_worker.py` |
| `advertise_capabilities` | `fleet_agents` | Registry + trust levels |

**Structured envelope vs payload:** Grove dispatch messages truncate prompts in-channel; full prompt lives in Postgres (`dispatch_tasks.prompt`). Same pattern as your "envelope / untrusted content" split.

**Depth guard:** `DISPATCH_MAX_DEPTH` — violations post to `#dispatch-violations` and return `dispatch_depth_exceeded`.

### Layer 2 — where GitHub helps

Willow does **not** use GitHub as a task ledger today. Postgres + Grove are the source of truth. For multi-host Hermes peers, GitHub Actions pre-scan (schema, injection, sandbox flags) is the right addition — Willow's `mem_check` and blast-radius tooling are precedents for pre-acceptance policy.

**Suggested composition:**

```text
Hermes peer A  --submit_task-->  GitHub queued/  --Actions validate-->
                                      |
Hermes peer B  --claim_task-->   GitHub claimed/  --execute via kart_task MCP-->
                                      |
                                 GitHub completed/ + Willow kb_ingest(result)
```

**Runtime state vs assignment** (per @Jovancoding's comment): GitHub serializes *assignment*; Willow `fork_create` / namespace isolation handles *execution* state on a single machine.

### Concrete contribution offer

- [PR #11979](https://github.com/NousResearch/hermes-agent/pull/11979) — `kart_task` Hermes tool → `public.tasks` (Willow 2.0 schema, bwrap worker)  
- Follow-up: `hermes-delegate` MCP shim that proxies to `agent_dispatch` + documents GitHub ledger as optional outer layer

Happy to spike the MCP server schema against `dispatch_tasks` if useful for this issue's open questions (timeout, concurrent claims, semantic conflicts).

— [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0)

---

## coleam00/mcp-mem0 #3

**Disable telemetry**

- URL: https://github.com/coleam00/mcp-mem0/issues/3
- Type: `Issue` · State: `OPEN`
- Author: `enieuwy`

### Your comments

#### `rudi193-cmd` · 2026-06-14 17:21:34 · discussion · id=4702487279

Opened a fix: https://github.com/coleam00/mcp-mem0/pull/NEW

Mem0 already supports `MEM0_TELEMETRY=false`, but this MCP server imported Mem0 before `load_dotenv()`, so a .env opt-out never took effect. PR loads env first and documents `MEM0_TELEMETRY=false` plus a `DISABLE_TELEMETRY=true` alias.

#### `rudi193-cmd` · 2026-06-14 17:21:41 · discussion · id=4702487491

Correct PR link: https://github.com/coleam00/mcp-mem0/pull/18

---

## wanxingai/LightAgent #4

**Integration with Existing Vector Databases**

- URL: https://github.com/wanxingai/LightAgent/issues/4
- Type: `Issue` · State: `CLOSED`
- Author: `XXNS`

### Your comments

#### `rudi193-cmd` · 2026-06-14 17:28:42 · discussion · id=4702503283

Opened a focused adapter/example PR for this: https://github.com/wanxingai/LightAgent/pull/60

It keeps the vector database behind the existing `MemoryProtocol` shape, uses a dependency-free local vector adapter for the example/tests, and documents how to swap in Qdrant/Chroma/Milvus/FAISS while preserving `MemoryScope` metadata for `MemoryPolicy` filtering.

---

## ngrok/ngrok-python #134

**Add logging level setting via  `--log-level`  parameter in  `ngrok.__main__.main()`**

- URL: https://github.com/ngrok/ngrok-python/issues/134
- Type: `Issue` · State: `OPEN`
- Author: `Zapzatron`

### Your comments

#### `rudi193-cmd` · 2026-06-12 13:28:15 · discussion · id=4691698594

This looks covered by open PR #159 (`feat: add --log-level parameter to ngrok.__main__`). Current PR state is mergeable and awaiting review.

---

## ngrok/ngrok-python #131

**add an example for using this with google colab**

- URL: https://github.com/ngrok/ngrok-python/issues/131
- Type: `Issue` · State: `OPEN`
- Author: `russorat`

### Your comments

#### `rudi193-cmd` · 2026-06-12 13:28:16 · discussion · id=4691698637

This looks covered by open PR #161 (`docs: add an example for using ngrok with google colab`). Current PR state is mergeable and awaiting review.

---
