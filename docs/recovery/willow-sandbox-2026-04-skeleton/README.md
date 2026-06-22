# Recovery: willow-sandbox clone skeleton (2026-04 era)

This directory preserves the **structure** of an early `willow-sandbox` repo clone
recovered from the USB drive `SEAN` on 2026-06-14.

## What happened

The clone was found at `/run/media/<user>/SEAN/willow-sandbox`. The rest of that
drive (`willow-data` 4.5G, `github-archive` 3.6G, `safe-app-store` 2.0G,
`willow-1.9` 245M, …) holds real content — but **this one directory is a hollow
copy: all 336 files are 0 bytes.** Only the directory tree and filenames survived;
the file contents are unrecoverable from this drive.

This is an early willow-2.0 sandbox clone (directories dated 2026-04-22 .. 2026-05-07).
It **predates the RH/APO discernment harness** — so it is not the "heavy corpus
sandbox" the RH harness needs. It is a different, older experiment workspace.

## What's here

- [`MANIFEST.md`](MANIFEST.md) — the full recovered structure: directory tree,
  complete 336-file inventory, and the 124 paths that are **absent from current
  master** (the genuinely sandbox-specific artifacts).

## How to read it

Most of the tree (`core/`, `willow/`, `sap/`, `tests/`, `wiki/`) already exists —
evolved — in current `master`. **Do not** resurrect the empty modules into the live
tree; current `master/sandbox/` is a different live Python package and the empty
files would break it.

The recoverable *signal* is in the 124 absent paths, two clusters worth noting:

1. **BTR (Behavioral-Truth-Rubric) experiment workspace** (`sandbox/` in the clone):
   `binder_sandbox.py`, `btr_score.py`, `make_phase_context_pack.py`, `adapters/`,
   `input/BTR_rubric*.json`, `output/` atoms + scores. An early discernment-scoring
   workbench — conceptually the ancestor of today's discernment benchmarks.
2. **Historical design lineage** (`docs/superpowers/plans` + `specs`): the
   willow-1.0 founding document, willow-18/19 phase plans, corpus-collapse design,
   persistent-memory design, rlm-willow-native, semantic-search. Titles only, but a
   useful index of how the architecture was planned.

## Rebuilding

To rebuild any of these with real content, the source is **not** this drive — look
to: the live `willow-1.9` (245M, intact on the same drive), the current evolved
modules in `master`, or the Postgres KB / SOIL history. This manifest tells you
*what* existed; those sources hold *what it said*.
