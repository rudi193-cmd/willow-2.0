# Open work (fleet backlog)

*Last updated: 2026-06-23 — upstream contributions desk pass (live `gh` reconciliation).*

**Strategy:** [`UPSTREAM_CONTRIBUTION_STRATEGY.md`](UPSTREAM_CONTRIBUTION_STRATEGY.md) · type ledger: [`upstream/type_ledger.json`](upstream/type_ledger.json)

> **2026-06-23 state change:** ctxvault #31 **merged**. Six long-stale maintainer-pending PRs
> batch-closed without merge on 2026-06-15 (~02:09 UTC): awesome-claude-skills #885,
> mengram #40, python-sdk #2640, ngrok-python #159 / #160 / #161. All currently-open PRs are
> **maintainer-blocked — nothing is blocked on us.** Green lane is clear; new green-lane work is unblocked.

## Upstream desk preflight

Score each open PR before opening new upstream work. Rubric: 5×0–2 → **green** 8–10 · **yellow** 5–7 · **red** 0–4.

| PR | Type | Score | Lane | Next action |
|----|------|-------|------|-------------|
| [claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | narrow_bugfix | 8 | green | Fix pushed `0c9cfea`; CHANGES_REQUESTED not yet dismissed (11d silent) — **re-request review** |
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | narrow_bugfix | 8 | green | Fix pushed `5a6e633`; CHANGES_REQUESTED not yet dismissed (11d silent) — **re-request review** |
| [claudeclaw #239](https://github.com/moazbuilds/claudeclaw/pull/239) | narrow_bugfix | 8 | green | CI green, no review yet — wait |
| [claudeclaw #240](https://github.com/moazbuilds/claudeclaw/pull/240) | docs_setup | 8 | green | CI green, no review yet — wait |
| [mcp-mem0 #18](https://github.com/coleam00/mcp-mem0/pull/18) | narrow_bugfix | 8 | green | Issue-linked (Fixes #3), mergeable, no review — wait |
| [DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) | ci_verify | 7 | yellow | CI publish workflow, mergeable, no review — wait (warm maintainer, 2 prior merges) |
| [PDFMathTranslate #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | small_feature | 6 | yellow | Mergeable, no review — wait |
| [mex #84](https://github.com/mex-memory/mex/pull/84) | mcp_adapter | 6 | yellow | REVIEW_REQUIRED, mergeable — wait |
| [codejail #309](https://github.com/openedx/codejail/pull/309) | small_feature | 6 | yellow | **CLA gate** — signed 2026-06-18 (rudi193@gmail.com); maintainer `mphilbrick211` active — ping once CLA clears |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | mcp_adapter | 4 | red | Rebased 2026-06-15; `check-pr-labels` FAILURE is a **maintainer-only label gate** (needs `kind/*` + `release-note`) — code clean, deprioritize |
| [hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | unsolicited_large_feature | 2 | red | No maintainer signal since 2026-06-08 — do not invest; consider withdrawing |

**Desk rule:** No new upstream PRs while green lanes have maintainer-pending merges, unless a new candidate scores green *and* has no overlapping open PR in the same repo. *(2026-06-23: green lane is clear of merge-pending blockers — new green-lane candidates are unblocked.)*

## Upstream PRs — actionable (our move)

| PR | Status | Next step |
|----|--------|-----------|
| [claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | Fix pushed `0c9cfea`; `claude-review` SUCCESS; review still CHANGES_REQUESTED | Re-request review from TerrysPOV (fix addressed 2026-06-12, undismissed) |
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | Fix pushed `5a6e633`; `claude-review` SUCCESS; review still CHANGES_REQUESTED | Re-request review from TerrysPOV (fix addressed 2026-06-12, undismissed) |
| [codejail #309](https://github.com/openedx/codejail/pull/309) | CLA signed 2026-06-18; maintainer `mphilbrick211` engaged; one CLA check FAILURE | Confirm CLA clears, then nudge `mphilbrick211` / `@moisesgsalas` |

## Upstream PRs — waiting on maintainers (no move)

| PR | Status | Next step |
|----|--------|-----------|
| [claudeclaw #239](https://github.com/moazbuilds/claudeclaw/pull/239) | CI green; mergeable; no review | Maintainer review |
| [claudeclaw #240](https://github.com/moazbuilds/claudeclaw/pull/240) | CI green; mergeable; no review | Maintainer review |
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
