# Open work (fleet backlog)

*Last updated: 2026-06-12 — upstream contributions desk pass.*

**Strategy:** [`UPSTREAM_CONTRIBUTION_STRATEGY.md`](UPSTREAM_CONTRIBUTION_STRATEGY.md) · type ledger: [`upstream/type_ledger.json`](upstream/type_ledger.json)

## Upstream desk preflight

Score each open PR before opening new upstream work. Rubric: 5×0–2 → **green** 8–10 · **yellow** 5–7 · **red** 0–4.

| PR | Type | Score | Lane | Next action |
|----|------|-------|------|-------------|
| [claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | narrow_bugfix | 9 | green | Wait for TerrysPOV re-review (fix pushed) |
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | narrow_bugfix | 9 | green | Wait for TerrysPOV re-review (fix pushed) |
| [claude-deep-review #5](https://github.com/liatrio-labs/claude-deep-review/pull/5) | narrow_bugfix | 7 | yellow | Wait for leehopper re-review |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | mcp_adapter | 3 | red | Blocked on maintainer labels |
| [awesome-claude-skills #885](https://github.com/ComposioHQ/awesome-claude-skills/pull/885) | listing_awesome | 6 | yellow | Wait for maintainer merge |
| [mengram #40](https://github.com/alibaizhanov/mengram/pull/40) | docs_setup | 7 | yellow | Maintainer review (pinged 2026-06-04) |
| [hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | unsolicited_large_feature | 2 | red | No maintainer signal — do not invest further |
| [python-sdk #2640](https://github.com/modelcontextprotocol/python-sdk/pull/2640) | narrow_bugfix | 6 | yellow | Maintainer review; megarepo — comment if stale |
| [ngrok-python #159–161](https://github.com/ngrok/ngrok-python/pulls) | docs_setup / narrow_bugfix | 5 | yellow | Maintainer review |

**Desk rule:** No new upstream PRs while green lanes have maintainer-pending merges, unless a new candidate scores green *and* has no overlapping open PR in the same repo.

## Upstream PRs — actionable

| PR | Status | Next step |
|----|--------|-----------|
| [claudeclaw #233](https://github.com/moazbuilds/claudeclaw/pull/233) | Fix pushed `0c9cfea`; `claude-review` pass; CHANGES_REQUESTED | Wait for TerrysPOV re-review |
| [claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | Fix pushed `5a6e633`; `claude-review` pass; CHANGES_REQUESTED | Wait for TerrysPOV re-review |
| [claude-deep-review #5](https://github.com/liatrio-labs/claude-deep-review/pull/5) | Scoped to `dedup_by_id`; portable test fixed; CodeRabbit pass; CHANGES_REQUESTED | Wait for leehopper re-review |
| [kanon #34](https://github.com/kelos-dev/kanon/pull/34) | Blocked on `needs-kind`, `needs-release-note`, `needs-triage` labels | Maintainer must apply labels (suggested `kind/api` + `release-note` in thread) |

## Upstream PRs — waiting on maintainers

| PR | Status | Next step |
|----|--------|-----------|
| [awesome-claude-skills #885](https://github.com/ComposioHQ/awesome-claude-skills/pull/885) | `ready-to-merge`; mergeable | Maintainer merge |
| [mengram #40](https://github.com/alibaizhanov/mengram/pull/40) | Pinged 2026-06-04 | Maintainer review |
| [hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | Open, no comments | Maintainer review |
| [python-sdk #2640](https://github.com/modelcontextprotocol/python-sdk/pull/2640) | Open, no comments | Maintainer review |
| [ngrok-python #159–161](https://github.com/ngrok/ngrok-python/pulls) | Rebased May 20; open | Maintainer review |

## Upstream outcomes — merged by maintainers

*Full auto-updated ledger: [`CONTRIBUTORS.md`](../CONTRIBUTORS.md). Below is the current merged set from that tracker.*

| PR | Note |
|----|------|
| [Emerging-Rule/community #11](https://github.com/Emerging-Rule/community/pull/11) | Creature Lab CS showcase + Neva and Theo science lesson |
| [manojmallick/sigmap #216](https://github.com/manojmallick/sigmap/pull/216) | Hot-cold cold signatures in bundled MCP server |
| [Emerging-Rule/community #10](https://github.com/Emerging-Rule/community/pull/10) | Calibration Series (6–10 + Social Studies 6–8) |
| [alash3al/stash #10](https://github.com/alash3al/stash/pull/10) | Escape LIKE wildcards in namespace path resolution |
| [alash3al/stash #9](https://github.com/alash3al/stash/pull/9) | Ollama local-first setup + pipeline stage alignment |
| [Emerging-Rule/community #9](https://github.com/Emerging-Rule/community/pull/9) | AI Literacy 9-12 series + Scribe companion |
| [Emerging-Rule/community #8](https://github.com/Emerging-Rule/community/pull/8) | AI and Education reading list for teachers |
| [Emerging-Rule/community #7](https://github.com/Emerging-Rule/community/pull/7) | The Scribe Who Forgot His Dreams — K-12 AI literacy story |
| [Filippo-Venturini/ctxvault #29](https://github.com/Filippo-Venturini/ctxvault/pull/29) | Expose indexed document text for recovery workflows |
| [RikyZ90/ShibaClaw #38](https://github.com/RikyZ90/ShibaClaw/pull/38) | Gateway WebSocket protocol contract docs |
| [smaramwbc/statewave #154](https://github.com/smaramwbc/statewave/pull/154) | `make test-cold` for cold-install verification |
| [alash3al/stash #8](https://github.com/alash3al/stash/pull/8) | Post-install guide + MCP copy-button fix |
| [Doorman11991/smallcode #32](https://github.com/Doorman11991/smallcode/pull/32) | Willow dev-methodology skill pack |
| [basicmachines-co/basic-memory #842](https://github.com/basicmachines-co/basic-memory/pull/842) | Ignore `CancelledError` in background task callback |
| [basicmachines-co/basic-memory #841](https://github.com/basicmachines-co/basic-memory/pull/841) | Restore `write_note` overwrite schema for external clients |
| [basicmachines-co/basic-memory #840](https://github.com/basicmachines-co/basic-memory/pull/840) | pgvector image for Postgres compose |
| [zeroc00I/DontFeedTheAI #5](https://github.com/zeroc00I/DontFeedTheAI/pull/5) | OpenAI-compatible chat completions proxy |
| [zeroc00I/DontFeedTheAI #4](https://github.com/zeroc00I/DontFeedTheAI/pull/4) | MIT LICENSE file |
| [manojmallick/sigmap #202](https://github.com/manojmallick/sigmap/pull/202) | Merge hot-cold cache + context-cold into MCP index |
| [paulkaefer/cowsay-files #34](https://github.com/paulkaefer/cowsay-files/pull/34) | kidcat.cow and billcipher.cow |
| [manojmallick/sigmap #145](https://github.com/manojmallick/sigmap/pull/145) | Willow adapter for Postgres-backed knowledge store |
| [manojmallick/sigmap #144](https://github.com/manojmallick/sigmap/pull/144) | Native Python AST extractor |
| [TensorBlock/awesome-mcp-servers #401](https://github.com/TensorBlock/awesome-mcp-servers/pull/401) | willow-1.7 listing |

## Upstream outcomes — closed without merge

| PR | Note |
|----|------|
| [openclaw/openclaw #90165](https://github.com/openclaw/openclaw/pull/90165) | FTS keyword search should not filter by embedding model |
| [voidcraft-labs/commcare-nova #57](https://github.com/voidcraft-labs/commcare-nova/pull/57) | Sanitize Long-like values before Firestore writes |
| [ogham-mcp/ogham-mcp #53](https://github.com/ogham-mcp/ogham-mcp/pull/53) | Memory Tool 6-op conformance CI |
| [holon-run/holon #1435](https://github.com/holon-run/holon/pull/1435) | Allow Sleep while waiting on background `command_task` |
| [abhixdd/ghgrab #65](https://github.com/abhixdd/ghgrab/pull/65) | Homebrew formula + agent integration docs |
| [Gentleman-Programming/engram #399](https://github.com/Gentleman-Programming/engram/pull/399) | Constant-time credential comparisons |
| [Gentleman-Programming/engram #398](https://github.com/Gentleman-Programming/engram/pull/398) | `scope=personal` search across projects |
| [NousResearch/hermes-agent #28241](https://github.com/NousResearch/hermes-agent/pull/28241) | Empty credential pool entries in `/model` picker |
| [NousResearch/hermes-agent #28236](https://github.com/NousResearch/hermes-agent/pull/28236) | `hermes_plugins.*` in gateway.log filter |
| [NousResearch/hermes-agent #28235](https://github.com/NousResearch/hermes-agent/pull/28235) | Plugin discovery failures → WARNING |
| [BerriAI/litellm #28193](https://github.com/BerriAI/litellm/pull/28193) | Silence botocore `ModuleNotFoundError` on bedrock/sagemaker |
| [node9-ai/node9-proxy #172](https://github.com/node9-ai/node9-proxy/pull/172) | Willow sovereign stack sensitive paths in blast |
| [Textualize/rich #4092](https://github.com/Textualize/rich/pull/4092) | `safe_markup` — escape external content before Rich render |
| [BerriAI/litellm #26307](https://github.com/BerriAI/litellm/pull/26307) | Custom fine-tuned GGUF via Ollama cookbook |
| [Textualize/textual #6510](https://github.com/Textualize/textual/pull/6510) | Async `message_feed` with pause/resume |
| [ollama/ollama #15765](https://github.com/ollama/ollama/pull/15765) | HuggingFace Hub direct GGUF pull pattern |
| [modelcontextprotocol/python-sdk #2494](https://github.com/modelcontextprotocol/python-sdk/pull/2494) | Postgres-backed MCP server example |
| [openclaw/openclaw #69792](https://github.com/openclaw/openclaw/pull/69792) | `sap-enforcer` skill |
| [NousResearch/hermes-agent #11979](https://github.com/NousResearch/hermes-agent/pull/11979) | Willow Kart task queue tool |
| [openclaw/openclaw #67789](https://github.com/openclaw/openclaw/pull/67789) | `willow-memory-health` ClawHub skill |

*38 closed-without-merge PRs total in `CONTRIBUTORS.md`; table above lists the notable recent ones. See the tracker for the full set (JointBERT, th0th, adjoint, moonshine, etc.).*

## Internal

- Provenance inventory: `chore/provenance-inventory-2026-06-03` branch / gh PR
