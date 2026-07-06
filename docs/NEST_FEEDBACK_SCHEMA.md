# Nest Feedback Schema — nest/v1

b17: B2DA2  ΔΣ=42

Every human gate action on the Nest queue (confirm / override / skip) writes one
annotated intake record through `core.intake.write()`. The record carries **both
the classifier's prediction and the human outcome**, making prediction error a
stored, queryable signal instead of a discarded one. This is the feedback edge
that lets the same learning loop that refines the fleet (corrections corpus,
block telemetry, flags) refine the user-file classifier.

## Why

Before nest/v1, `confirm_review()` with an `override_dest` wrote the *predicted*
track into intake at `tier=verified, confidence=1.0` — recording the
classifier's mistake as human-verified truth, and discarding the correction.
The agent side of Willow learns from its errors (block telemetry → flags →
boot rails); the human-file side did not. nest/v1 closes that asymmetry with
the same machinery.

## Record shape

Standard intake envelope (`core/intake.py` — id, content, source, agent, tier,
confidence, keywords, tags, created_at). Keywords, tags, and content always
carry the **outcome** track, never the prediction. The feedback edge lives in
`extra`:

```json
{
  "content": "Nest override: earnings_march.pdf → ~/personal/legal/earnings_march.pdf (track: legal)",
  "source": "nest/override",
  "tier": "verified",
  "confidence": 1.0,
  "keywords": ["legal", "earnings_march.pdf"],
  "tags": ["nest", "override", "legal"],
  "extra": {
    "schema": "nest/v1",
    "event": "override",
    "prediction": {
      "track": "journal",
      "dest": "~/personal/journal/earnings_march.pdf",
      "method": "heuristic",
      "confidence": 0.70,
      "classifier_version": "b2da2-seed-1"
    },
    "outcome": {
      "track": "legal",
      "dest": "~/personal/legal/earnings_march.pdf",
      "matched": false
    },
    "features": {
      "filename": "earnings_march.pdf",
      "ext": ".pdf"
    }
  }
}
```

## Field semantics

| Field | Meaning |
|-------|---------|
| `event` | `confirm` (prediction matched), `override` (human corrected), `skip` (declined to file — weak negative) |
| `prediction` | Frozen at **scan** time on the queue row. `method` ∈ heuristic / none (later: ollama / vision). `classifier_version` pins which ruleset made the call. |
| `outcome.track` | Derived, not asked — final destination reverse-mapped against `TRACK_TO_DEST`. A dest outside every known track ⇒ `custom` (a signal that a new track wants to exist). |
| `outcome.matched` | The prediction-error bit. The entire learning signal. |
| `features` | What the file looked like to the classifier, so learning passes never re-read moved files. |

Tier rules: confirm/override are human actions ⇒ `verified`, confidence 1.0.
Skip is "not now," not a truth claim ⇒ `observed`, confidence 0.5.

Queue rows staged before nest/v1 have no stored prediction; one is
reconstructed from the row's `track` field with
`classifier_version: "pre-nest-v1"`.

## Closing the loop — corrections counter and rule-delta flags

`outcome.matched: false` additionally upserts a counter in SOIL
`corpus/nest_corrections`, keyed by `md5(predicted->outcome:ext)` — the same
pattern as `tool_denials` / block telemetry:

```json
{
  "id": "nest-corr-a1b2c3d4",
  "type": "nest_correction",
  "predicted_track": "journal",
  "outcome_track": "legal",
  "ext": ".pdf",
  "sample_filenames": ["earnings_march.pdf"],
  "count": 3
}
```

At `count >= 3` a flag opens in `{agent}/flags` (`flag-nest-<rule_key>`)
proposing a rule delta:

> Nest classifier overridden 3×: journal → legal on .pdf files.
> fix_path: propose keyword/rule delta; human ratifies; bump CLASSIFIER_VERSION.

**The classifier never rewrites its own rules.** The flag is a proposal; the
human ratifies (Dual Commit — the original `gate.py` constitution applied to
learning). Every ratified delta bumps `CLASSIFIER_VERSION`, so old errors do
not indict new rules. Flags do not reopen once resolved; the running count
stays in `corpus/nest_corrections`.

## What consumes this

- `promote_intake` — records route through the normal tier pipeline; nothing new.
- Rule-delta review — a human (or agent proposing to a human) reads
  `corpus/nest_corrections` + open `flag-nest-*` flags and edits the keyword
  lists in `sap/core/nest_intake.py` / `apps/nest/classify.py`.
- Backlog draining doubles as training: every confirm on the pending queue
  teaches the router at zero extra cost.

## Follow-ups (out of scope here)

- Extract keyword lists from code into one versioned data file shared by
  `nest_intake._classify` and `apps/nest/classify.py` (currently duplicated).
- Richer `features` (fragments, extract_method) once the extract/card stage
  from the Option C pipeline lands.
- `prediction.method: ollama|vision` when local-model classify escalation ships.
