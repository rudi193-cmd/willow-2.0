# Contributors & acknowledgments

Willow 2.0 — local-first AI stack. PolyForm Noncommercial 1.0.0.

## Built by

- **Sean Campbell** — architecture, knowledge graph, agent identity, fleet design

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
| [RikyZ90/ShibaClaw](https://github.com/RikyZ90/ShibaClaw) | RikyZ90 | docs: Gateway WebSocket protocol contract (#26) | [PR #38](https://github.com/RikyZ90/ShibaClaw/pull/38) merged |
| [smaramwbc/statewave](https://github.com/smaramwbc/statewave) | smaramwbc | feat(server): add make test-cold for cold-install verification (#68) | [PR #154](https://github.com/smaramwbc/statewave/pull/154) merged |
| [Doorman11991/smallcode](https://github.com/Doorman11991/smallcode) | Doorman11991 | feat(skills): bundle Willow dev-methodology skill pack | [PR #32](https://github.com/Doorman11991/smallcode/pull/32) merged |
| [doobidoo/mcp-memory-service](https://github.com/doobidoo/mcp-memory-service) | doobidoo | docs: contradiction resolution approaches (RFC #732 reference) | [PR #984](https://github.com/doobidoo/mcp-memory-service/pull/984) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(cli): ignore CancelledError in background task done callback (#839) | [PR #842](https://github.com/basicmachines-co/basic-memory/pull/842) merged |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | feat: OpenAI-compatible chat completions proxy (#1) | [PR #5](https://github.com/zeroc00I/DontFeedTheAI/pull/5) merged |
| [zeroc00I/DontFeedTheAI](https://github.com/zeroc00I/DontFeedTheAI) | zeroc00I | docs: add MIT LICENSE file (#3) | [PR #4](https://github.com/zeroc00I/DontFeedTheAI/pull/4) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | fix(mcp): restore write_note overwrite schema for external clients (#818) | [PR #841](https://github.com/basicmachines-co/basic-memory/pull/841) merged |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | basicmachines-co | docs(installer): use pgvector image for Postgres compose | [PR #840](https://github.com/basicmachines-co/basic-memory/pull/840) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | fix(mcp): merge hot-cold cache and context-cold into MCP index | [PR #202](https://github.com/manojmallick/sigmap/pull/202) merged |
| [paulkaefer/cowsay-files](https://github.com/paulkaefer/cowsay-files) | paulkaefer | Add kidcat.cow and billcipher.cow | [PR #34](https://github.com/paulkaefer/cowsay-files/pull/34) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | feat: Willow adapter for Postgres-backed knowledge store | [PR #145](https://github.com/manojmallick/sigmap/pull/145) merged |
| [manojmallick/sigmap](https://github.com/manojmallick/sigmap) | manojmallick | feat: native Python AST extractor for accurate signature extraction | [PR #144](https://github.com/manojmallick/sigmap/pull/144) merged |
| [TensorBlock/awesome-mcp-servers](https://github.com/TensorBlock/awesome-mcp-servers) | TensorBlock | Add willow-1.7 — portless MCP server with PGP-signed authorization | [PR #401](https://github.com/TensorBlock/awesome-mcp-servers/pull/401) merged |
| [Filippo-Venturini/ctxvault](https://github.com/Filippo-Venturini/ctxvault) | Filippo-Venturini | feat: expose indexed document text for recovery workflows (#22) | [PR #29](https://github.com/Filippo-Venturini/ctxvault/pull/29) open |
| [alibaizhanov/mengram](https://github.com/alibaizhanov/mengram) | alibaizhanov | docs: add CONTRIBUTING.md with local setup and PR guidelines | [PR #40](https://github.com/alibaizhanov/mengram/pull/40) open |
| [holon-run/holon](https://github.com/holon-run/holon) | holon-run | fix: allow Sleep while waiting on same-WorkItem background command_task (#1416) | [PR #1435](https://github.com/holon-run/holon/pull/1435) open |
| [alash3al/stash](https://github.com/alash3al/stash) | alash3al | docs: post-install guide + fix MCP copy buttons (#6) | [PR #8](https://github.com/alash3al/stash/pull/8) open |
| [doobidoo/mcp-memory-service](https://github.com/doobidoo/mcp-memory-service) | doobidoo | feat(entities): Phase 1b — configurable terms + frequency-based extraction (RFC #732) | [PR #1007](https://github.com/doobidoo/mcp-memory-service/pull/1007) open |
| [doobidoo/mcp-memory-service](https://github.com/doobidoo/mcp-memory-service) | doobidoo | feat(reasoning): Phase 1a — transitive closure + abduction (RFC #732) | [PR #1006](https://github.com/doobidoo/mcp-memory-service/pull/1006) open |
| [abhixdd/ghgrab](https://github.com/abhixdd/ghgrab) | abhixdd | feat: Homebrew formula + agent integration docs (Willow) | [PR #65](https://github.com/abhixdd/ghgrab/pull/65) open |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | ComposioHQ | feat: add 10 development methodology skills | [PR #885](https://github.com/ComposioHQ/awesome-claude-skills/pull/885) open |
| [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) | Gentleman-Programming | fix(cloud): constant-time credential comparisons (#350) | [PR #399](https://github.com/Gentleman-Programming/engram/pull/399) open |
| [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) | Gentleman-Programming | fix(mcp): allow scope=personal to search across projects | [PR #398](https://github.com/Gentleman-Programming/engram/pull/398) open |
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | ngrok | docs: add an example for using ngrok with google colab | [PR #161](https://github.com/ngrok/ngrok-python/pull/161) open |
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | ngrok | fix: update type hints to reflect awaitable return types for module methods | [PR #160](https://github.com/ngrok/ngrok-python/pull/160) open |
| [ngrok/ngrok-python](https://github.com/ngrok/ngrok-python) | ngrok | feat: add `--log-level` parameter to `ngrok.__main__` | [PR #159](https://github.com/ngrok/ngrok-python/pull/159) open |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | modelcontextprotocol | fix(client): propagate transport exceptions in default message handler | [PR #2640](https://github.com/modelcontextprotocol/python-sdk/pull/2640) open |
| [liatrio-labs/claude-deep-review](https://github.com/liatrio-labs/claude-deep-review) | liatrio-labs | feat: standalone finding deduplication module + cross-session persistence | [PR #5](https://github.com/liatrio-labs/claude-deep-review/pull/5) open |
| [brainqub3/claude_code_RLM](https://github.com/brainqub3/claude_code_RLM) | brainqub3 | docs: KB-first MCP integration pattern as RLM variant | [PR #3](https://github.com/brainqub3/claude_code_RLM/pull/3) open |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | BerriAI | cookbook: routing to a custom fine-tuned GGUF model via Ollama | [PR #26307](https://github.com/BerriAI/litellm/pull/26307) open |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | feat: Willow Kart task queue tool | [PR #11979](https://github.com/NousResearch/hermes-agent/pull/11979) open |
| [ogham-mcp/ogham-mcp](https://github.com/ogham-mcp/ogham-mcp) | ogham-mcp | feat: Memory Tool 6-op conformance CI (#52) | [PR #53](https://github.com/ogham-mcp/ogham-mcp/pull/53) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | fix(auth): treat empty credential pool entries as unauthenticated in /model picker | [PR #28241](https://github.com/NousResearch/hermes-agent/pull/28241) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | fix(logging): include hermes_plugins.* in gateway.log component filter | [PR #28236](https://github.com/NousResearch/hermes-agent/pull/28236) closed |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | NousResearch | fix(plugins): raise plugin discovery failures to WARNING level | [PR #28235](https://github.com/NousResearch/hermes-agent/pull/28235) closed |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | BerriAI | fix(bedrock,sagemaker): silence ModuleNotFoundError when botocore is not installed | [PR #28193](https://github.com/BerriAI/litellm/pull/28193) closed |
| [node9-ai/node9-proxy](https://github.com/node9-ai/node9-proxy) | node9-ai | feat(blast): add Willow sovereign stack sensitive paths | [PR #172](https://github.com/node9-ai/node9-proxy/pull/172) closed |
| [AllHailSeizure/LLMPhysics-Journal-Ambitions-Contest](https://github.com/AllHailSeizure/LLMPhysics-Journal-Ambitions-Contest) | AllHailSeizure | feat(scorer): Ollama as third judge + Anthropic prompt caching | [PR #3](https://github.com/AllHailSeizure/LLMPhysics-Journal-Ambitions-Contest/pull/3) closed |
| [AllHailSeizure/LLMPhysics-Journal-Ambitions-Contest](https://github.com/AllHailSeizure/LLMPhysics-Journal-Ambitions-Contest) | AllHailSeizure | feat(scorer): Ollama as third judge + Anthropic prompt caching | [PR #3](https://github.com/AllHailSeizure/LLMPhysics-Journal-Ambitions-Contest/pull/3) closed |
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
| [Textualize/rich](https://github.com/Textualize/rich) | Textualize | feat(examples): safe_markup — escaping external content before Rich rendering | [PR #4092](https://github.com/Textualize/rich/pull/4092) closed |
| [Kludex/starlette](https://github.com/Kludex/starlette) | Kludex | docs: add FilesystemAuthBackend example to authentication guide | [PR #3249](https://github.com/Kludex/starlette/pull/3249) closed |
| [Textualize/textual](https://github.com/Textualize/textual) | Textualize | feat(examples): async message_feed with background worker and pause/resume | [PR #6510](https://github.com/Textualize/textual/pull/6510) closed |
| [ollama/ollama](https://github.com/ollama/ollama) | ollama | docs: add HuggingFace Hub direct GGUF pull pattern to import guide | [PR #15765](https://github.com/ollama/ollama/pull/15765) closed |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | modelcontextprotocol | feat(examples): postgres-backed MCP server with filesystem authorization | [PR #2494](https://github.com/modelcontextprotocol/python-sdk/pull/2494) closed |
| [TensorBlock/awesome-mcp-servers](https://github.com/TensorBlock/awesome-mcp-servers) | TensorBlock | feat: add willow-mcp to Knowledge Management & Memory | [PR #432](https://github.com/TensorBlock/awesome-mcp-servers/pull/432) closed |
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | punkpeye | feat: add willow-mcp to Knowledge & Memory 🤖🤖🤖 | [PR #5247](https://github.com/punkpeye/awesome-mcp-servers/pull/5247) closed |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | openclaw | feat(skill): add sap-enforcer — SAP/1.0 MCP tool authorization | [PR #69792](https://github.com/openclaw/openclaw/pull/69792) closed |
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
