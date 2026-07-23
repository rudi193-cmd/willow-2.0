# Contributors & acknowledgments

Willow 2.0 — local-first AI stack. PolyForm Noncommercial 1.0.0.

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
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | docs(schema-v2): mark open items 1–4 done — they shipped; only the auto-promote decision remains | [PR #21](https://github.com/almanac-data/almanac-template/pull/21) merged |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Make the Codex lane and control panel cross-platform | [PR #4](https://github.com/dpmadsen/multimodels-mcp/pull/4) merged |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Fix npm test runner so compiled tests actually execute | [PR #3](https://github.com/dpmadsen/multimodels-mcp/pull/3) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | fix(detect): Tier 2 comment guard for apiPatterns (closes #28) | [PR #30](https://github.com/Redential/redential-cli/pull/30) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Map official MCP SDK imports to ai/mcp | [PR #19](https://github.com/Redential/redential-cli/pull/19) merged |
| [Redential/redential-cli](https://github.com/Redential/redential-cli) | Redential | Add Model Context Protocol taxonomy slug | [PR #18](https://github.com/Redential/redential-cli/pull/18) merged |
| [AllHailSeizure/Imageination](https://github.com/AllHailSeizure/Imageination) | AllHailSeizure | docs: make setup commands portable | [PR #7](https://github.com/AllHailSeizure/Imageination/pull/7) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #10](https://github.com/almanac-data/economy-almanac/pull/10) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #4](https://github.com/almanac-data/agriculture-almanac/pull/4) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #4](https://github.com/almanac-data/education-almanac/pull/4) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #4](https://github.com/almanac-data/science-almanac/pull/4) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #4](https://github.com/almanac-data/justice-almanac/pull/4) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #4](https://github.com/almanac-data/transportation-almanac/pull/4) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #43](https://github.com/almanac-data/climate-almanac/pull/43) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #4](https://github.com/almanac-data/energy-almanac/pull/4) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #11](https://github.com/almanac-data/environment-almanac/pull/11) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #12](https://github.com/almanac-data/health-almanac/pull/12) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #10](https://github.com/almanac-data/civic-almanac/pull/10) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat: revised-vs-superseded disambiguation via lead-signature fingerprint (almanac-template#11 item 3) | [PR #20](https://github.com/almanac-data/almanac-template/pull/20) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #9](https://github.com/almanac-data/civic-almanac/pull/9) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #9](https://github.com/almanac-data/economy-almanac/pull/9) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #42](https://github.com/almanac-data/climate-almanac/pull/42) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #3](https://github.com/almanac-data/education-almanac/pull/3) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #10](https://github.com/almanac-data/environment-almanac/pull/10) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #3](https://github.com/almanac-data/energy-almanac/pull/3) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #3](https://github.com/almanac-data/science-almanac/pull/3) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #3](https://github.com/almanac-data/transportation-almanac/pull/3) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #3](https://github.com/almanac-data/agriculture-almanac/pull/3) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #11](https://github.com/almanac-data/health-almanac/pull/11) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #3](https://github.com/almanac-data/justice-almanac/pull/3) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat: archive-rot recheck for recovery[] candidates (almanac-template#11 item 2) | [PR #19](https://github.com/almanac-data/almanac-template/pull/19) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | test: revert propagate-engine verification marker | [PR #18](https://github.com/almanac-data/almanac-template/pull/18) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | test: verify propagate-engine fan-out (will revert) | [PR #17](https://github.com/almanac-data/almanac-template/pull/17) merged |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #1](https://github.com/almanac-data/transportation-almanac/pull/1) merged |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #1](https://github.com/almanac-data/science-almanac/pull/1) merged |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #1](https://github.com/almanac-data/justice-almanac/pull/1) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #9](https://github.com/almanac-data/health-almanac/pull/9) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #8](https://github.com/almanac-data/environment-almanac/pull/8) merged |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #1](https://github.com/almanac-data/energy-almanac/pull/1) merged |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #1](https://github.com/almanac-data/education-almanac/pull/1) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #7](https://github.com/almanac-data/economy-almanac/pull/7) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #40](https://github.com/almanac-data/climate-almanac/pull/40) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #7](https://github.com/almanac-data/civic-almanac/pull/7) merged |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | chore(schema): adopt v2 catalog schema + migrate entries | [PR #1](https://github.com/almanac-data/agriculture-almanac/pull/1) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat(schema): add v1->v2 catalog migration script | [PR #16](https://github.com/almanac-data/almanac-template/pull/16) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat(ci): add propagate-engine workflow to auto-PR engine changes to verticals | [PR #15](https://github.com/almanac-data/almanac-template/pull/15) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | chore: land recovery-bot commit onto main | [PR #14](https://github.com/almanac-data/almanac-template/pull/14) merged |
| [almanac-data/.github](https://github.com/almanac-data/.github) | almanac-data | docs: list six new almanac vertical stubs on org profile | [PR #2](https://github.com/almanac-data/.github/pull/2) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat(bot): recovery-candidate discovery via jeles-remote (#11 item 1) | [PR #13](https://github.com/almanac-data/almanac-template/pull/13) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat(schema): adopt catalog-entry v2 as canonical schema | [PR #12](https://github.com/almanac-data/almanac-template/pull/12) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat(schema): add catalog-entry v2 JSON Schema + gitignore .cursor overlay | [PR #9](https://github.com/almanac-data/almanac-template/pull/9) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | docs(schema): add catalog-entry v2 rationale (SCHEMA-V2.md) | [PR #8](https://github.com/almanac-data/almanac-template/pull/8) merged |
| [almanac-data/.github](https://github.com/almanac-data/.github) | almanac-data | docs: agent guide and fleet overlay gitignore | [PR #1](https://github.com/almanac-data/.github/pull/1) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | feat(check_links): headless-browser reachability fallback | [PR #39](https://github.com/almanac-data/climate-almanac/pull/39) merged |
| [Taiko2k/Tauon](https://github.com/Taiko2k/Tauon) | Taiko2k | fix(lyrics): use OggOpus for .opus tag writes (#2135) | [PR #2209](https://github.com/Taiko2k/Tauon/pull/2209) merged |
| [Taiko2k/Tauon](https://github.com/Taiko2k/Tauon) | Taiko2k | Fix Tidal return-type annotations: return_list yields track ids (list[int]) | [PR #2208](https://github.com/Taiko2k/Tauon/pull/2208) merged |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | feat: headless reachability fallback (propagated from template) | [PR #6](https://github.com/almanac-data/civic-almanac/pull/6) merged |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | feat: headless reachability fallback (propagated from template) | [PR #6](https://github.com/almanac-data/environment-almanac/pull/6) merged |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | feat: headless reachability fallback (propagated from template) | [PR #6](https://github.com/almanac-data/economy-almanac/pull/6) merged |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | feat: headless reachability fallback (propagated from template) | [PR #6](https://github.com/almanac-data/health-almanac/pull/6) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | feat: headless reachability fallback (propagated from template) | [PR #33](https://github.com/almanac-data/climate-almanac/pull/33) merged |
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | feat: headless reachability fallback | [PR #1](https://github.com/almanac-data/almanac-template/pull/1) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Point repo links at the almanac-data org | [PR #32](https://github.com/almanac-data/climate-almanac/pull/32) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Auto-open dead-link issues from the daily reachability probe | [PR #29](https://github.com/almanac-data/climate-almanac/pull/29) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Add GitHub issue forms for dataset suggestions and dead-link reports | [PR #28](https://github.com/almanac-data/climate-almanac/pull/28) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Add good first issues badge to README | [PR #27](https://github.com/almanac-data/climate-almanac/pull/27) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Automate daily link checks with reliable curl probes | [PR #3](https://github.com/almanac-data/climate-almanac/pull/3) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Seed catalog wave 1: 13 major climate datasets | [PR #2](https://github.com/almanac-data/climate-almanac/pull/2) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | Add agent guide, pyproject, and fleet development docs | [PR #1](https://github.com/almanac-data/climate-almanac/pull/1) merged |
| [Filippo-Venturini/ctxvault](https://github.com/Filippo-Venturini/ctxvault) | Filippo-Venturini | feat: configurable embedding model per vault (#18) | [PR #34](https://github.com/Filippo-Venturini/ctxvault/pull/34) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(cli): show configured project in list when uncredentialed (#1003) | [PR #1010](https://github.com/basicmachines-co/basic-memory/pull/1010) merged |
| [mex-memory/mex](https://github.com/mex-memory/mex) | mex-memory | feat: add packages/mex-mcp — MCP server for mex-agent | [PR #84](https://github.com/mex-memory/mex/pull/84) merged |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | ci: add GitHub Actions workflow to publish Docker image to ghcr.io | [PR #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) merged |
| [wanxingai/LightAgent](https://github.com/wanxingai/LightAgent) | wanxingai | docs: add vector memory adapter example | [PR #60](https://github.com/wanxingai/LightAgent/pull/60) merged |
| [shinpr/mcp-local-rag](https://github.com/shinpr/mcp-local-rag) | shinpr | fix: report removedChunks and existed from delete_file | [PR #152](https://github.com/shinpr/mcp-local-rag/pull/152) merged |
| [max-rh/sshelf](https://github.com/max-rh/sshelf) | max-rh | feat: print generated SSH command from CLI | [PR #3](https://github.com/max-rh/sshelf/pull/3) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | docs: add heartbeat example (partial #179) | [PR #240](https://github.com/moazbuilds/claudeclaw/pull/240) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | fix(discord): ignore thread recap system messages (#230) | [PR #239](https://github.com/moazbuilds/claudeclaw/pull/239) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix: promote first project when config default missing from DB (#974) | [PR #985](https://github.com/basicmachines-co/basic-memory/pull/985) merged |
| [Filippo-Venturini/ctxvault](https://github.com/Filippo-Venturini/ctxvault) | Filippo-Venturini | fix: remove stale reindex vault_config kwarg | [PR #31](https://github.com/Filippo-Venturini/ctxvault/pull/31) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | Add: Creature Lab CS showcase + Neva and Theo science lesson (grades 3–8) | [PR #11](https://github.com/Emerging-Rule/community/pull/11) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | fix(mcp): include hot-cold cold signatures in bundled server (#201) | [PR #216](https://github.com/manojmallick/sigmap/pull/216) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | fix(sessions): treat session.json without sessionId as absent (#228) | [PR #234](https://github.com/moazbuilds/claudeclaw/pull/234) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | fix(commands): resolve /context JSONL path without daemon cwd (#229) | [PR #233](https://github.com/moazbuilds/claudeclaw/pull/233) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | Example: Calibration Series (6–10 + Social Studies 6–8) | [PR #10](https://github.com/Emerging-Rule/community/pull/10) merged |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | fix(security): escape LIKE wildcards in namespace path resolution | [PR #10](https://github.com/alash3al/stash/pull/10) merged |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | docs: Ollama local-first setup + pipeline stage count alignment | [PR #9](https://github.com/alash3al/stash/pull/9) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | Example: AI Literacy 9-12 series + Scribe companion (Issue #5) | [PR #9](https://github.com/Emerging-Rule/community/pull/9) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | feat(research): AI and Education reading list for teachers | [PR #8](https://github.com/Emerging-Rule/community/pull/8) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | feat(lessons): The Scribe Who Forgot His Dreams — K-12 AI literacy (story) | [PR #7](https://github.com/Emerging-Rule/community/pull/7) merged |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | feat(plugins): dreaming memory consolidation (config.yaml re-scope) | [PR #64281](https://github.com/NousResearch/hermes-agent/pull/64281) open |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | docs: clarify that curl /sse holding open is expected SSE behavior (#11) | [PR #14](https://github.com/alash3al/stash/pull/14) open |
| [castroquiles/glapagos](https://github.com/castroquiles/glapagos) | castroquiles | feat(api): export committed OpenAPI spec and cover the API (#13) | [PR #20](https://github.com/castroquiles/glapagos/pull/20) open |
| [castroquiles/HeatWatch](https://github.com/castroquiles/HeatWatch) | castroquiles | fix(geo_utils): correct clip_array_to_bounds off-by-one; add geo_utils tests + NDVI no-data guard | [PR #20](https://github.com/castroquiles/HeatWatch/pull/20) open |
| [PDFMathTranslate/PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) | PDFMathTranslate | feat: mirror source directory tree in batch translation output | [PR #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) open |
| [openedx/codejail](https://github.com/openedx/codejail) | openedx | feat: introduce CodeJailConfig class; keep module-level backward compat | [PR #309](https://github.com/openedx/codejail/pull/309) open |
| [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) | coleam00 | fix: disable Mem0 telemetry via env (Fixes #3) | [PR #18](https://github.com/coleam00/mcp-mem0/pull/18) open |
| [kelos-dev/kanon](https://github.com/kelos-dev/kanon) | kelos-dev | Add repo-local project overlays (#33) | [PR #34](https://github.com/kelos-dev/kanon/pull/34) open |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Fix npm test runner so compiled tests actually execute | [PR #2](https://github.com/dpmadsen/multimodels-mcp/pull/2) closed |
| [dpmadsen/multimodels-mcp](https://github.com/dpmadsen/multimodels-mcp) | dpmadsen | Make the Codex lane and control panel cross-platform | [PR #1](https://github.com/dpmadsen/multimodels-mcp/pull/1) closed |
| [almanac-data/civic-almanac](https://github.com/almanac-data/civic-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #8](https://github.com/almanac-data/civic-almanac/pull/8) closed |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #41](https://github.com/almanac-data/climate-almanac/pull/41) closed |
| [almanac-data/environment-almanac](https://github.com/almanac-data/environment-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #9](https://github.com/almanac-data/environment-almanac/pull/9) closed |
| [almanac-data/justice-almanac](https://github.com/almanac-data/justice-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #2](https://github.com/almanac-data/justice-almanac/pull/2) closed |
| [almanac-data/transportation-almanac](https://github.com/almanac-data/transportation-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #2](https://github.com/almanac-data/transportation-almanac/pull/2) closed |
| [almanac-data/education-almanac](https://github.com/almanac-data/education-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #2](https://github.com/almanac-data/education-almanac/pull/2) closed |
| [almanac-data/science-almanac](https://github.com/almanac-data/science-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #2](https://github.com/almanac-data/science-almanac/pull/2) closed |
| [almanac-data/economy-almanac](https://github.com/almanac-data/economy-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #8](https://github.com/almanac-data/economy-almanac/pull/8) closed |
| [almanac-data/energy-almanac](https://github.com/almanac-data/energy-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #2](https://github.com/almanac-data/energy-almanac/pull/2) closed |
| [almanac-data/agriculture-almanac](https://github.com/almanac-data/agriculture-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #2](https://github.com/almanac-data/agriculture-almanac/pull/2) closed |
| [almanac-data/health-almanac](https://github.com/almanac-data/health-almanac) | almanac-data | chore(engine): propagate changes from almanac-template | [PR #10](https://github.com/almanac-data/health-almanac/pull/10) closed |
| [stevesolun/ctx](https://github.com/stevesolun/ctx) | stevesolun | fix: support networkx < 3.4 in node_link_data/node_link_graph calls | [PR #120](https://github.com/stevesolun/ctx/pull/120) closed |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | DeusData | fix: skip Antigravity IDE install roots during discovery | [PR #468](https://github.com/DeusData/codebase-memory-mcp/pull/468) closed |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(mcp): keep search index type in vector hydration | [PR #984](https://github.com/basicmachines-co/basic-memory/pull/984) closed |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(mcp): keep search index type in vector hydration | [PR #983](https://github.com/basicmachines-co/basic-memory/pull/983) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | feat(plugins): dreaming — automatic background memory consolidation | [PR #40737](https://github.com/NousResearch/hermes-agent/pull/40737) closed |
| [voidcraft-labs/commcare-nova](https://github.com/voidcraft-labs/commcare-nova) | voidcraft-labs | fix(mcp): sanitize Long-like values before Firestore writes | [PR #57](https://github.com/voidcraft-labs/commcare-nova/pull/57) closed |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | openclaw | fix(memory): do not filter FTS keyword search by embedding model (#48300) | [PR #90165](https://github.com/openclaw/openclaw/pull/90165) closed |


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
