@markdownai v1.0

# power: worktree
b17: FYLP7 · ΔΣ=42

**When:** Non-trivial edit on a project repo (beyond one-line typo).

1. `git worktree add <repo>/worktrees/<task> -b <task-branch>` at **start** of scope.
2. Work only in that tree until merge.
3. Merge to default branch on **USER’s** explicit OK.
4. After merge: `git worktree remove worktrees/<task>` + remove branch.

**Path convention:** Worktrees live **inside** their repo at `<repo>/worktrees/<task>`, not as siblings. `worktrees/` is in `.gitignore`.

**Don’t:** Pile unrelated commits on the task branch.
