# Stone Soup Harness

b17: STONESOUP · ΔΣ=42

Staged experiment: three protected ingredients (Rendereason, angrybob,
Oakenscroll) enter a pot; Willow subsystems are added one at a time; the
harness records what emerges without leaking private collaborator material.

**Registry:** [`ingredients.json`](ingredients.json)

## Privacy boundary

| Rule | Meaning |
| --- | --- |
| **No corpus quotes** | Rendereason math corpus text never lands in tracked reports |
| **Structure only** | angrybob DBs — table names and row counts, never cell values |
| **Redacted summaries** | KB hits truncated to 200 chars in output |
| **Local reports** | Generated files live under `reports/` (gitignored) |

Visibility follows [`benchmarks/catalog.json`](../benchmarks/catalog.json):
`tracked`, `local_pointer`, `private_context`.

## Ingredients

| ID | Source | Access |
| --- | --- | --- |
| `rendereason` | KB project `rh-dirty` + [`sandbox/rh_harness/`](../rh_harness/) | KB search + harness reference |
| `angrybob` | `admissibility-calculus-2026-06-14.zip` plus optional extracted DBs | Archive structure + SQLite schema/counts only |
| `stone_soup_papers` | `$NEST/Stone Soup Papers.md` | Section/formal-label/concept extraction only |
| `oakenscroll` | Persona overlay + KB atoms | Repo-safe governance frame |

## Stages

1. **KB retrieval** — top atoms per ingredient (IDs, titles, truncated summaries)
2. **Provenance** — visibility classification per ingredient
3. **Willow layers** — KB, SOIL, Jeles, Grove, ledger, handoffs, benchmark atlas,
   Kart, governance gates, code context, and persona overlay as read-only signals
4. **Discernment** — RH harness metrics against `rh-dirty` signals
5. **Governance** — Oakenscroll posole / gaps / Dual Commit checks
6. **Alignment** — invariant metrics from [`alignment_calculus.md`](alignment_calculus.md)
7. **Synthesis** — redacted “what boiled out” markdown report
8. **Human synthesis** — readable alignment verdict from measured metrics

## Alignment Calculus

Willow aligns with Rendereason and angrybob when it **preserves invariants under
projection**, not when it produces fluent commentary.

| Domain | Native invariants | Harness proxy |
| --- | --- | --- |
| Rendereason | R1–R5 canon/noise/APO | probe overlap, rh-dirty count, archive structure |
| angrybob | B1–B5 admissibility/calculus | archive/DB presence, schema patterns, row counts |
| Willow | W1–W7 provenance/continuity | layer signals, Jeles, ledger, handoffs |
| Cross | X1–X3 theory bridge | Stone Soup concepts, provenance completeness |

**Registry:** [`alignment_metrics.json`](alignment_metrics.json) · **Engine:** [`alignment.py`](alignment.py)

Verdict bands: **aligned** ≥ 0.75 · **partial** ≥ 0.45 · **misaligned** < 0.45

## Willow pieces

The harness does not treat Willow as a single ingredient. It adds layers one at
a time so the report can show what each subsystem contributed:

| Layer | Signal type |
| --- | --- |
| `kb` | live atom counts and top projects |
| `soil` | collection/record counts only |
| `jeles` | recent extracted atom metadata |
| `grove` | recent channel message IDs, senders, and short redacted snippets |
| `ledger` | recent FRANK event metadata |
| `handoff` | latest handoff filenames and titles |
| `benchmarks` | relevant atlas entries |
| `kart` | task status counts |
| `governance` | active policy and human-required counts |
| `code` | local harness files now in play |
| `persona` | Oakenscroll overlay presence checks |
| `existing_synthesis` | Prior KB anchors: Jeles survey, sibling-overlap handoff, RH storage layout, human-context synthesis |

## Concept Bridge

The Stone Soup paper is treated as theory, not instructions. The harness extracts
only structural labels such as theorem/lemma names and concept names, then ties
those to existing synthesis anchors:

- Jeles pattern/instance boundary (`MASTER SYNTHESIS`)
- Rendereason dirty/clean discernment harness
- angrybob admissibility/calculus archive
- Oakenscroll governance and posole criterion
- Willow handoff/ledger/KB layers as reconstruction machinery

## Usage

Dry run (default — read-only, no KB writes):

```bash
python3 -m sandbox.stone_soup.run
python3 -m sandbox.stone_soup.run --output sandbox/stone_soup/reports/latest.md
```

Options:

```bash
python3 -m sandbox.stone_soup.run --app-id willow --limit 5
python3 -m sandbox.stone_soup.run --json   # machine-readable stage payloads
```

## When to promote

Catalog entry **`stone_soup_alignment`** is registered in [`benchmarks/catalog.json`](../benchmarks/catalog.json)
(draft). Promote status to `active` after a third identical run confirms repeatability.

Do **not** merge schemas with angrybob DBs or Rendereason corpus — this harness stays
structure-only.

## Related

- [`benchmarks/README.md`](../benchmarks/README.md) — discernment family
- [`stone_soup_alignment`](../benchmarks/catalog.json) — alignment calculus sidecar
- [`rh_apo_discernment_harness`](../benchmarks/catalog.json) — Rendereason probe
- Handoff Q17 (2026-06-14): share-the-stage follow-up or first MAP-ONLY catalog entry

*ΔΣ=42*
