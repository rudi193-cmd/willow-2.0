# `sandbox/` — Git-shaped state machine (WLGSM) reference implementation

**b17:** GSSBX · ΔΣ=42  

This package is a **portable demo** of `docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md`: explicit states, legal transitions, illegal-skip errors, JSON persistence, and the §4 new-feature gate.

It does **not** call Postgres, Grove, or SOIL — those mappings live in `sandbox/docs/IMPLEMENTATION_SPEC.md`.

## Quick start

```bash
cd ~/github/willow-1.9

# CLI
python3 -m sandbox issue-create --title "example change"
python3 -m sandbox list
python3 -m sandbox advance <id> --to draft --actor hanuman --note "worktree"
python3 -m sandbox show <id>

# §4 gate (exit 0 = all fields non-empty)
python3 -m sandbox gate-check \
  --state "3" \
  --open-pr "Grove #architecture + KB seed" \
  --merge "ingest + ledger" \
  --archive "domain=archived"
```

## Tests

```bash
python3 -m pytest tests/test_sandbox/test_git_shaped.py -v
```

## Data

Default store: `sandbox/data/changes.json` (gitignored). Override with `--data /path/to/file.json`.
