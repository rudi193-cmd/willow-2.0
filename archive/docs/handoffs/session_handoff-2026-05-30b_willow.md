---
agent: willow
date: 2026-05-30
session: 2026-05-30b
runtime: claude-code
format: v2
---

# HANDOFF: Stop-hook tests added; PR #141 merged

## What I Now Understand

This session worked the Stop hook on branch `fix/stop-hook-async-slow-path` (PR #141 — "perf: Stop hook async slow path + 3b inference"), which **passed CI and was merged to master by Sean**. The real hook source is `willow/fylgja/events/stop.py` + `willow/fylgja/events/stop_slow.py`: `stop.py:main()` runs the fast path (clear boot sentinel, prune depth/thread temp files, write session composite, personal-signal scan) then fires `_launch_slow_path(session_id)` — a detached `subprocess.Popen([py, stop_slow.py, sid], start_new_session=True, DEVNULL)`. `stop_slow.py` imports its workers from `stop` and runs affect tagging, `_promote_session_to_kb` (3b inference via `_infer_3b_summarize`), `_write_stack_snapshot` (3-worker ThreadPoolExecutor over `agent_task_list`/`handoff_latest`/`ledger_read`, then `soil_put` to `{agent}/stack/current`), `handoff_rebuild`, and `_drain_kart_queue` (runs `scripts/kart_poll.py`). Stale kart logs flagged an `OLLAMA_URL` NameError and a double-JSON parse failure in `_infer_3b_summarize`; the **current committed source already fixes both** (local `_url`, `raw_decode` merge loop). I added `tests/test_stop_hook.py` (10 tests, all green via `.venv-dev` pytest) and Sean confirmed it landed ("its in").

Two early missteps I correct here for accuracy: my first file Reads of `.willow/hooks/willow_stop.py` and `core/agent_identity.py` came back **glitched** (non-monotonic line numbers, a fabricated placeholder body) and I drew wrong conclusions (missing `core.handoff_sync`, no-op ThreadPoolExecutor, return-1-on-success) — all retracted after re-reading via kart `cat -n`. And `agent_task_submit` silently no-ops when called with `command=` instead of `task=`/`script_body=`.

## Open Threads

- **Tests landing** — `tests/test_stop_hook.py` confirmed in by Sean; I did not personally commit/push it. If it went onto the merged branch rather than master, verify it's actually on `origin/master` (it was untracked in the working tree when #141 merged). Fix_path: `git ls-tree origin/master tests/test_stop_hook.py`.
- **Stray ScheduleWakeup** — I set one with prompt `noop` mid-session; it fired once, harmless, no further wakeups scheduled.
- **Read-tool glitch** — some willow-2.0 `.py` reads returned corrupted content this session; cross-check critical source via kart `cat -n` before acting. See [[kart-task-param-and-drain]].
- **Carried from prior handoff (still open):** teachers-app/Quiet Corner redirect loop; upstream PRs liatrio-labs/claude-deep-review #5 and Emerging-Rule/community #9; GEMINI_API_KEY deferred; failed SAFE manifests (ratatosk, ask-jeles, utety-chat); OpenClaw Discord bridge parked.
- **Closed this session (via drained kart backlog, verify if doubted):** Grove orphan `kart_worker.py` removed + pushed to safe-app-willow-grove master; `~/.willow/env` rewritten from `export KEY=val` to plain `KEY=val` for systemd.

## What We Agreed On

- **Execution lane is kart, not Bash.** All `ls`/`git`/`pytest`/pipelines go through `agent_task_submit` + `kart_task_run`. Data (KB/SOIL/fleet/handoff) goes through Willow MCP. No agent Bash.
- `agent_task_submit` takes `task=` (shell) or `script_body=` (python) — **not** `command=`.
- `kart_task_run` drains the whole pending backlog and replays completed results; to read one task's output, redirect it to `/tmp/*.txt` and Read that instead of scanning the flood.
- Tests for the hook are mocked/pure (no Ollama/Postgres/MCP needed): they monkeypatch `urllib.request.urlopen`, parse `stop_slow.py`'s import list to assert names resolve on `stop`, and mock `subprocess.Popen`.

## 17 Questions

Q1: Did `tests/test_stop_hook.py` land on `origin/master`, or only on the merged feature branch's tree?
Q2: Should the test be wired into the CI workflow's pytest selection, or is `tests/` auto-collected already?
Q3: Was PR #141 merged squash or merge-commit — does master's history keep both perf commits?
Q4: Should the stale `.kart-scripts/test_infer_3b.py` (which still hits the old `OLLAMA_URL` path) be deleted now that real tests exist?
Q5: Is the Stop hook actually firing `stop_slow.py` in live sessions (any `~/.willow/logs/hook_timing.jsonl` entries yet)? It read "no timing log yet" this session.
Q6: Grove `app.py` kart gate — was that committed/pushed, or still local? (carried from prior handoff)
Q7: Are the dead watch PIDs in `.willow/` (ci-watch, notif-watch, upstream-pr-watch) meant to be respawned or retired?
Q8: teachers-app redirect loop — still broken on HTTP?
Q9: Upstream claude-deep-review #5 — any reviewer response?
Q10: Emerging-Rule/community #9 — merged?
Q11: Re-sign failed SAFE manifests (ratatosk, ask-jeles, utety-chat)?
Q12: Skill surface phase 3 — ready to start?
Q13: Should the Read-tool glitch be reported as a harness bug, or is it environment-local?
Q14: Any worktrees to prune now that kart-unify and #141 are merged?
Q15: Should `docs/handoffs/` remain the handoff home, or migrate to `~/.willow/handoffs/willow/` per boot.md v2?
Q16: GEMINI_API_KEY — still deferred (Groq + Ollama sufficient)?
Q17: Verify `tests/test_stop_hook.py` is on `origin/master`; if not, open a one-file follow-up PR to land it.
