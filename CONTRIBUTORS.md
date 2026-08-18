# Contributors & acknowledgments

Willow 2.0 — local-first AI stack. Apache-2.0.

## Built by

- **USER** — architecture, knowledge graph, agent identity, fleet design

## Open Source — Used Directly

| Project | What Willow uses |
|---|---|
| [LiteLLM](https://github.com/BerriAI/litellm) (BerriAI) | Unified inference gateway — Ollama default + cloud provider abstraction |
| [Ollama](https://github.com/ollama/ollama) | Local-first LLM inference, default provider |
| [Textual](https://github.com/Textualize/textual) (Textualize) | Terminal dashboard UI framework |
| [mcp-proxy](https://github.com/TBXark/mcp-proxy) (TBXark) | MCP server aggregation pattern |
| [punkpeye/mcp-proxy](https://github.com/punkpeye/mcp-proxy) | stdio→HTTP/SSE MCP transport bridge |
| [FastMCP](https://github.com/jlowin/fastmcp) | MCP server framework |
| [psycopg2](https://github.com/psycopg/psycopg2) | Postgres adapter |
| [cryptography](https://github.com/pyca/cryptography) | Fernet vault encryption |

## Open Source — Patterns Learned From

| Project | What we learned |
|---|---|
| [SuperAGI](https://github.com/TransformerOptimus/SuperAGI) | Toolkit marketplace JSON seed pattern |
| [Khoj](https://github.com/khoj-ai/khoj) | Local-first multi-LLM agent architecture |
| [Open WebUI](https://github.com/open-webui/open-webui) | Multi-model Ollama integration patterns |
| [PrivateGPT](https://github.com/zylon-ai/private-gpt) | Local inference abstraction layer |
| [ClawHub](https://clawhub.ai) / [OpenClaw](https://github.com/openclaw/openclaw) | Skill registry protocol and distribution |

## Upstream Contributions

These projects power Willow. When their maintainers merge our PRs, they earn a place here.

| Project | Maintainer | What we contributed | Status |
|---------|-----------|---------------------|--------|
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | DeusData | fix(registry): drop suffix_match CALLS across language boundaries | [PR #1647](https://github.com/DeusData/codebase-memory-mcp/pull/1647) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | chore(repo): untrack sibling-checkout symlinks and ignore them | [PR #28](https://github.com/almanac-data/almanac-template/pull/28) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore(monitor): refresh observed from the daily probe | [PR #16](https://github.com/almanac-data/environment-almanac/pull/16) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore(monitor): refresh observed from the daily probe | [PR #15](https://github.com/almanac-data/economy-almanac/pull/15) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore(monitor): refresh observed from the daily probe | [PR #15](https://github.com/almanac-data/civic-almanac/pull/15) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore(monitor): refresh observed from the daily probe | [PR #21](https://github.com/almanac-data/health-almanac/pull/21) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore(monitor): refresh observed from the daily probe | [PR #52](https://github.com/almanac-data/climate-almanac/pull/52) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #9](https://github.com/almanac-data/transportation-almanac/pull/9) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #9](https://github.com/almanac-data/science-almanac/pull/9) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #9](https://github.com/almanac-data/justice-almanac/pull/9) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #9](https://github.com/almanac-data/energy-almanac/pull/9) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #9](https://github.com/almanac-data/education-almanac/pull/9) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #10](https://github.com/almanac-data/agriculture-almanac/pull/10) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #15](https://github.com/almanac-data/environment-almanac/pull/15) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #14](https://github.com/almanac-data/economy-almanac/pull/14) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #14](https://github.com/almanac-data/civic-almanac/pull/14) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #20](https://github.com/almanac-data/health-almanac/pull/20) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | fix: a connection failure is not HTTP 0, and not "reachable" | [PR #49](https://github.com/almanac-data/climate-almanac/pull/49) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | fix(check_links): a connection failure is not HTTP 0, and not "reachable" | [PR #27](https://github.com/almanac-data/almanac-template/pull/27) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #8](https://github.com/almanac-data/transportation-almanac/pull/8) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #8](https://github.com/almanac-data/science-almanac/pull/8) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #8](https://github.com/almanac-data/justice-almanac/pull/8) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #8](https://github.com/almanac-data/energy-almanac/pull/8) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #8](https://github.com/almanac-data/education-almanac/pull/8) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #9](https://github.com/almanac-data/agriculture-almanac/pull/9) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #14](https://github.com/almanac-data/environment-almanac/pull/14) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #13](https://github.com/almanac-data/economy-almanac/pull/13) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #13](https://github.com/almanac-data/civic-almanac/pull/13) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #48](https://github.com/almanac-data/climate-almanac/pull/48) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | fix: link-check survives repos where Actions may not open PRs | [PR #19](https://github.com/almanac-data/health-almanac/pull/19) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | fix(link-check): survive repos where Actions may not open PRs | [PR #26](https://github.com/almanac-data/almanac-template/pull/26) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #6](https://github.com/almanac-data/transportation-almanac/pull/6) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #6](https://github.com/almanac-data/science-almanac/pull/6) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #6](https://github.com/almanac-data/justice-almanac/pull/6) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #6](https://github.com/almanac-data/energy-almanac/pull/6) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #6](https://github.com/almanac-data/education-almanac/pull/6) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #13](https://github.com/almanac-data/environment-almanac/pull/13) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #12](https://github.com/almanac-data/economy-almanac/pull/12) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #12](https://github.com/almanac-data/civic-almanac/pull/12) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #7](https://github.com/almanac-data/agriculture-almanac/pull/7) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore: propagate engine from almanac-template (observed automation) | [PR #47](https://github.com/almanac-data/climate-almanac/pull/47) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore: propagate engine from almanac-template (AGENTS.md v2 + observed automation) | [PR #18](https://github.com/almanac-data/health-almanac/pull/18) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | docs: bring AGENTS.md to schema v2, keeping this vertical's own voice | [PR #46](https://github.com/almanac-data/climate-almanac/pull/46) merged |
| [almanac-data/almanac-data](https://github.com/almanac-data/almanac-data) | almanac-data | feat(propagate): carry AGENTS.md; finalize the org .github drafts | [PR #3](https://github.com/almanac-data/almanac-data/pull/3) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat: make AGENTS.md propagatable, and let the daily probe record what it saw | [PR #24](https://github.com/almanac-data/almanac-template/pull/24) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #5](https://github.com/almanac-data/transportation-almanac/pull/5) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #5](https://github.com/almanac-data/science-almanac/pull/5) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #5](https://github.com/almanac-data/justice-almanac/pull/5) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #12](https://github.com/almanac-data/environment-almanac/pull/12) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #5](https://github.com/almanac-data/energy-almanac/pull/5) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #5](https://github.com/almanac-data/education-almanac/pull/5) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #11](https://github.com/almanac-data/economy-almanac/pull/11) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + SCHEMA-V2) | [PR #45](https://github.com/almanac-data/climate-almanac/pull/45) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #11](https://github.com/almanac-data/civic-almanac/pull/11) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #6](https://github.com/almanac-data/agriculture-almanac/pull/6) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore: propagate engine from almanac-template (observed writer + v2 docs) | [PR #17](https://github.com/almanac-data/health-almanac/pull/17) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | docs: bring CONTRIBUTING.md to schema v2, keeping this vertical's own voice | [PR #44](https://github.com/almanac-data/climate-almanac/pull/44) merged |
| [almanac-data/almanac-data](https://github.com/almanac-data/almanac-data) | almanac-data | feat(propagate): carry CONTRIBUTING.md and SCHEMA-V2.md, with a local-override escape hatch | [PR #2](https://github.com/almanac-data/almanac-data/pull/2) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat(check_links): actually write `observed`, and correct the claim that it already did | [PR #23](https://github.com/almanac-data/almanac-template/pull/23) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | docs: make `observed` machine-written by convention, not just by schema | [PR #22](https://github.com/almanac-data/almanac-template/pull/22) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Document exit-code contract for scripting and CI (#29) | [PR #57](https://github.com/Redential/redential-cli/pull/57) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Auth flow structural detection (session, oauth, jwt-refresh) | [PR #54](https://github.com/Redential/redential-cli/pull/54) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Taxonomy 1.8.0: auth flow slugs (session, oauth, jwt-refresh) | [PR #53](https://github.com/Redential/redential-cli/pull/53) merged |
| [almanac-data/almanac-data](https://github.com/almanac-data/almanac-data) | almanac-data | docs: document full almanac fleet project sync | [PR #1](https://github.com/almanac-data/almanac-data/pull/1) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | test: RFC #13 fixture backdated-segment negative contract | [PR #39](https://github.com/Redential/redential-cli/pull/39) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | docs: RFC #13 vault anchor record schema (discussion draft) | [PR #38](https://github.com/Redential/redential-cli/pull/38) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | docs(schema-v2): mark open items 1–4 done — they shipped; only the auto-promote decision remains | [PR #21](https://github.com/almanac-data/almanac-template/pull/21) merged |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Make the Codex lane and control panel cross-platform | [PR #4](https://github.com/dpmadsen/multimodels-mcp/pull/4) merged |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Fix npm test runner so compiled tests actually execute | [PR #3](https://github.com/dpmadsen/multimodels-mcp/pull/3) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | fix(detect): Tier 2 comment guard for apiPatterns (closes #28) | [PR #30](https://github.com/Redential/redential-cli/pull/30) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Map official MCP SDK imports to ai/mcp | [PR #19](https://github.com/Redential/redential-cli/pull/19) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Add Model Context Protocol taxonomy slug | [PR #18](https://github.com/Redential/redential-cli/pull/18) merged |
| [AllHailSeizure/Imageination](https://github.com/AllHailSeizure/Imageination) | AllHailSeizure | docs: make setup commands portable | [PR #7](https://github.com/AllHailSeizure/Imageination/pull/7) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | feat(http): honor HTTP_PROXY/HTTPS_PROXY/NO_PROXY on login and submit | [PR #84](https://github.com/Redential/redential-cli/pull/84) open |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | feat(plugins): dreaming memory consolidation (config.yaml re-scope) | [PR #64281](https://github.com/NousResearch/hermes-agent/pull/64281) open |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Fix npm test runner so compiled tests actually execute | [PR #2](https://github.com/dpmadsen/multimodels-mcp/pull/2) closed |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Make the Codex lane and control panel cross-platform | [PR #1](https://github.com/dpmadsen/multimodels-mcp/pull/1) closed |


## Contributors to Willow

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

Forkers and contributors to **willow-2.0** and earlier lines. The fork-watcher workflow updates this table when you contribute back.

## MCP ecosystem

Willow speaks [Model Context Protocol](https://modelcontextprotocol.io).

Listed on [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) and [ClawHub](https://clawhub.ai).

## License

See [`LICENSE`](LICENSE).

---

*Plant the tree. Tend the roots. Let nothing be lost.*
