# Skill audit: Cursor native vs Willow Fylgja

**Problem:** Most Cursor `~/.cursor/skills-cursor/*` skills assume the **agent stays in the foreground** for the whole workflow (poll CI, fix, poll again). That blocks the chat thread and burns context on waits.

**Willow answer:** **Data** via Willow MCP · **shell** via `agent_task_submit` + `kart_task_run` · **long waits** via monitored background shell (`/loop` pattern) or Kart daemon — agent wakes on events, not spin-waits.

---

## Cursor skills inventory (`~/.cursor/skills-cursor/`)

| Skill | Default execution | Foreground risk | Willow counterpart / pattern |
|-------|-------------------|-----------------|------------------------------|
| **babysit** | Agent polls PR/CI in-thread until green | **High** — entire merge loop in chat | `willow/fylgja/skills/babysit.md` — Kart + background `gh pr checks` watcher |
| **loop** | Background shell + `notify_on_output` sentinel | **Low** — designed for async wake | Same pattern; prefer over inline `sleep` in agent |
| **split-to-prs** | Interactive plan → execute git | Medium — user approval gates | `worktree.md`, Kart for git; plan stays foreground |
| **shell** | Immediate terminal | Medium — by design for `/shell` | Kart unless user explicitly wants `/shell` |
| **sdk** | Foreground code/integration | Medium | Docs only; no Willow duplicate |
| **create-hook** | One-shot authoring | Low | `willow/fylgja/events/*` + `install_project.py` |
| **create-rule** | One-shot authoring | Low | `willow/fylgja/config/*.mdc` via install |
| **create-skill** | One-shot authoring | Low | `willow/fylgja/skills/*.md` + `stamp_handoffs_mai.py` |
| **create-subagent** | Foreground Task tool | Medium | Cursor Task for explore; Kart for shell sub-work |
| **migrate-to-skills** | Subagents or sequential | Medium | One-time; Kart for file ops |
| **canvas** | Foreground asset gen | Low | N/A |
| **statusline** | Config edit | Low | `scripts/cli_statusline.sh` (willow-2.0) |
| **update-cli-config** | Config edit | Low | `~/.cursor/cli-config.json` |
| **update-cursor-settings** | Config edit | Low | IDE settings |

---

## Claude Code hooks (native)

Installed via `./willow.sh agents install <id> --ide <surface>` from `willow/fylgja/install_project.py`:

| Hook | Role |
|------|------|
| `session_start` | Anchor, handoff, MCP-first |
| `pre_tool` | Bash→Kart, Read→mai_read_file, PYTHONPATH guard |
| `prompt_submit` | Boot gate, persona |
| `post_tool` | Kart follow-up |
| `stop` | Handoff pipeline, kart_poll |

**Gap:** Cursor-global skills (babysit, split-to-prs) are **not** auto-installed into the repo — they live in `skills-cursor` and run unless rules redirect to Willow.

---

## Foreground anti-patterns → replacements

| Anti-pattern | Replacement |
|--------------|-------------|
| `gh pr checks --watch` in agent turn | Background loop + sentinel (see `loop` skill) or Kart script + `kart_task_run` |
| `sleep 30 && gh pr checks` repeated in chat | `AGENT_LOOP_TICK_*` watcher with `notify_on_output` |
| Agent runs full pytest fix loop inline | `agent_task_submit` + exit; wake when Kart task completes |
| Long `git`/`gh` chains in Bash tool | Kart `task=` or `script_body=` |
| Babysit until merge in one session | **Arm watch** → user keeps working → **wake** only on red/green |

---

## Recommended rollout

1. **Adopt** `willow/fylgja/skills/babysit.md` for PR merge-ready work (Cursor + Claude).
2. **Cursor rule** (optional): "For PR babysit / CI watch, use Willow babysit skill — no foreground `--watch`."
3. **Audit** each `skills-cursor` skill: add `## Background mode` section or mark `foreground-only`.
4. **Sync manifest** `.sync-manifest.json` — track which Cursor skills have Willow twins and last review date.
5. **Install** — after adding Fylgja skills, `./willow.sh agents install <agent> --ide <surface>`.

---

## Open

- [ ] Cursor skill symlink/copy from `willow/fylgja/skills/babysit.md` into `skills-cursor/babysit` (or rule-only reference)
- [ ] `CLAUDE_COMMAND_SKILLS` — add babysit, loop, kart to Claude plugin manifest if needed
- [ ] Task tool subagents for babysit — still foreground *for the subagent*; prefer shell watcher for parent session

*2026-05-28 — fleet/handoff session*
