# Open work (fleet backlog)

*Last updated: 2026-07-14 — desk touch: Hermes dreaming re-scope (#64281); #40737 closed.*

**Strategy:** [`UPSTREAM_CONTRIBUTION_STRATEGY.md`](UPSTREAM_CONTRIBUTION_STRATEGY.md) · type ledger: [`upstream/type_ledger.json`](upstream/type_ledger.json)

**Auto intel (weekly Kart):** [`upstream/MAINTAINER_HEATMAP.md`](upstream/MAINTAINER_HEATMAP.md) · [`upstream/PROMISE_LEDGER.md`](upstream/PROMISE_LEDGER.md) — refreshed by `willow-upstream-desk.timer` / `scripts/upstream_desk_intel.py`.

> **2026-07-14 state change:** [NousResearch/hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) **closed** by `hermes-sweeper` (`env-var-for-config` — behavioral settings must live in `config.yaml`). Re-scoped successor [hermes-agent #64281](https://github.com/NousResearch/hermes-agent/pull/64281) opened — plugin-owned `$HERMES_HOME/dreaming/config.yaml`, CI green, follow-up on [#25309](https://github.com/NousResearch/hermes-agent/issues/25309#issuecomment-4966947692). **Wait on maintainer** review.
>
> **2026-07-11 state change:** Maintainer heatmap pass (205 threads, 66 repos) — **9 cold lanes** folded in below. [zeroc00I/DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) **merged** 2026-07-08. [mex-memory/mex #84](https://github.com/mex-memory/mex/pull/84) **merged** 2026-07-06. [Taiko2k/Tauon #2209](https://github.com/Taiko2k/Tauon/pull/2209) **merged** 2026-07-02 (companion to #2208). New open threads not on prior desk: [basicmachines-co/basic-memory #1010](https://github.com/basicmachines-co/basic-memory/pull/1010), [castroquiles/HeatWatch #20](https://github.com/castroquiles/HeatWatch/pull/20). Audit: [`audits/OPEN_WORK_DESK_VERIFY_2026-07-11.md`](audits/OPEN_WORK_DESK_VERIFY_2026-07-11.md).
>
> **2026-06-30 state change:** [Taiko2k/Tauon #2208](https://github.com/Taiko2k/Tauon/pull/2208) **merged** (Tidal return-type annotations toward #1338). [alash3al/stash #14](https://github.com/alash3al/stash/pull/14) **opened** (docs_setup — SSE curl troubleshooting, closes #11); issue follow-up posted 2026-06-30 — **wait on maintainer**.
>
> **2026-06-29 state change:** claudeclaw **#239 and #240 merged** (TerrysPOV approved + merged
> 2026-06-28). claudeclaw **#234** — `listThreadSessions` filter at HEAD (`a9eb7cb`/`54854a9`); TerrysPOV's 2026-06-28 `CHANGES_REQUESTED` may be stale vs parent `5a6e6336` but **still live on GitHub** as of 2026-07-11 — needs maintainer re-review/dismissal. codejail **#309** CLA **executed 2026-06-24**; review nudge posted 2026-06-28 — maintainer's court.

## Cold lanes (maintainer heatmap)

Open repos with **no maintainer reply** (or stale `CHANGES_REQUESTED`). Source: [`MAINTAINER_HEATMAP.md`](upstream/MAINTAINER_HEATMAP.md) — regenerate with `python3 scripts/upstream_desk_intel.py` or wait for weekly Kart run.

| Repo | Open threads | Known PR(s) | Desk action |
|------|--------------|-------------|-------------|
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | 2 | (see issue #6) | **Cold** — no maintainer signal; deprioritize or gentle nudge |
| [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) | 2 | [#18](https://github.com/coleam00/mcp-mem0/pull/18) | **Cold** — mergeable, no review; wait or withdraw |
| [kelos-dev/kanon](https://github.com/kelos-dev/kanon) | 2 | [#34](https://github.com/kelos-dev/kanon/pull/34) | **Cold** — label gate only; deprioritize |
| [openedx/codejail](https://github.com/openedx/codejail/pull/309) | 1 | [#309](https://github.com/openedx/codejail/pull/309) | **Cold** — CLA done; wait on `mphilbrick211` |
| [PDFMathTranslate/PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) | 1 | [#1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | **Cold** — mergeable, no review |
| [alibaizhanov/mengram](https://github.com/alibaizhanov/mengram) | 1 | (see issue #6) | **Cold** — prior #40 closed without merge |
| [castroquiles/HeatWatch](https://github.com/castroquiles/HeatWatch) | 1 | [#20](https://github.com/castroquiles/HeatWatch/pull/20) | **Cold** — geo_utils off-by-one; no maintainer reply |
| [Corykidios/logeionicon_mcp](https://github.com/Corykidios/logeionicon_mcp) | 1 | (see issue #6) | **Cold** — commenter thread only |
| [METR/eval-analysis-public](https://github.com/METR/eval-analysis-public) | 1 | (see issue #6) | **Cold** — commenter thread only |

**Desk rule for cold:** Do not invest further unless maintainer engages or you explicitly withdraw. Prefer **warm** lanes (DeusData/codebase-memory-mcp, claudeclaw/TerrysPOV, ctxvault, stash/alash3al) for new nudges.

## Upstream desk preflight

Score each open PR before opening new upstream work. Rubric: 5×0–2 → **green** 8–10 · **yellow** 5–7 · **red** 0–4.

| PR | Type | Score | Lane | Next action |
|----|------|-------|------|-------------|
| [claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | narrow_bugfix | 8 | green | **MERGED 2026-06-28** ✓ |
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | narrow_bugfix | 8 | green | Filter at HEAD; live `CHANGES_REQUESTED` on GitHub — **wait on maintainer** re-review/dismiss |
| [claudeclaw #239](https://github.com/moazbuilds/claudeclaw/pull/239) | narrow_bugfix | 8 | green | **MERGED 2026-06-28** ✓ |
| [claudeclaw #240](https://github.com/moazbuilds/claudeclaw/pull/240) | docs_setup | 8 | green | **MERGED 2026-06-28** ✓ |
| [mcp-mem0 #18](https://github.com/coleam00/mcp-mem0/pull/18) | narrow_bugfix | 8 | green | Issue-linked (Fixes #3), mergeable, no review — **cold maintainer** |
| [DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) | ci_verify | 7 | — | **MERGED 2026-07-08** ✓ |
| [PDFMathTranslate #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | small_feature | 6 | yellow | Mergeable, no review — **cold** |
| [mex #84](https://github.com/mex-memory/mex/pull/84) | mcp_adapter | 6 | — | **MERGED 2026-07-06** ✓ |
| [codejail #309](https://github.com/openedx/codejail/pull/309) | small_feature | 6 | yellow | CLA **executed 2026-06-24**; review nudge 2026-06-28 — **cold**, wait on maintainer |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | mcp_adapter | 4 | red | Label gate (`kind/*` + `release-note`) — deprioritize |
| [stash #14](https://github.com/alash3al/stash/pull/14) | docs_setup | 9 | green | OPEN; warm maintainer — **wait on maintainer** |
| [basic-memory #1010](https://github.com/basicmachines-co/basic-memory/pull/1010) | narrow_bugfix | 7 | yellow | OPEN — uncredentialed project list; warm repo |
| [HeatWatch #20](https://github.com/castroquiles/HeatWatch/pull/20) | narrow_bugfix | 6 | yellow | OPEN — geo_utils off-by-one; **cold** |
| [hermes-agent #64281](https://github.com/NousResearch/hermes-agent/pull/64281) | mcp_adapter | 8 | green | Re-scope of #40737 (`config.yaml` policy); CI green — **wait on maintainer** |

**Desk rule:** No new upstream PRs while green lanes have maintainer-pending merges, unless a new candidate scores green *and* has no overlapping open PR in the same repo.

## Upstream PRs — actionable (our move)

*None.* Every open PR is maintainer-blocked as of 2026-07-14.

## Upstream PRs — waiting on maintainers (no move)

| PR | Status | Next step |
|----|--------|-----------|
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | `listThreadSessions` filter at HEAD; live `CHANGES_REQUESTED` | Maintainer to re-review/dismiss or merge |
| [codejail #309](https://github.com/openedx/codejail/pull/309) | CLA executed; `openedx/cla` SUCCESS; review nudge 2026-06-28 | Maintainer review (`mphilbrick211` / `@moisesgsalas`) |
| [stash #14](https://github.com/alash3al/stash/pull/14) | Docs-only SSE curl note; closes #11 | Maintainer review (`alash3al`) |
| [glapagos #20](https://github.com/castroquiles/glapagos/pull/20) | 9/9 checks green, mergeable | Maintainer review |
| [mcp-mem0 #18](https://github.com/coleam00/mcp-mem0/pull/18) | Mergeable; issue-linked; no review | Maintainer review (**cold**) |
| [PDFMathTranslate #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | Mergeable; no review | Maintainer review (**cold**) |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | Code clean; blocked on maintainer labels | Maintainer adds labels or deprioritize |
| [basic-memory #1010](https://github.com/basicmachines-co/basic-memory/pull/1010) | OPEN; warm repo (groksrc) | Maintainer review |
| [HeatWatch #20](https://github.com/castroquiles/HeatWatch/pull/20) | OPEN; no maintainer reply | Maintainer review (**cold**) |
| [hermes-agent #64281](https://github.com/NousResearch/hermes-agent/pull/64281) | OPEN; CI green; addresses #40737 config policy | Maintainer review (warm — sweeper engaged on prior PR) |

## Upstream outcomes — recently merged by maintainers

*Full auto-updated ledger: [`CONTRIBUTORS.md`](../CONTRIBUTORS.md). Recent merges since last desk pass:*

| PR | Note |
|----|------|
| [zeroc00I/DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) | CI publish workflow — merged 2026-07-08 |
| [mex-memory/mex #84](https://github.com/mex-memory/mex/pull/84) | MCP adapter — merged 2026-07-06 by theDakshJaitly |
| [Taiko2k/Tauon #2209](https://github.com/Taiko2k/Tauon/pull/2209) | Follow-on Tidal typing — merged 2026-07-02 |
| [Taiko2k/Tauon #2208](https://github.com/Taiko2k/Tauon/pull/2208) | Tidal return-type annotations — merged 2026-06-30 by C0rn3j |
| [moazbuilds/claudeclaw #239](https://github.com/moazbuilds/claudeclaw/pull/239) | TerrysPOV approved + merged 2026-06-28 |
| [moazbuilds/claudeclaw #240](https://github.com/moazbuilds/claudeclaw/pull/240) | docs_setup — TerrysPOV approved + merged 2026-06-28 |
| [moazbuilds/claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | narrow_bugfix — merged 2026-06-28 |
| [Filippo-Venturini/ctxvault #31](https://github.com/Filippo-Venturini/ctxvault/pull/31) | Remove stale `vault_config` reindex kwarg — merged 2026-06-17 |
| [max-rh/sshelf #3](https://github.com/max-rh/sshelf/pull/3) | Print generated SSH command from CLI |
| [liatrio-labs/claude-deep-review #5](https://github.com/liatrio-labs/claude-deep-review/pull/5) | Extract `dedup_by_id` into standalone module |
| [basicmachines-co/basic-memory #985](https://github.com/basicmachines-co/basic-memory/pull/985) | Promote first project when config default missing from DB |
| [Emerging-Rule/community #11](https://github.com/Emerging-Rule/community/pull/11) | Creature Lab CS showcase + science lesson |
| [manojmallick/sigmap #216](https://github.com/manojmallick/sigmap/pull/216) | Hot-cold cold signatures in bundled MCP server |
| [alash3al/stash #10](https://github.com/alash3al/stash/pull/10) | Escape LIKE wildcards in namespace path resolution |

*(Older merges remain in `CONTRIBUTORS.md`; this table keeps the recent set.)*

## Upstream outcomes — recently closed without merge

| PR | Note |
|----|------|
| [ComposioHQ/awesome-claude-skills #885](https://github.com/ComposioHQ/awesome-claude-skills/pull/885) | 10 dev-methodology skills listing — batch-closed 2026-06-15 |
| [alibaizhanov/mengram #40](https://github.com/alibaizhanov/mengram/pull/40) | CONTRIBUTING.md docs — batch-closed 2026-06-15 |
| [modelcontextprotocol/python-sdk #2640](https://github.com/modelcontextprotocol/python-sdk/pull/2640) | Propagate transport exceptions — closed 2026-06-15 |
| [ngrok/ngrok-python #159](https://github.com/ngrok/ngrok-python/pull/159) | `--log-level` parameter — batch-closed 2026-06-15 |
| [ngrok/ngrok-python #160](https://github.com/ngrok/ngrok-python/pull/160) | Type hints awaitable return — batch-closed 2026-06-15 |
| [NousResearch/hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | Dreaming plugin — closed `not_planned` (`env-var-for-config`); superseded by #64281 |

*See `CONTRIBUTORS.md` for the full closed-without-merge set.*

## Internal

- Provenance inventory: `chore/provenance-inventory-2026-06-03` branch / gh PR
- Kart/watchmen queue: [`audits/KART_FAILURE_MODES.md`](audits/KART_FAILURE_MODES.md)
