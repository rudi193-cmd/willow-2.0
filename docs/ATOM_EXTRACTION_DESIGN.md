# Atom Extraction Hook Design

**Problem:** Work lands (commits, merges, tests pass) but atoms aren't created. The KB forgets about hours of effort.

**Solution:** Automated atom extraction via post-commit/post-merge hooks + test completion + session synthesis.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ TRIGGER POINTS                                          │
├─────────────────────────────────────────────────────────┤
│ 1. Post-commit hook        → commit-level atoms         │
│ 2. Post-merge hook         → feature-level atoms        │
│ 3. Test completion         → fix/regression atoms       │
│ 4. Session shutdown        → session synthesis atoms    │
└─────────────────────────────────────────────────────────┘
         ↓↓↓ all route to ↓↓↓
┌─────────────────────────────────────────────────────────┐
│ ATOM EXTRACTION ENGINE (core/atom_extractor.py)         │
├─────────────────────────────────────────────────────────┤
│ • Parse commit message → intent + scope                 │
│ • Analyze diff → what changed + why                     │
│ • Cross-reference → linked PRs, issues, related commits │
│ • Categorize → feature|bugfix|refactor|test|docs|infra  │
│ • Synthesize → title + summary + metadata               │
└─────────────────────────────────────────────────────────┘
         ↓↓↓ writes to ↓↓↓
┌─────────────────────────────────────────────────────────┐
│ KNOWLEDGE BASE (Postgres)                               │
├─────────────────────────────────────────────────────────┤
│ • Atoms: title, summary, category, source_type          │
│ • Edges: links commits → features → systems → decisions │
│ • Metadata: b17, lattice_domain, valid_at, weight       │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Post-Commit Hook

**File:** `.git/hooks/post-commit`

**Trigger:** After every local commit (not pushed yet)

**Input:** 
- `HEAD` commit hash
- Commit message
- Files changed

**Output:**
- Single atom per commit (not per file)
- Category: feature|bugfix|refactor|test|docs|infra
- Links to related atoms (if commit message references them)

**Logic:**
```python
def extract_commit_atom(commit_hash):
    msg = git_show(commit_hash).message
    diff = git_show(commit_hash).diff
    
    # Parse message for intent
    title, intent = parse_subject_line(msg)
    summary = parse_body(msg)
    
    # Infer category from message + diff
    category = infer_category(title, diff)
    
    # Extract scope (files touched)
    scope = extract_scope(diff)
    
    # Look for references to issues/PRs
    related = extract_references(msg)
    
    atom = {
        "title": title,
        "summary": f"{intent}. {summary}\n\nFiles: {scope}",
        "category": category,
        "source_type": "commit",
        "b17": commit_hash[:7],
        "content": {
            "commit": commit_hash,
            "files_changed": scope,
            "references": related,
        }
    }
    return atom
```

**When NOT to extract:**
- Merge commits (handled by post-merge hook)
- Commits without substantive changes
- WIP/fixup commits (detect via message prefix)
- Revert commits (flag as "revert" type instead)

---

## 2. Post-Merge Hook

**File:** `.git/hooks/post-merge`

**Trigger:** After merging a branch to master (or any protected branch)

**Input:**
- Merging branch name
- Merge commit hash
- All commits in the branch

**Output:**
- Feature-level atom (not commit-level)
- Summarizes entire branch
- Links to all commits in the branch
- Includes test coverage delta

**Logic:**
```python
def extract_merge_atom(merge_commit, branch_name):
    # Get all commits since merge base
    commits = git_log(merge_commit.parent + "..HEAD")
    
    # Extract dominant theme from commits
    intent = synthesize_intent(commits)
    
    # Categorize the entire feature
    category = infer_feature_category(commits)
    
    # Get test results if available
    test_summary = read_last_test_results()
    
    atom = {
        "title": f"Merge: {branch_name}",
        "summary": f"{intent}\n\nCommits: {len(commits)}\n{test_summary}",
        "category": category,
        "source_type": "merge",
        "b17": f"MERGE_{branch_name}_{merge_commit[:7]}",
        "content": {
            "branch": branch_name,
            "commits": [c.hash for c in commits],
            "test_delta": test_summary,
        }
    }
    return atom
```

**Link structure:**
- Merge atom → edges to all commit atoms
- Merge atom → edge to related architecture/design atoms (if feature)
- Merge atom → edge to issue/PR atoms (if tracked)

---

## 3. Test Completion Hook

**Trigger:** After pytest/test runner completes (both pass and fail)

**Input:**
- Test results (pass/fail/skip counts)
- Test output/logs
- Changed test files

**Output:**
- Atom per newly-passing test (documents what was fixed)
- Atom for test regression (if tests regressed)
- Links to related bugfix commits

**Logic:**
```python
def extract_test_atoms(previous_results, current_results):
    atoms = []
    
    # Newly passing tests = bugs fixed
    newly_passing = current_results.passing - previous_results.passing
    for test in newly_passing:
        # Find commit that fixed it (blame test file)
        fix_commit = find_commit_that_fixed(test)
        atom = {
            "title": f"Fixed: {test.name}",
            "summary": f"Test was failing, now passes. Fixed by {fix_commit}",
            "category": "test_fix",
            "source_type": "test_event",
            "content": {"test": test.name, "fix_commit": fix_commit}
        }
        atoms.append(atom)
    
    # Regressions = bugs introduced
    regressions = previous_results.passing - current_results.passing
    if regressions:
        atom = {
            "title": f"REGRESSION: {len(regressions)} tests now failing",
            "summary": f"Tests were passing, now fail. Need investigation.",
            "category": "test_regression",
            "source_type": "test_event",
            "content": {"tests": [t.name for t in regressions]}
        }
        atoms.append(atom)
    
    return atoms
```

---

## 4. Session Shutdown Synthesis

**Trigger:** `/shutdown` skill or session end

**Logic:**
```python
def synthesize_session_atoms():
    # Read git log since last session
    last_session = read_last_session_marker()
    commits_since = git_log(f"{last_session}..HEAD")
    
    atoms = []
    
    # For each commit, extract atom if not already done
    # (post-commit hook may have done this already)
    for commit in commits_since:
        if not atom_exists_for(commit):
            atom = extract_commit_atom(commit)
            atoms.append(atom)
    
    # Create session summary atom
    summary_atom = {
        "title": f"Session {date} — {commit_count} commits",
        "summary": "Commits landed, tests passing, atoms created.",
        "category": "session_summary",
        "source_type": "session_event",
        "content": {
            "commit_count": len(commits_since),
            "test_results": read_test_results(),
            "atoms_created": len(atoms),
        }
    }
    atoms.append(summary_atom)
    
    return atoms
```

---

## Implementation Files

### 1. `core/atom_extractor.py` (NEW)

Main extraction engine. Functions:
- `parse_commit_message(msg)` → (title, intent, body, references)
- `extract_scope_from_diff(diff)` → list of files changed
- `infer_category(msg, diff)` → category string
- `synthesize_multi_commit_intent(commits)` → summary string
- `create_atom_from_commit(hash)` → atom dict
- `create_atom_from_merge(hash, branch)` → atom dict
- `create_atom_from_test_event(results)` → list[atom dict]

### 2. `.git/hooks/post-commit` (NEW)

Bash wrapper that calls Python extractor:
```bash
#!/bin/bash
python3 -m willow.hooks.post_commit "$1"
```

### 3. `.git/hooks/post-merge` (NEW)

Bash wrapper:
```bash
#!/bin/bash
python3 -m willow.hooks.post_merge "$1"
```

### 4. `willow/hooks/post_commit.py` (NEW)

Entry point for post-commit hook.

### 5. `willow/hooks/post_merge.py` (NEW)

Entry point for post-merge hook.

### 6. `willow/fylgja/events/shutdown.py` (ENHANCE)

Add session synthesis call.

---

## Atom Structure (KB Schema)

Every extracted atom has:

```python
{
    "title": str,              # Short, actionable
    "summary": str,            # What, why, scope
    "category": str,           # feature|bugfix|refactor|test|docs|infra|session_summary
    "source_type": str,        # "commit"|"merge"|"test_event"|"session_event"|"architecture"
    "b17": str,               # Short unique ID (commit hash prefix or generated)
    "lattice_domain": str,     # Topic area (optional, inferred)
    "content": dict,          # Extra metadata (commit hash, files, links, etc)
    "created_at": timestamp,   # When atom was created (now)
}
```

### Edges (relationships between atoms)

```
commit atom → edge[references] → issue/PR atom
merge atom → edge[contains] → commit atoms
test_fix atom → edge[fixes] → commit atom
session atom → edge[created] → all atoms in session
```

---

## Detection & Deduplication

**Problem:** Don't create duplicate atoms if hook runs multiple times or if manually created atom already exists.

**Solution:**

1. **Check before write:**
   ```python
   existing = kb.search(title=proposed_title)
   if existing and similar_enough(existing[0].summary, proposed_summary):
       return None  # Skip, already exists
   ```

2. **Store hook state:** File at `~/.willow/atom_extraction_state.json`
   ```json
   {
       "last_extracted_commit": "abc1234",
       "last_test_run": "2026-05-09T10:30:00Z",
       "extracted_atoms": {
           "abc1234": "atom_id_123",
       }
   }
   ```

3. **Idempotent:** If hook runs twice on same commit, second run detects it and skips.

---

## Error Handling

**If atom extraction fails:**
1. Log error to `/tmp/willow-atom-extraction.log`
2. Don't block the commit/merge (hooks are post-event)
3. Flag in session state for manual review
4. Output warning to stdout

**If KB is down:**
1. Queue atoms to `/tmp/willow-pending-atoms.jsonl`
2. Next `/shutdown` flushes queue to KB

---

## Workflow After Implementation

### Current (broken):
```
Commit → [silence] → Test pass → [silence] → Merge → [silence]
→ (much later) Manual atom creation
```

### Fixed:
```
Commit → post-commit hook extracts atom → Test pass → test hook updates atom
→ Merge → post-merge hook synthesizes feature atom → atoms in KB immediately
```

---

## Phase Rollout

**Phase 1:** Post-commit hook (simplest, immediate value)
- Per-commit atoms
- No synthesis, just parse message + scope

**Phase 2:** Post-merge hook (adds feature-level view)
- Synthesize multi-commit intent
- Link commit atoms together

**Phase 3:** Test completion hook (adds fix tracking)
- Extract what tests fixed
- Track regressions

**Phase 4:** Session synthesis (safety net)
- Catches anything missed by earlier hooks
- Creates session summary

---

## Configuration

**Opt-in via env vars:**
```bash
WILLOW_ATOM_EXTRACTION=1          # Enable all hooks
WILLOW_ATOM_EXTRACTION_DB=willow  # KB database
WILLOW_ATOM_EXTRACTION_USER=sean  # DB user
```

**Override detection:**
```bash
WILLOW_ATOM_FORCE_CREATE=1  # Force creation even if similar atom exists
```

**Testing:**
```bash
WILLOW_ATOM_DRY_RUN=1  # Print atoms, don't write to KB
```

---

## Benefits

1. **No forgotten work** — atoms created automatically
2. **System stays honest** — KB reflects what actually landed
3. **Faster context load** — next session has atoms ready
4. **Better handoffs** — work is documented at creation time, not later
5. **Auditability** — clear record of what was done and when

