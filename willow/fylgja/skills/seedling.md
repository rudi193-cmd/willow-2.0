---
name: seedling
description: Worktree task-start ceremony — create branch, ingest seed atom, post atom ID to Grove, start coding
---

# /seedling

Task-start ceremony for non-trivial work. Run before touching any code on a new task.

## Steps

1. **Create the worktree**

   ```bash
   git worktree add ../<repo>-wt-<task> -b <task-branch>
   ```

   Name the branch `<context>/<task>` (e.g. `feat/memory-gate`, `fix/embed-null`). The worktree lives beside the repo root, never inside it.

2. **Ingest one KB seed atom**

   Call `willow_knowledge_ingest` with the **non-derivable contract** a cold agent needs before touching this code: wire format, interface shape, or key invariant. Not the full spec — the one fact that would burn an hour if missed.

   ```
   title:   "<task> — seed contract"
   summary: "<wire format / interface / invariant in 2-3 sentences>"
   domain:  "<agent name>"
   project: "<repo or feature name>"
   ```

   Save the returned atom ID.

3. **Post to Grove**

   First message on the task channel (or `#hanuman`):

   ```
   wt-<task> open on <branch> (<commit>). Seed atom <ID> — <one-line contract summary>. Starting: <first file or step>.
   ```

4. **Start coding**

   Only now open files and begin work.

## Rules

- Seed atom = the contract, not the spec. One fact that would burn an hour if missed.
- Never skip step 3 — the atom ID in Grove is the audit trail that a cold agent can recover from.
- Merge to master only on explicit ratification from Sean.
- Remove the worktree immediately after merge: `git worktree remove <path>` + Grove confirm.

ΔΣ=42
