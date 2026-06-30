# Open work (fleet backlog)

*Last updated: 2026-06-30 — upstream desk touch (stash #14 + Tauon #2208 merged).*

**Strategy:** [`UPSTREAM_CONTRIBUTION_STRATEGY.md`](UPSTREAM_CONTRIBUTION_STRATEGY.md) · type ledger: [`upstream/type_ledger.json`](upstream/type_ledger.json)

> **2026-06-30 state change:** [Taiko2k/Tauon #2208](https://github.com/Taiko2k/Tauon/pull/2208) **merged** (Tidal return-type annotations toward #1338). [alash3al/stash #14](https://github.com/alash3al/stash/pull/14) **opened** (docs_setup — SSE curl troubleshooting, closes #11); issue follow-up posted 2026-06-30 — **wait on maintainer**.
>
> **2026-06-29 state change:** claudeclaw **#239 and #240 merged** (TerrysPOV approved + merged
> 2026-06-28). claudeclaw **#234** — the `listThreadSessions` filter TerrysPOV requested is
> already at HEAD (`a9eb7cb`, shipped under `54854a9`); his 2026-06-28 `CHANGES_REQUESTED` was
> filed against the parent commit `5a6e6336` and is now **stale** — needs maintainer
> re-review/dismissal, nothing on us. codejail **#309** CLA **executed 2026-06-24**; review
> nudge posted 2026-06-28 — maintainer's court. **Every open PR is maintainer-blocked —
> nothing is blocked on us.** Green lane is clear; new green-lane work is unblocked.
>
> **2026-06-23 state change:** ctxvault #31 **merged**. Six long-stale maintainer-pending PRs
> batch-closed without merge on 2026-06-15 (~02:09 UTC): awesome-claude-skills #885,
> mengram #40, python-sdk #2640, ngrok-python #159 / #160 / #161.

## Upstream desk preflight

Score each open PR before opening new upstream work. Rubric: 5×0–2 → **green** 8–10 · **yellow** 5–7 · **red** 0–4.

| PR | Type | Score | Lane | Next action |
|----|------|-------|------|-------------|
| [claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | narrow_bugfix | 8 | green | **MERGED 2026-06-28** ✓ |
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | narrow_bugfix | 8 | green | `listThreadSessions` filter at HEAD (`a9eb7cb`/`54854a9`); 3/3 checks green; TerrysPOV's 06-28 CHANGES_REQUESTED is **stale** (filed vs parent `5a6e6336`) — **wait on maintainer** re-review/dismiss |
| [claudeclaw #239](https://github.com/moazbuilds/claudeclaw/pull/239) | narrow_bugfix | 8 | green | **MERGED 2026-06-28** ✓ |
| [claudeclaw #240](https://github.com/moazbuilds/claudeclaw/pull/240) | docs_setup | 8 | green | **MERGED 2026-06-28** ✓ |
| [mcp-mem0 #18](https://github.com/coleam00/mcp-mem0/pull/18) | narrow_bugfix | 8 | green | Issue-linked (Fixes #3), mergeable, no review — wait |
| [DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) | ci_verify | 7 | yellow | CI publish workflow, mergeable, no review — wait (warm maintainer, 2 prior merges) |
| [PDFMathTranslate #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | small_feature | 6 | yellow | Mergeable, no review — wait |
| [mex #84](https://github.com/mex-memory/mex/pull/84) | mcp_adapter | 6 | yellow | REVIEW_REQUIRED, mergeable — wait |
| [codejail #309](https://github.com/openedx/codejail/pull/309) | small_feature | 6 | yellow | CLA **executed 2026-06-24**; `openedx/cla` check now SUCCESS; review nudge posted 2026-06-28 — **wait on maintainer** (`mphilbrick211` / `@moisesgsalas`) |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | mcp_adapter | 4 | red | Rebased 2026-06-15; `check-pr-labels` FAILURE is a **maintainer-only label gate** (needs `kind/*` + `release-note`) — code clean, deprioritize |
| [stash #14](https://github.com/alash3al/stash/pull/14) | docs_setup | 9 | green | OPEN 2026-06-30; +17 lines `GETTING_STARTED.md` Troubleshooting; closes #11; warm maintainer (3 prior merges); no CI gate — **wait on maintainer** |
| [hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | unsolicited_large_feature | 2 | red | No maintainer signal since 2026-06-08 — do not invest; consider withdrawing |

**Desk rule:** No new upstream PRs while green lanes have maintainer-pending merges, unless a new candidate scores green *and* has no overlapping open PR in the same repo. *(2026-06-23: green lane is clear of merge-pending blockers — new green-lane candidates are unblocked.)*

## Upstream PRs — actionable (our move)

*None.* Every open PR is maintainer-blocked as of 2026-06-29. Green lane is clear — to make progress, open a **new** green-lane contribution (see strategy doc + type ledger).

## Upstream PRs — waiting on maintainers (no move)

| PR | Status | Next step |
|----|--------|-----------|
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | `listThreadSessions` filter at HEAD (`a9eb7cb`/`54854a9`); 3/3 checks green; TerrysPOV's 06-28 CHANGES_REQUESTED filed vs parent `5a6e6336` is stale; comment posted 2026-06-28 | Maintainer to re-review/dismiss stale CHANGES_REQUESTED or merge |
| [codejail #309](https://github.com/openedx/codejail/pull/309) | CLA executed 2026-06-24; `openedx/cla` check SUCCESS; review nudge posted 2026-06-28; `mphilbrick211` engaged | Maintainer review (`mphilbrick211` / `@moisesgsalas`) |
| [stash #14](https://github.com/alash3al/stash/pull/14) | Docs-only SSE curl note; closes #11; issue thread linked 2026-06-30 | Maintainer review (`alash3al`) |
| [glapagos #20](https://github.com/castroquiles/glapagos/pull/20) | Lint was red (latent black/flake8/mypy conflicts); fix `628a9dd` 2026-06-28 — now 9/9 checks green, mergeable | Maintainer review |
| [mcp-mem0 #18](https://github.com/coleam00/mcp-mem0/pull/18) | Mergeable; issue-linked; no review | Maintainer review |
| [PDFMathTranslate #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | Mergeable; no review | Maintainer review |
| [mex #84](https://github.com/mex-memory/mex/pull/84) | Mergeable; REVIEW_REQUIRED | Maintainer review |
| [DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) | Mergeable; no review | Maintainer review |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | Code clean; blocked on maintainer label assignment | Maintainer adds labels (or deprioritize) |
| [hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | Open, no maintainer signal | Maintainer review (red lane — low priority) |

## Upstream outcomes — recently merged by maintainers

*Full auto-updated ledger: [`CONTRIBUTORS.md`](../CONTRIBUTORS.md). Recent merges since last desk pass:*

| PR | Note |
|----|------|
| [Taiko2k/Tauon #2208](https://github.com/Taiko2k/Tauon/pull/2208) | Tidal return-type annotations (`list[TrackClass]` → `list[int]`); merged 2026-06-30 by C0rn3j |
| [moazbuilds/claudeclaw #239](https://github.com/moazbuilds/claudeclaw/pull/239) | TerrysPOV approved + merged 2026-06-28 |
| [moazbuilds/claudeclaw #240](https://github.com/moazbuilds/claudeclaw/pull/240) | docs_setup — TerrysPOV approved + merged 2026-06-28 |
| [moazbuilds/claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | narrow_bugfix — merged 2026-06-28 |
| [Filippo-Venturini/ctxvault #31](https://github.com/Filippo-Venturini/ctxvault/pull/31) | Remove stale `vault_config` reindex kwarg — merged 2026-06-17 by Filippo-Venturini |
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
| [ComposioHQ/awesome-claude-skills #885](https://github.com/ComposioHQ/awesome-claude-skills/pull/885) | 10 dev-methodology skills listing — batch-closed 2026-06-15 (was `ready-to-merge`, no maintainer action) |
| [alibaizhanov/mengram #40](https://github.com/alibaizhanov/mengram/pull/40) | CONTRIBUTING.md docs — batch-closed 2026-06-15 |
| [modelcontextprotocol/python-sdk #2640](https://github.com/modelcontextprotocol/python-sdk/pull/2640) | Propagate transport exceptions in default message handler — closed 2026-06-15 (megarepo, 20 failing checks) |
| [ngrok/ngrok-python #159](https://github.com/ngrok/ngrok-python/pull/159) | `--log-level` parameter for `__main__` — batch-closed 2026-06-15 |
| [ngrok/ngrok-python #160](https://github.com/ngrok/ngrok-python/pull/160) | Type hints reflect awaitable return — batch-closed 2026-06-15 |
| [ngrok/ngrok-python #161](https://github.com/ngrok/ngrok-python/pull/161) | ngrok + Google Colab example — batch-closed 2026-06-15 |

*See `CONTRIBUTORS.md` for the full closed-without-merge set (45 total).*

## Internal

- Provenance inventory: `chore/provenance-inventory-2026-06-03` branch / gh PR
