@markdownai v1.0

# Lane-4 harnesses — small-model task envelopes

**b17:** HARN1 · ΔΣ=42

A *harness* is everything a small local model (3B–8B via Ollama) needs to own
one fleet chore safely: the prompt, the output schema, few-shot anchors, the
failure-mode checklist its verifier must catch, and scored fixtures. The
intelligence lives in the harness; the model only fills the TASK slot.

Doctrine (from the 2026-07-05 loops discussion, intake atom 4B79925A):

- **The verifier is never model-authored and never the same model class that
  did the work.** Every harness declares a `verify_class`:
  `recount | exitcode | schema | coverage | containment`.
- **`containment` harnesses cannot self-complete.** Their output lands in a
  review queue (mem_ratify or human-required); the runner enforces this by
  refusing to mark fixtures "pass" on containment checks alone — they score
  "contained" instead.
- Schema conformance is enforced at generation time via Ollama structured
  outputs (`format: <json-schema>`), so syntactic failure is near-impossible;
  the checks that matter are the *semantic residue* (IDs exist, dates parse,
  claims trace to input).

## Layout

Each harness directory contains:

| File | Purpose |
|------|---------|
| `harness.json` | Metadata: model, verify_class, temperature, options |
| `prompt.md` | System prompt (the TASK contract) |
| `schema.json` | JSON Schema passed to Ollama `format` |
| `fewshot.json` | 2–4 input→output anchor pairs, prepended as chat turns |
| `failure_modes.md` | What the verifier / reviewer must catch, ranked |
| `fixtures.jsonl` | Scored eval cases: `{"input": ..., "checks": {...}}` |

## Running

```bash
# One harness, live model, all fixtures (needs Ollama on localhost:11434;
# inside Kart use allow_localhost=True):
python willow/fylgja/harnesses/runner.py willow/fylgja/harnesses/commit_atom

# Different model / N repeats per fixture (reliability envelope):
python willow/fylgja/harnesses/runner.py willow/fylgja/harnesses/commit_atom \
    --model llama3.1:8b --repeat 5
```

The runner prints a per-fixture receipt and exits nonzero if any
**required** check fails — exitcode-verifiable by CI or a dispatch tenant.

## Harnesses

| Harness | Chore | verify_class | Completion authority |
|---------|-------|--------------|----------------------|
| `commit_atom` | Commit → KB atom extraction | `coverage` + `schema` | Self, backed by commits-vs-atoms recount |
| `dream_synthesis` | Cross-atom pattern synthesis | `containment` | mem_ratify queue only |
| `briefing_draft` | Daily briefing prose from norn report | `containment` | Review surface only |

## Envelope experiments

`envelope/EXPERIMENT.md` defines the 3B structured-output reliability
experiment: which task shapes hold at `llama3.2:3b`, where they break, and
the promotion rule for graduating a harness from 8B to 3B.
