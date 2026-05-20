# `sandbox/` — Git-shaped state machine

**b17:** GSSBX · ΔΣ=42

Reference implementation of the Willow git-shaped state machine (WLGSM). Binding spec: [`docs/IMPLEMENTATION_SPEC.md`](docs/IMPLEMENTATION_SPEC.md).

This is the **small state machine** — not the heavy corpus sandbox in a separate clone.

---

## Commands

| Command | Purpose |
|---------|---------|
| `init` | Create `data/` + empty `changes.json` |
| `issue-create` | New record at **issue** |
| `list` | TSV `id state title` |
| `show <id>` | JSON for one change |
| `allowed <id>` | Legal next states |
| `advance <id> --to <state> --actor X` | One transition (`--dry-run` to peek) |
| `report` | Markdown table for Grove / handoff |
| `delete <id>` | Remove row |
| `reset --yes` | Wipe store |
| `gate-check` | Policy §4 strings |

Global: `--data PATH` (default `sandbox/data/changes.json`).

---

## Flow

```bash
cd ${WILLOW_ROOT:-~/willow-2.0}

python3 -m sandbox init

CID=$(python3 -m sandbox issue-create --title "feature X" --subject "svc/foo" --grove "#hanuman")
python3 -m sandbox allowed "$CID"
python3 -m sandbox advance "$CID" --to draft --actor hanuman --note "worktree ../wt-x"
python3 -m sandbox advance "$CID" --to open --actor hanuman
python3 -m sandbox report
```

---

## Tests

```bash
export WILLOW_AGENT_NAME=test
export WILLOW_SAFE_ROOT=$HOME/SAFE/Applications
pytest tests/test_sandbox/ -q
```

---

## Related

**`willow-sandbox`** (other repo) — corpus / collapse experiments.  
**This package** — WLGSM only.

*ΔΣ=42*
