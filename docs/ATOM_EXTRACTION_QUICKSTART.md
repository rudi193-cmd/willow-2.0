# Atom Extraction — Quick Start

The system automatically creates KB atoms when work lands, so the KB stays in sync with what's actually been built.

## Enable It

```bash
export WILLOW_ATOM_EXTRACTION=1
```

Add to your shell profile to make it permanent.

## What Happens

### Post-Commit
Every time you commit:
```bash
$ git commit -m "fix: remove duplicate _open_run() definition"
[master d74b5de] fix: remove duplicate _open_run() definition
[atom-extract] d74b5de: fix: remove duplicate _open_run() definition
```

Atom automatically written to KB with:
- Title: commit subject
- Summary: intent + files changed
- Category: auto-detected (feature|bugfix|refactor|test|docs|infra)
- Source: commit hash
- References: any #issues or @mentions in the message

### Post-Merge
When a feature branch merges:
```bash
$ git merge feat/run-ledger
[master 3c20441] Merge branch 'feat/run-ledger'
[atom-merge] run-ledger_3c20441: Merge: feat/run-ledger
```

Synthesis atom written with:
- Title: "Merge: branch-name"
- Summary: synthesized intent from all commits in branch
- Category: inferred from all commits
- Links to all commit atoms

### Test Pass
(stub — implement after Phase 1)

## Debugging

Print what atoms would be created:
```bash
export WILLOW_ATOM_VERBOSE=1
git commit -m "test: add 3 new tests for mirror_pass"
[atom-extract] abc1234: test: add 3 new tests for mirror_pass
```

Or dry-run without writing to KB:
```bash
export WILLOW_ATOM_DRY_RUN=1
```

## Manual Atom Creation Still Works

The hooks don't prevent you from creating atoms manually. If you need to add context that git can't infer, write atoms with:
```python
from core.pg_bridge import PgBridge

bridge = PgBridge()
bridge.knowledge_put({
    "title": "Token-Context Dedup prevents duplicate reasoning",
    "summary": "...",
    "source_type": "architecture",
    "category": "system",
})
```

Or via the KB CLI (when available).

## What Gets Created

Each atom has:
- **title**: commit subject (first line of message)
- **summary**: intent + files changed + references
- **category**: feature, bugfix, refactor, test, docs, infra, or inferred
- **source_type**: "commit" or "merge"
- **b17**: short commit hash for easy reference
- **created_at**: when the atom was created (now)

The atom is linked to related atoms via edges (future work).

## Disable Temporarily

If the KB is down or you want to skip hook:
```bash
unset WILLOW_ATOM_EXTRACTION
git commit -m "..."  # No atom created
```

Or use `--no-verify`:
```bash
git commit --no-verify -m "..."  # Skip all hooks
```

## Hook State

The system tracks extracted atoms in `~/.willow/atom_extraction_state.json` to avoid duplicates:
```json
{
  "extracted_atoms": {
    "d74b5de09ceea9d43c89d144ae2ebbbefdb19dd7": "d74b5de",
    "1694630...": "1694630"
  },
  "last_extracted_commit": "1694630...",
  "last_test_run": "2026-05-09T10:30:00Z"
}
```

If needed, you can delete this file to force re-extraction:
```bash
rm ~/.willow/atom_extraction_state.json
```

## Phases

**Phase 1 (now):** Post-commit + post-merge hooks
**Phase 2:** Test completion tracking
**Phase 3:** Session synthesis (catches anything missed)
**Phase 4:** Atom linking + edge creation

