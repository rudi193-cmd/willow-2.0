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
| [almanac-data/almanac-template](https://github.com/almanac-data/almanac-template) | almanac-data | docs(schema): add catalog-entry v2 rationale (SCHEMA-V2.md) | [PR #8](https://github.com/almanac-data/almanac-template/pull/8) merged |
| [almanac-data/.github](https://github.com/almanac-data/.github) | almanac-data | docs: agent guide and fleet overlay gitignore | [PR #1](https://github.com/almanac-data/.github/pull/1) merged |
| [almanac-data/climate-almanac](https://github.com/almanac-data/climate-almanac) | almanac-data | feat(check_links): headless-browser reachability fallback | [PR #39](https://github.com/almanac-data/climate-almanac/pull/39) merged |
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
| [wanxingai/LightAgent](https://github.com/wanxingai/LightAgent) | wanxingai | docs: add vector memory adapter example | [PR #60](https://github.com/wanxingai/LightAgent/pull/60) merged |
| [shinpr/mcp-local-rag](https://github.com/shinpr/mcp-local-rag) | shinpr | fix: report removedChunks and existed from delete_file | [PR #152](https://github.com/shinpr/mcp-local-rag/pull/152) merged |
| [max-rh/sshelf](https://github.com/max-rh/sshelf) | max-rh | feat: print generated SSH command from CLI | [PR #3](https://github.com/max-rh/sshelf/pull/3) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | docs: add heartbeat example (partial #179) | [PR #240](https://github.com/moazbuilds/claudeclaw/pull/240) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | fix(discord): ignore thread recap system messages (#230) | [PR #239](https://github.com/moazbuilds/claudeclaw/pull/239) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix: promote first project when config default missing from DB (#974) | [PR #985](https://github.com/basicmachines-co/basic-memory/pull/985) merged |
| [Filippo-Venturini/ctxvault](https://github.com/Filippo-Venturini/ctxvault) | Filippo-Venturini | fix: remove stale reindex vault_config kwarg | [PR #31](https://github.com/Filippo-Venturini/ctxvault/pull/31) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | Add: Creature Lab CS showcase + Neva and Theo science lesson (grades 3–8) | [PR #11](https://github.com/Emerging-Rule/community/pull/11) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | fix(mcp): include hot-cold cold signatures in bundled server (#201) | [PR #216](https://github.com/manojmallick/sigmap/pull/216) merged |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | fix(commands): resolve /context JSONL path without daemon cwd (#229) | [PR #233](https://github.com/moazbuilds/claudeclaw/pull/233) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | Example: Calibration Series (6–10 + Social Studies 6–8) | [PR #10](https://github.com/Emerging-Rule/community/pull/10) merged |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | fix(security): escape LIKE wildcards in namespace path resolution | [PR #10](https://github.com/alash3al/stash/pull/10) merged |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | docs: Ollama local-first setup + pipeline stage count alignment | [PR #9](https://github.com/alash3al/stash/pull/9) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | Example: AI Literacy 9-12 series + Scribe companion (Issue #5) | [PR #9](https://github.com/Emerging-Rule/community/pull/9) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | feat(research): AI and Education reading list for teachers | [PR #8](https://github.com/Emerging-Rule/community/pull/8) merged |
| [Emerging-Rule/community](https://github.com/Emerging-Rule/community) | Emerging-Rule | feat(lessons): The Scribe Who Forgot His Dreams — K-12 AI literacy (story) | [PR #7](https://github.com/Emerging-Rule/community/pull/7) merged |
| [Filippo-Venturini/ctxvault](https://github.com/Filippo-Venturini/ctxvault) | Filippo-Venturini | feat: expose indexed document text for recovery workflows (#22) | [PR #29](https://github.com/Filippo-Venturini/ctxvault/pull/29) merged |
| [RikyZ90/ShibaClaw](https://github.com/RikyZ90/ShibaClaw) | RikyZ90 | docs: Gateway WebSocket protocol contract (#26) | [PR #38](https://github.com/RikyZ90/ShibaClaw/pull/38) merged |
| [smaramwbc/statewave](https://github.com/smaramwbc/statewave) | smaramwbc | feat(server): add make test-cold for cold-install verification (#68) | [PR #154](https://github.com/smaramwbc/statewave/pull/154) merged |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | docs: post-install guide + fix MCP copy buttons (#6) | [PR #8](https://github.com/alash3al/stash/pull/8) merged |
| [Doorman11991/smallcode](https://github.com/Doorman11991/smallcode) | Doorman11991 | feat(skills): bundle Willow dev-methodology skill pack | [PR #32](https://github.com/Doorman11991/smallcode/pull/32) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(cli): ignore CancelledError in background task done callback (#839) | [PR #842](https://github.com/basicmachines-co/basic-memory/pull/842) merged |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | feat: OpenAI-compatible chat completions proxy (#1) | [PR #5](https://github.com/zeroc00I/DontFeedTheAI/pull/5) merged |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | docs: add MIT LICENSE file (#3) | [PR #4](https://github.com/zeroc00I/DontFeedTheAI/pull/4) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(mcp): restore write_note overwrite schema for external clients (#818) | [PR #841](https://github.com/basicmachines-co/basic-memory/pull/841) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | docs(installer): use pgvector image for Postgres compose | [PR #840](https://github.com/basicmachines-co/basic-memory/pull/840) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | fix(mcp): merge hot-cold cache and context-cold into MCP index | [PR #202](https://github.com/manojmallick/sigmap/pull/202) merged |
| [paulkaefer/cowsay-files](https://github.com/paulkaefer/cowsay-files) | paulkaefer | Add kidcat.cow and billcipher.cow | [PR #34](https://github.com/paulkaefer/cowsay-files/pull/34) merged |
| [liatrio-labs/claude-deep-review](https://github.com/liatrio-labs/claude-deep-review) | liatrio-labs | refactor: extract dedup_by_id from merge_findings into standalone module | [PR #5](https://github.com/liatrio-labs/claude-deep-review/pull/5) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | feat: Willow adapter for Postgres-backed knowledge store | [PR #145](https://github.com/manojmallick/sigmap/pull/145) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | feat: native Python AST extractor for accurate signature extraction | [PR #144](https://github.com/manojmallick/sigmap/pull/144) merged |
| [TensorBlock/awesome-mcp-servers](https://github.com/TensorBlock/awesome-mcp-servers) | TensorBlock | Add willow-1.7 — portless MCP server with PGP-signed authorization | [PR #401](https://github.com/TensorBlock/awesome-mcp-servers/pull/401) merged |
| [Taiko2k/Tauon](https://github.com/Taiko2k/Tauon) | Taiko2k | fix(lyrics): use OggOpus for .opus tag writes (#2135) | [PR #2209](https://github.com/Taiko2k/Tauon/pull/2209) open |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | docs: clarify that curl /sse holding open is expected SSE behavior (#11) | [PR #14](https://github.com/alash3al/stash/pull/14) open |
| [castroquiles/glapagos](https://github.com/castroquiles/glapagos) | castroquiles | feat(api): export committed OpenAPI spec and cover the API (#13) | [PR #20](https://github.com/castroquiles/glapagos/pull/20) open |
| [castroquiles/HeatWatch](https://github.com/castroquiles/HeatWatch) | castroquiles | fix(geo_utils): correct clip_array_to_bounds off-by-one; add geo_utils tests + NDVI no-data guard | [PR #20](https://github.com/castroquiles/HeatWatch/pull/20) open |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(cli): show configured project in list when uncredentialed (#1003) | [PR #1010](https://github.com/basicmachines-co/basic-memory/pull/1010) open |
| [mex-memory/mex](https://github.com/mex-memory/mex) | mex-memory | feat: add packages/mex-mcp — MCP server for mex-agent | [PR #84](https://github.com/mex-memory/mex/pull/84) open |
| [PDFMathTranslate/PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) | PDFMathTranslate | feat: mirror source directory tree in batch translation output | [PR #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) open |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | ci: add GitHub Actions workflow to publish Docker image to ghcr.io | [PR #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) open |
| [openedx/codejail](https://github.com/openedx/codejail) | openedx | feat: introduce CodeJailConfig class; keep module-level backward compat | [PR #309](https://github.com/openedx/codejail/pull/309) open |
| [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) | coleam00 | fix: disable Mem0 telemetry via env (Fixes #3) | [PR #18](https://github.com/coleam00/mcp-mem0/pull/18) open |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | feat(plugins): dreaming — automatic background memory consolidation | [PR #40737](https://github.com/NousResearch/hermes-agent/pull/40737) open |
| [kelos-dev/kanon](https://github.com/kelos-dev/kanon) | kelos-dev | Add repo-local project overlays (#33) | [PR #34](https://github.com/kelos-dev/kanon/pull/34) open |
| [moazbuilds/claudeclaw](https://github.com/moazbuilds/claudeclaw) | moazbuilds | fix(sessions): treat session.json without sessionId as absent (#228) | [PR #234](https://github.com/moazbuilds/claudeclaw/pull/234) open |
| [stevesolun/ctx](https://github.com/stevesolun/ctx) | stevesolun | fix: support networkx < 3.4 in node_link_data/node_link_graph calls | [PR #120](https://github.com/stevesolun/ctx/pull/120) closed |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | DeusData | fix: skip Antigravity IDE install roots during discovery | [PR #468](https://github.com/DeusData/codebase-memory-mcp/pull/468) closed |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(mcp): keep search index type in vector hydration | [PR #984](https://github.com/basicmachines-co/basic-memory/pull/984) closed |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(mcp): keep search index type in vector hydration | [PR #983](https://github.com/basicmachines-co/basic-memory/pull/983) closed |
| [voidcraft-labs/commcare-nova](https://github.com/voidcraft-labs/commcare-nova) | voidcraft-labs | fix(mcp): sanitize Long-like values before Firestore writes | [PR #57](https://github.com/voidcraft-labs/commcare-nova/pull/57) closed |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | openclaw | fix(memory): do not filter FTS keyword search by embedding model (#48300) | [PR #90165](https://github.com/openclaw/openclaw/pull/90165) closed |
| [alibaizhanov/mengram](https://github.com/alibaizhanov/mengram) | alibaizhanov | docs: add CONTRIBUTING.md with local setup and PR guidelines | [PR #40](https://github.com/alibaizhanov/mengram/pull/40) closed |
| [ogham-mcp/ogham-mcp](https://github.com/ogham-mcp/ogham-mcp) | ogham-mcp | feat: Memory Tool 6-op conformance CI (#52) | [PR #53](https://github.com/ogham-mcp/ogham-mcp/pull/53) closed |
| [holon-run/holon](https://github.com/holon-run/holon) | holon-run | fix: allow Sleep while waiting on same-WorkItem background command_task (#1416) | [PR #1435](https://github.com/holon-run/holon/pull/1435) closed |
| [abhixdd/ghgrab](https://github.com/abhixdd/ghgrab) | abhixdd | feat: Homebrew formula + agent integration docs (Willow) | [PR #65](https://github.com/abhixdd/ghgrab/pull/65) closed |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | ComposioHQ | feat: add 10 development methodology skills | [PR #885](https://github.com/ComposioHQ/awesome-claude-skills/pull/885) closed |
| [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) | Gentleman-Programming | fix(cloud): constant-time credential comparisons (#350) | [PR #399](https://github.com/Gentleman-Programming/engram/pull/399) closed |
| [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) | Gentleman-Programming | fix(mcp): allow scope=personal to search across projects | [PR #398](https://github.com/Gentleman-Programming/engram/pull/398) closed |
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | ngrok | docs: add an example for using ngrok with google colab | [PR #161](https://github.com/ngrok/ngrok-python/pull/161) closed |
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | ngrok | fix: update type hints to reflect awaitable return types for module methods | [PR #160](https://github.com/ngrok/ngrok-python/pull/160) closed |
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | ngrok | feat: add `--log-level` parameter to `ngrok.__main__` | [PR #159](https://github.com/ngrok/ngrok-python/pull/159) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | fix(auth): treat empty credential pool entries as unauthenticated in /model picker | [PR #28241](https://github.com/NousResearch/hermes-agent/pull/28241) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | fix(logging): include hermes_plugins.* in gateway.log component filter | [PR #28236](https://github.com/NousResearch/hermes-agent/pull/28236) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | fix(plugins): raise plugin discovery failures to WARNING level | [PR #28235](https://github.com/NousResearch/hermes-agent/pull/28235) closed |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | BerriAI | fix(bedrock,sagemaker): silence ModuleNotFoundError when botocore is not installed | [PR #28193](https://github.com/BerriAI/litellm/pull/28193) closed |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | modelcontextprotocol | fix(client): propagate transport exceptions in default message handler | [PR #2640](https://github.com/modelcontextprotocol/python-sdk/pull/2640) closed |
| [node9-ai/node9-proxy](https://github.com/node9-ai/node9-proxy) | node9-ai | feat(blast): add Willow sovereign stack sensitive paths | [PR #172](https://github.com/node9-ai/node9-proxy/pull/172) closed |
| [CinnamonInt/Cinnamonint](https://github.com/CinnamonInt/Cinnamonint) | CinnamonInt | feat: token_edges relationship discovery | [PR #2](https://github.com/CinnamonInt/Cinnamonint/pull/2) closed |
| [monologg/JointBERT](https://github.com/monologg/JointBERT) | monologg | feat: rule-based fallback predictor (no torch/transformers required) | [PR #36](https://github.com/monologg/JointBERT/pull/36) closed |
| [S1LV4/th0th](https://github.com/S1LV4/th0th) | S1LV4 | feat(packages/willow): Willow SOIL adapter for memory edge persistence | [PR #38](https://github.com/S1LV4/th0th/pull/38) closed |
| [irodion/adjoint](https://github.com/irodion/adjoint) | irodion | feat(store): Postgres-backed session store with LISTEN/NOTIFY | [PR #4](https://github.com/irodion/adjoint/pull/4) closed |
| [samballington/CodeWise](https://github.com/samballington/CodeWise) | samballington | feat(backends): PostgreSQL + pgvector backend | [PR #15](https://github.com/samballington/CodeWise/pull/15) closed |
| [rish-e/tokenpilot](https://github.com/rish-e/tokenpilot) | rish-e | feat: mtime-aware dedup tracker (session_dedup.py) | [PR #1](https://github.com/rish-e/tokenpilot/pull/1) closed |
| [irodion/adjoint](https://github.com/irodion/adjoint) | irodion | feat(memory): Norn PII scrubber — structural pass extending Redactor | [PR #3](https://github.com/irodion/adjoint/pull/3) closed |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | feat: add Willow regex patterns for SSN, PAN/Luhn, phone, AI API keys | [PR #2](https://github.com/zeroc00I/DontFeedTheAI/pull/2) closed |
| [aviv4339/claude-guard](https://github.com/aviv4339/claude-guard) | aviv4339 | feat: richer hook template with agent identity, depth guard, reflection detection | [PR #1](https://github.com/aviv4339/claude-guard/pull/1) closed |
| [cneiman/moonshine](https://github.com/cneiman/moonshine) | cneiman | feat(adapters): Postgres backend for warm/cold memory tiers | [PR #2](https://github.com/cneiman/moonshine/pull/2) closed |
| [m4cd4r4/claude-echoes](https://github.com/m4cd4r4/claude-echoes) | m4cd4r4 | feat(server): wire GIN index for hybrid BM25+pgvector RRF search | [PR #1](https://github.com/m4cd4r4/claude-echoes/pull/1) closed |
| [brainqub3/RLM](https://github.com/brainqub3/RLM) | brainqub3 | docs: KB-first MCP integration pattern as RLM variant | [PR #3](https://github.com/brainqub3/RLM/pull/3) closed |
| [Textualize/rich](https://github.com/Textualize/rich) | Textualize | feat(examples): safe_markup — escaping external content before Rich rendering | [PR #4092](https://github.com/Textualize/rich/pull/4092) closed |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | BerriAI | cookbook: routing to a custom fine-tuned GGUF model via Ollama | [PR #26307](https://github.com/BerriAI/litellm/pull/26307) closed |
| [Kludex/starlette](https://github.com/Kludex/starlette) | Kludex | docs: add FilesystemAuthBackend example to authentication guide | [PR #3249](https://github.com/Kludex/starlette/pull/3249) closed |
| [Textualize/textual](https://github.com/Textualize/textual) | Textualize | feat(examples): async message_feed with background worker and pause/resume | [PR #6510](https://github.com/Textualize/textual/pull/6510) closed |
| [ollama/ollama](https://github.com/ollama/ollama) | ollama | docs: add HuggingFace Hub direct GGUF pull pattern to import guide | [PR #15765](https://github.com/ollama/ollama/pull/15765) closed |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | modelcontextprotocol | feat(examples): postgres-backed MCP server with filesystem authorization | [PR #2494](https://github.com/modelcontextprotocol/python-sdk/pull/2494) closed |
| [TensorBlock/awesome-mcp-servers](https://github.com/TensorBlock/awesome-mcp-servers) | TensorBlock | feat: add willow-mcp to Knowledge Management & Memory | [PR #432](https://github.com/TensorBlock/awesome-mcp-servers/pull/432) closed |
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | punkpeye | feat: add willow-mcp to Knowledge & Memory 🤖🤖🤖 | [PR #5247](https://github.com/punkpeye/awesome-mcp-servers/pull/5247) closed |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | openclaw | feat(skill): add sap-enforcer — SAP/1.0 MCP tool authorization | [PR #69792](https://github.com/openclaw/openclaw/pull/69792) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | feat: Willow Kart task queue tool | [PR #11979](https://github.com/NousResearch/hermes-agent/pull/11979) closed |
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | punkpeye | Add willow-1.7 — portless MCP server with PGP-signed authorization | [PR #4991](https://github.com/punkpeye/awesome-mcp-servers/pull/4991) closed |
| [RyjoxTechnologies/Octopoda-OS](https://github.com/RyjoxTechnologies/Octopoda-OS) | RyjoxTechnologies | feat(brain): add DarkRadar fifth signal to BrainHub | [PR #1](https://github.com/RyjoxTechnologies/Octopoda-OS/pull/1) closed |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | openclaw | feat(skill): add willow-memory-health ClawHub skill | [PR #67789](https://github.com/openclaw/openclaw/pull/67789) closed |


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
