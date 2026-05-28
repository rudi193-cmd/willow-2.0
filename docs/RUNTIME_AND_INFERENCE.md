# Runtime vs agent vs inference

b17: RTINF · ΔΣ=42

Three layers — do not collapse them.

## 1. Runtime (CLI / IDE) — transport

| Surface | Role |
|---------|------|
| Cursor, Claude Code, Codex CLI, Gemini CLI, raw API | **How** tokens move — not **who** the fleet agent is |

The model behind the CLI has no fleet namespace. It must not claim hanuman’s Postgres rows, SOIL paths, or Grove sender unless `WILLOW_AGENT_NAME` says so.

**Claude ego:** Claude will act like the main character. SessionStart injects `[IDENTITY]`: you are `$WILLOW_AGENT_NAME`; the IDE model is transport only. Route work with `agent_route` + `agent_dispatch(to=…)`.

## 2. Agent (fleet identity) — Postgres + Grove + SOIL

Set per session:

```bash
cd ~/willow-2.0
./willow agents active heimdallr
./willow agents install heimdallr --ide all
```

- MCP `app_id` / env `WILLOW_AGENT_NAME` = **caller**
- `agent_dispatch(to="loki", …)` = **recipient**
- SOIL: `{agent}/collection` via `core/agent_namespace.py`

See [`AGENT_IDENTITY.md`](AGENT_IDENTITY.md).

## 3. Inference (LLM backend) — provider-agnostic

`core/inference_router.py` — one edge for scripts and `infer_chat`:

| `WILLOW_INFERENCE_PROVIDER` | Chain |
|----------------------------|--------|
| `local` | Ollama only |
| `cloud` | Gemini → Groq (70b) → OpenRouter → fleet free keys |
| `auto` (default) | Ollama, then cloud chain |

**Keys** (any one is enough for cloud):

- `GEMINI_API_KEY` — Google AI (free tier OK)
- `GROQ_API_KEY` — e.g. `llama-3.3-70b-versatile`
- `OPENROUTER_API_KEY`
- Ollama at `OLLAMA_URL` (no key)

Set in `~/.willow/env`, agent `mcp.json`, or `~/.willow/secrets/credentials.json`.

**Not required:** Anthropic API for normal fleet inference (`willow.md`: no Anthropic in infer path).

### LiteLLM gateway (optional)

```bash
./willow.sh providers enable gemini <key>
./willow.sh litellm-start   # localhost:4000
```

SOIL registry: `core/providers.py` + `build_litellm_config()`.

### Verify

```bash
export WILLOW_AGENT_NAME=willow
python3 -c "
from core.inference_router import chat
t, p = chat('You are willow.', 'Say OK and your provider.')
print(p, t[:80])
"
```

*ΔΣ=42*
