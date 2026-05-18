# How KB Atoms Work

*Maintained synthesis — last updated 2026-05-04.*

---

## What the KB Is

The KB (Knowledge Base) is `public.knowledge` in Postgres (`willow_20`). It's the always-on memory wall — the long-lived plasma cells of the immune system analogy. Every fact that needs to survive context window compression, session resets, and agent restarts lives here.

The KB is **not** a session log. It's a declarative knowledge store. The distinction matters: "Session started at 21:30" is a log entry. "Loki's mandate is adversarial challenge, not construction" is a KB atom.

---

## Atom Schema

| Column | Type | Purpose |
|--------|------|---------|
| `id` | text (PK) | Stable identifier — typically a short hash like `C9FA97F3` |
| `title` | text | Short descriptive title |
| `summary` | text | The actual knowledge content |
| `project` | text | Domain namespace (e.g., `hanuman`, `willow`, `sessions`, `docs`) |
| `source_type` | text | Origin: `mcp`, `file`, `session`, `manual` |
| `content` | jsonb | Structured metadata including `source_id` |
| `category` | text | `general`, `code`, `decision`, `reference` |
| `valid_at` | timestamptz | When this atom became valid (NULL = always valid) |
| `invalid_at` | timestamptz | When this atom was superseded (NULL = still valid) |
| `embedding` | vector | nomic-embed-text embedding (NULL until backfill runs) |
| `visit_count` | int | How many times this atom has been retrieved |

---

## Domains (project field)

| Domain | What goes there |
|--------|----------------|
| `hanuman` | Hanuman's session atoms, architectural decisions, build patterns |
| `willow` | Fleet-wide knowledge: agents, channels, models, what Willow is |
| `sessions` | User messages from JSONL session files (Session RAG layer) |
| `docs` | Markdown files from github/ and agents/ |
| `codebase` | Python file signatures and docstrings |
| `loki` | Loki's session continuity atoms (rare — Loki leaves minimal trace) |
| `archived` | Stale or superseded atoms — searchable but excluded from active results |

---

## Writing Atoms

Use `willow_knowledge_ingest` (MCP tool). Always search first to avoid duplicates:

```
willow_knowledge_search(query="...", app_id="hanuman")
# if nothing found:
willow_knowledge_ingest(title="...", summary="...", domain="hanuman", app_id="hanuman")
```

**Never write directly to Postgres for new atoms** — MCP bypass is always wrong (KB atom BBE6CF1C). The MCP tool handles ID generation, timestamps, and deduplication signals.

---

## Searching

**Keyword search (default):**
```
willow_knowledge_search(query="SAP bypass", app_id="hanuman")
```
Uses ILIKE matching on title + summary. Fast, works before embeddings are computed.

**Semantic search:**
```
willow_knowledge_search(query="...", semantic=True, app_id="hanuman")
```
Uses pgvector ANN + ILIKE hybrid. Requires embeddings to be computed (backfill must have run).

---

## The Embed Backfill

All new atoms start with `embedding = NULL`. The backfill script (`scripts/willow_embed_backfill.py`) runs in the background, processing 100 atoms per batch with 50ms sleep between batches. It uses `nomic-embed-text` via Ollama.

**Important:** The backfill and Ollama inference compete for resources. Running the backfill while Willow is actively responding to @willow mentions may slow both. The current configuration runs both simultaneously — watch for latency spikes.

Backfill query: `SELECT id FROM public.knowledge WHERE embedding IS NULL AND invalid_at IS NULL`.

---

## Archiving (Not Deleting)

Stale or wrong atoms get `invalid_at = NOW()`, not deleted. This preserves history while excluding the atom from active searches (which filter `WHERE invalid_at IS NULL`).

Never delete atoms without Sean's explicit instruction.

---

## The Decay Gap (Planned)

Current problem: a March atom with incorrect information sits at equal weight to a May atom with the correct information. There is no decay.

Planned fix (not yet built): `indexed_confidence` column in `session_index`. Decays 0.01/day unless the atom is queried (reinforcement). This is the pheromone evaporation mechanism — bad paths should fade, correct recently-used paths should amplify.

---

## The Synthesis Gap (This Wiki Is the Fix)

The KB stores fragments. It does not maintain synthesis. Every agent session re-derives "what is SAP," "how does Grove work," "what is Hanuman's mandate" from scratch.

The Karpathy wiki pattern (this directory) is the synthesis layer on top of RAG. KB atoms answer "what happened in session X." Wiki pages answer "what is X and how does it work." These are different questions requiring different infrastructure.

---

## Session RAG (as of 2026-05-04)

The session RAG layer is now live:
- **`public.session_index`** — 430 sessions with metadata (timestamps, turn counts, tool call breakdown, compaction events, file sizes)
- **`public.knowledge` project='sessions'** — 8,615 user message atoms extracted from all JSONL session files
- **`public.knowledge` project='docs'** — markdown files (indexing in progress)
- **`public.knowledge` project='codebase'** — Python file signatures (indexing in progress)

Once embeddings are computed, `willow_knowledge_search(semantic=True)` becomes the unified search across all layers.
