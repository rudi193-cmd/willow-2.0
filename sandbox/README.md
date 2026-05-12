# `sandbox/` — Git-shaped state machine (WLGSM) reference implementation

**b17:** GSSBX · ΔΣ=42  

Portable implementation of `docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md`. Full binding spec: `sandbox/docs/IMPLEMENTATION_SPEC.md`.

## Commands (quick reference)

| Command | Purpose |
|---------|---------|
| `init` | Create `data/` and empty `changes.json` if missing |
| `issue-create` | New record at **issue** (`--title`, `--subject`, `--flag`, `--grove`, `--kb-hint`, `--fork`) |
| `list` | TSV `id state title` (default), `--long` adds timestamps + hints, `--json` full records |
| `show <id>` | Pretty JSON for one change |
| `allowed <id>` | Legal **next** states from current state |
| `advance <id> --to <state> --actor X` | One transition; `--dry-run` prints JSON preview **without** writing |
| `report` | Markdown table — paste into Grove / handoff |
| `delete <id>` | Remove one row |
| `reset --yes` | Wipe entire store (requires `--yes`) |
| `gate-check` | Validate policy §4 four strings (exit 1 if any empty) |

Global: `--data PATH` (default `sandbox/data/changes.json`).

## Typical flows

```bash
cd ~/github/willow-1.9

python3 -m sandbox init

CID=$(python3 -m sandbox issue-create --title "feature X" --subject "svc/foo" --grove "#hanuman")
python3 -m sandbox allowed "$CID"
python3 -m sandbox advance "$CID" --to draft --actor hanuman --note "worktree ../wt-x"
python3 -m sandbox advance "$CID" --to open --actor hanuman --dry-run --note "peek"
python3 -m sandbox advance "$CID" --to open --actor hanuman
python3 -m sandbox list --long
python3 -m sandbox report
```

Clean slate:

```bash
python3 -m sandbox reset --yes
```

## Tests

```bash
python3 -m pytest tests/test_sandbox/test_git_shaped.py -v
```

## Related repos

**`willow-sandbox`** (separate clone) is for heavier corpus / collapse work. This **`willow-1.9/sandbox/`** package is the small **WLGSM state machine** only.
