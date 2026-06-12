---
name: worktree-enforce
description: Hard enforcement checklist for the worktree-pr constraint. Run this before any code change. Direct master commits are banned — no exceptions.
autoInvoke:
  - Before writing or editing any code file
  - Before running git commit
  - When about to make a "quick fix" directly on master
---

# Worktree Enforce — Pre-Code Checklist

**STOP.** Before touching any code file, answer these three questions:

1. **Am I on a feature branch?**
   ```bash
   git branch --show-current
   ```
   If the answer is `master` — stop and create a branch first.

2. **Do I have an open fork tracking this work?**
   ```
   fork_list(status="open", app_id="hanuman")
   ```
   If not — create one with `fork_create` before writing any code.

3. **Is there a PR destination for this work?**
   The branch must be pushable to GitHub and mergeable via PR with CI + USER approval.

## If any answer is NO — do this first

```bash
git checkout -b fix/<slug>    # or feat/ or chore/
```

```
fork_create(app_id="hanuman", title="<what you're doing>", created_by="hanuman", topic="<slug>")
```

Then proceed.

## The rule

`worktree-pr` is a CRITICAL constraint in `willow.md`. It is not a suggestion. It exists because:
- Direct master commits bypass CI
- They cannot be reviewed before they're live
- They cannot be rolled back cleanly
- They make the ledger untrustworthy

A "quick fix" on master is not worth any of that.

## Exceptions

There are none. If something feels urgent enough to skip a branch, it's urgent enough to have a branch named `hotfix/<slug>`.

## After the work

```bash
git push -u origin fix/<slug>
gh pr create --title "..." --body "..."
```

Wait for CI. Get USER's approval. Merge. Delete the branch.

See `/worktree` for the full flow including teardown.
