# Kart Sandbox (bwrap) Audit

- **Date:** 2026-06-11
- **Auditor:** willow (Claude Code session, persona Hanuman) — audit-only, no code changed
- **Trigger:** Operator observation — "those Kart fixes didn't fix Kart." Confirmed live: this session was sent to read two ongoing session transcripts and Kart could not see either, returning empty results with no signal.
- **Scope:** the bwrap sandbox layer — `core/kart_sandbox.py`, `willow/fylgja/config/kart-sandbox.json`, `core/kart_execute.py`, `core/kart_worker.py`, `willow/fylgja/kart_queue.py` — graded against the bubblewrap reference atoms in the KB (29DFB21C, 2621D1D9, 9B4DB48B, 7DD730AC).
- **Relationship to prior audits:** `KART_DEEP_AUDIT_2026-06-04.md` covered the **queue state machine** (claim/lease/reap, status vocabulary, observability) — mostly addressed (`reap_stale_tasks` is live). The v2026.06.6 "audit PR 5 — Kart hygiene" guarded two **write-side** sandbox symptoms (GPG signing, INDEX regen) via `is_bwrap()`. **Neither touched the read/visibility or security posture of the sandbox itself.** That is this audit's ground.

---

## What Kart is meant to be — the design intent

The name is not "cart." It is **Kartikeya** — Skanda / Murugan, the six-faced commander of the divine armies, born to lead the devas against Taraka. The fleet's naming is deliberate (the 06-04 deep audit was witnessed under **Skirnir, the gate-witness**; the dashboard is **Heimdallr**). Two attributes define the god and therefore the tool:

- **The Vel — the single divine spear.** One disciplined instrument through which all decisive force flows. In Kart this is the *chokepoint*: every agent's execution routed through one sanctioned, contained, recorded crossing — as `willow`, not as whatever IDE is driving. This is built, and built well. The spear is forged.
- **The six faces (Shanmukha) — total awareness in every direction at once.** The commander who sees the whole field directs the whole field. This is the intent of an execution plane that governs a fleet: omnidirectional sight, *and knowledge of the edges of its own sight*. This is the attribute the audit finds shattered.

The one-line statement of where Kart stands: **the Vel is built; the six faces are shut.** A six-faced commander squinting through a bind list, calling every direction it cannot see "empty ground." Every finding below is an instance of one of those two — disciplining the spear (security/containment) or opening a face (visibility/observability).

---

## Verdict in one paragraph

The Kart sandbox is built as a **containment** boundary (protect the host from a task) but is simultaneously trusted as a **fidelity** surface (the agent assumes what it sees inside equals the host). In Kartikeya's terms: it is the Vel without the six faces — a disciplined instrument that cannot see the field it strikes. Those two goals conflict, and nothing reconciles them. When a task references a path that isn't bound or a binary that isn't on the sandbox PATH, bwrap returns *empty* or a bare non-zero exit with no stderr — indistinguishable from genuine absence. So an agent cannot tell "this doesn't exist" from "I can't see this." Meanwhile the bind set is too generous on the security axis: every Kart task — including LLM-generated workflow scripts and any prompt-injected agent — gets **read-write** access to `~/.ssh`, `~/.config/gh`, all of `~/github`, and (with `allow_net`) `~/.netrc`. The write-side guards from PR 5 are correct but local; the disease is structural and untreated on both the visibility and the security axes.

---

## Severity index

| # | Finding | Axis | Severity |
|---|---------|------|----------|
| S1 | `~/.ssh` and `~/.config/gh` bound **read-write**; `~/.netrc` bound on `allow_net`. Any task can read/modify/exfiltrate SSH private keys + GitHub credentials | security | **High** |
| S2 | No `--new-session` and no seccomp filter → TIOCSTI terminal-injection (CVE-2017-5226). KB atom 2621D1D9 names this exact mitigation as required | security | **High** |
| S3 | Read-side visibility divergence: unbound path → empty result, no "not mounted" signal. `empty` is indistinguishable from `absent` | reliability | **High** |
| S4 | Whole `~/github` and `~/.local` bound **read-write** — a compromised/injected task can mutate every local repo and share | security | **Medium** |
| S5 | Session-transcript stores (`~/.claude`, `~/.cursor`) are not bound — Kart is structurally blind to exactly the data agents are routinely asked to inspect | reliability | **Medium** |
| S6 | Sandbox `PATH` excludes `~/.local/bin` and npm-global bin — host binaries (e.g. `cursor-agent`) are invisible *even though their files are bound under `~/.local`* | reliability | **Medium** |
| S7 | `&&`-chain abort and "command not found" surface as `returncode≠0` with empty `stderr` — opaque failure, no cause | observability | **Medium** |
| S8 | Symlinked-bind fragility: every symlinked store needs a hand-coded re-add (`~/.willow`, `/var/run/postgresql`, merged-usr links). A new symlinked store silently breaks | maintainability | **Medium** |
| S9 | `_add()` silently skips a bind target that doesn't exist (`if not host.exists(): return`). A renamed/typo'd bind vanishes with zero warning | maintainability | **Low/Med** |
| S10 | Durable failure artifacts still thin (carry-forward of 06-04 F6): no `.kart-logs/<id>/`, no env/argv fingerprint on failures. PR 5 added head+tail clip markers but not a durable record | observability | **Low** |
| S11 | Host `/tmp` is bound **read-write** instead of `--tmpfs /tmp` — cross-task channel, host-`/tmp` pollution, and a shared scratch surface between sandboxed tasks | security/isolation | **Medium** |
| S12 | `--unshare-ipc` and `--unshare-uts` not set — task shares host SysV/POSIX IPC (shared memory) and UTS (hostname) namespaces | security/isolation | **Medium** |
| S13 | No `--seccomp` filter — zero syscall containment; the kernel attack surface is fully exposed (compounds S2) | security | **Medium** |
| S14 | `--unshare-pid` without `--as-pid-1` — no init/reaper inside the PID namespace, so a task that spawns children leaks zombies until the namespace tears down | robustness | **Low** |
| S15 | No `--json-status-fd` / `--info-fd` — Kart cannot distinguish "bwrap failed to build the sandbox" (mount/setup error) from "the command failed." Setup errors masquerade as command errors | observability | **Low/Med** |
| S16 | No `/dev/shm` tmpfs (`--dev /dev` gives a minimal devtmpfs) — tools needing POSIX shared memory (some multiprocessing, Postgres, headless Chromium) fail in non-obvious ways | reliability | **Low** |
| S17 | No explicit `--cap-drop ALL` / `--unshare-cgroup` — mostly covered by the unprivileged user namespace, but not belt-and-suspenders | security | **Low** |

---

## Findings

### S1 — SSH keys and GitHub creds are read-write inside every task *(security, High)*

`willow/fylgja/config/kart-sandbox.json` `bind_read_write` includes:

```
"{{HOME}}/.ssh",
"{{HOME}}/.config/gh",
"{{HOME}}/github",
"{{HOME}}/.local",
```

and `build_bwrap_argv` adds `~/.netrc` whenever `allow_net=True` (`kart_sandbox.py:217-221`). These are bound with `--bind` (read-write), not `--ro-bind`. KB atom 29DFB21C is explicit: *"bubblewrap is not a complete security policy by itself — callers must choose bind mounts."* The current choice hands every task the user's private keys, with write access, and with the network reachable in the same breath. A prompt-injected agent, a poisoned workflow phase, or a copy-pasted malicious one-liner can read `~/.ssh/id_*` and POST it out. **Fix:** drop `~/.ssh` entirely (git over HTTPS uses `gh`/token; git over SSH should use the `SSH_AUTH_SOCK` agent socket, not the key files); make `~/.config/gh` and `~/.netrc` read-only and only present when a task explicitly opts into credentialed network work.

### S2 — Missing `--new-session` → TIOCSTI injection (CVE-2017-5226) *(security, High)*

`build_bwrap_argv` (`kart_sandbox.py:170-233`) assembles: `--unshare-net` (conditionally), `--dev /dev`, `--proc /proc`, `--unshare-pid`, `--die-with-parent`, the binds, and the merged-usr symlinks. It does **not** pass `--new-session`, and there is no `--seccomp` filter. KB atom 2621D1D9: *"--new-session needed without TIOCSTI seccomp filter (CVE-2017-5226)."* Without it, a sandboxed process shares the parent's controlling terminal and can push characters into it via the `TIOCSTI` ioctl — i.e. inject commands that run in the operator's shell after the task "finishes." **Fix:** add `--new-session` to the argv (note: it disables terminal interactivity for the task, which is fine for Kart's non-interactive model), or attach a seccomp filter blocking `TIOCSTI`.

### S3 — Empty is indistinguishable from absent *(reliability, High — the live failure)*

bwrap builds a tmpfs root and mounts only the configured binds (KB 29DFB21C). Anything outside the bind set simply does not exist in the container. `collect_bind_mounts._add()` further does `if not host.exists(): return` (`kart_sandbox.py:114`). Net effect: a read of an unbound path returns "no such file" / empty, identical to a real absence. There is **no channel** that tells the caller "that path was never mounted." This session ran four negative searches (`~/.cursor`, `~/.config`, `~/.claude/projects`, cursor-agent stores) that all came back empty — none of which meant the data was absent; it meant the sandbox couldn't see it. **Fix:** make the boundary legible — see KP3.

### S4 — Blanket read-write on `~/github` and `~/.local` *(security, Medium)*

Both are `--bind` (rw). The blast radius of any task is every repository under `~/github` and the entire `~/.local` share. Combined with S1/S2 this means a single bad task is not contained to its work — it can rewrite history in unrelated repos or tamper with local application state. **Fix:** default `~/github` to ro-bind and rw-bind only `{{WILLOW_ROOT}}` + the active worktree (already discovered dynamically); promote other repos to rw only on explicit opt-in.

### S5 — Session transcripts are unreachable *(reliability, Medium)*

`~/.claude` (Claude Code transcripts) and `~/.cursor` (cursor-agent chats) are absent from every bind list. Agents are routinely asked to inspect prior/parallel sessions; via Kart that always fails silently. **Fix:** ro-bind `~/.claude` and `~/.cursor` (read-only is sufficient and safer), **or** establish the rule that transcripts are read host-side through the MCP session index (`session_query`), never through Kart, and document it so the failure stops being a surprise.

### S6 — PATH omits user/npm bins *(reliability, Medium)*

`kart_env` (`kart_sandbox.py:263-341`) builds `PATH` from the inherited `os.environ` `PATH` plus venv bin dirs. It does not guarantee `~/.local/bin` or the npm global bin dir. So `which cursor-agent` fails inside the sandbox even though `~/.local` is bound and the binary file is physically present — the shim just isn't on `PATH`. A command that works on the host fails in Kart with no explanation. **Fix:** append the known user bin dirs to `PATH` in `kart_env`, and/or report "binary X not found on sandbox PATH" distinctly from a real failure.

### S7 — Opaque `&&`/not-found failures *(observability, Medium)*

`run_shell` runs `bash -c <cmd>` and returns `{returncode, stdout, stderr}`. For an `&&` chain where an early link returns non-zero (e.g. `which cursor-agent`), bash aborts the chain, the task is marked `failed`, and `stderr` is empty — the caller sees `returncode 1` with no cause. `run_shell_task` merges block errors but inherits the same emptiness. **Fix:** when `returncode≠0` and `stderr` is empty, annotate with the last non-zero step and a hint to check sandbox PATH/binds (pairs with KP3).

### S8 — Symlinked-bind fragility *(maintainability, Medium)*

Because `_add()` resolves symlinks and dedups by real path, every symlinked store that agents expect at its symlink path must be **manually re-added** as a `--symlink` after the fact: `~/.willow` (`:197-206`), `/var/run/postgresql` (`:208-215`), and the six merged-usr links (`:184-196`). This is a growing hand-maintained list; the next symlinked store added to config will resolve away and silently not appear at its expected path. **Fix:** generalize — after building binds, for any configured path that is a symlink on the host, auto-emit the `--symlink` so the container path matches the host path.

### S9 — Silent skip of missing bind targets *(maintainability, Low/Med)*

`_add()` returns early when `host.exists()` is false. A bind entry that is renamed, typo'd, or not-yet-created vanishes from the sandbox with no log line. Good for optional `bind_try`, bad for `bind_read_write` where absence is usually a real misconfiguration. **Fix:** log skipped `bind_read_write` entries (not `bind_try`) at warning level so config rot is visible.

### S10 — Thin durable failure artifacts *(observability, Low — carry-forward of 06-04 F6)*

PR 5's `clip_output` (`kart_sandbox.py:420-431`) fixed the *silent front-truncation* by adding an explicit head+tail clip marker — a real improvement. Still missing, per 06-04 F6: a durable `.kart-logs/<task_id>/` with full stdout/stderr, the bwrap argv summary, `allow_net`, `cwd`, `script_path`, and an env fingerprint. Failures remain hard to forensically reconstruct after the fact. **Fix:** write a per-task log artifact on failure (or always) and reference its path in `result`.

---

## Unused bwrap capabilities — the complete flag surface vs. what Kart reaches for

Graded against `bubblewrap/README.md#usage` (KB 2621D1D9, 29DFB21C, 9B4DB48B). `build_bwrap_argv` (`kart_sandbox.py:170-233`) uses: `--unshare-net` (conditional), `--dev`, `--proc`, `--unshare-pid`, `--die-with-parent`, `--ro-bind`/`--bind`, `--symlink`. Everything below is available and unused.

| bwrap capability | Kart | Gap |
|---|---|---|
| `--unshare-user` | implicit | bwrap always creates a userns unprivileged — OK |
| `--unshare-pid` | ✅ | used |
| `--unshare-net` | ✅ (cond.) | used; removed on `allow_net` |
| `--unshare-ipc` | ❌ | **S12** — host IPC/shm shared |
| `--unshare-uts` | ❌ | **S12** — host hostname shared |
| `--unshare-cgroup` | ❌ | S17 — cgroup ns not isolated |
| `--new-session` | ❌ | **S2** — TIOCSTI injection (CVE-2017-5226) |
| `--as-pid-1` | ❌ | **S14** — no zombie reaper under `--unshare-pid` |
| `--die-with-parent` | ✅ | used |
| `--tmpfs /tmp` | ❌ | **S11** — host `/tmp` rw-bound instead |
| `/dev/shm` tmpfs | ❌ | **S16** — POSIX shm absent |
| `--seccomp` / `--add-seccomp-fd` | ❌ | **S13** — no syscall filter at all |
| `--cap-drop ALL` | ❌ | S17 — implicit via userns, not explicit |
| `--clearenv` / `--setenv` | ❌ | env curated via `subprocess(env=…)` instead — functional, but bwrap-side would be more robust |
| `--json-status-fd` / `--info-fd` | ❌ | **S15** — setup failure indistinguishable from command failure |
| `--dev /dev` (minimal, not `--dev-bind`) | ✅ | correct choice — host devices not exposed |
| `--ro-bind /usr /etc …` | ✅ | used |
| `--symlink` | ✅ | used (merged-usr, `~/.willow`) |

The shape of the gap: Kart reaches for the **filesystem** flags (binds, symlinks, dev/proc) and one namespace flag (`pid`, plus conditional `net`), and stops. It skips the **rest of the namespace isolation** (`ipc`, `uts`, `cgroup`), the **kernel-surface hardening** (`seccomp`, `new-session`, `as-pid-1`), the **scratch isolation** (`tmpfs /tmp`, `/dev/shm`), and the **setup-status channel** (`json-status-fd`). It is a filesystem jail with the process- and kernel-level walls left out.

---

## Root-cause model

```
                 containment goal              fidelity goal
        (protect host from the task)   (agent trusts what it sees == host)
                       \                          /
                        \                        /
   bind set chosen for convenience    no manifest of what is / isn't mounted
        (too broad: S1/S4)              (empty == absent: S3/S5/S6/S7)
                        \                        /
                         \                      /
              one sandwich serving neither goal well:
        leaks credentials AND lies about what it can see
```

The write-side guards (PR 5 `is_bwrap()`) are correct but treat individual symptoms. The two structural fixes are orthogonal and map exactly onto the god's two attributes: **discipline the Vel** — tighten the binds and the kernel surface (S1/S2/S4/S11–S17) — and **open the six faces** — declare the boundary so the commander sees every direction and the edges of its own sight (S3/S5/S6/S7/S15). Do both and the rest are mop-up.

---

## Proposed remediation plan (ordered; each verifiable, reversible, PR-gated)

Grouped by the god's two attributes: **KP1–KP2 + KP5–KP7 discipline the Vel** (one clean, contained instrument); **KP3–KP4 open the six faces** (the commander sees every direction, and knows the edges of its sight). KP3 is the keystone — it restores the defining divine attribute, so the dark stops being reported as empty.

**KP1 — Security bind hardening** *(S1, S4)*
Drop `~/.ssh` from binds; rely on `SSH_AUTH_SOCK`. Make `~/.config/gh` and `~/.netrc` read-only and gated on an explicit credentialed-network opt-in. Default `~/github` to ro-bind; rw only `{{WILLOW_ROOT}}` + active worktree. Files: `kart-sandbox.json`, `core/kart_sandbox.py`, `tests/test_kart_sandbox.py`.

**KP2 — Namespace + kernel-surface hardening** *(S2, S11, S12, S13, S14, S16, S17)*
One coherent pass over `build_bwrap_argv`: add `--new-session` (S2), `--unshare-ipc` + `--unshare-uts` (S12), `--as-pid-1` (S14), `--tmpfs /tmp` and a `/dev/shm` tmpfs (S11/S16), and a baseline `--seccomp` filter blocking at least `TIOCSTI` (S13). Each is a one-line argv addition guarded by a regression test asserting presence. Validate against the existing bwrap smoke tests so nothing that currently runs breaks (the `/tmp` change is the one to watch — anything writing to host `/tmp` and expecting persistence will need a bound work dir instead). Files: `core/kart_sandbox.py`, `tests/test_kart_sandbox.py`.

**KP3 — Boundary manifest (make empty ≠ absent)** *(S3, S6, S7, S15)*
Wire bwrap's `--json-status-fd` so sandbox-setup failures are distinguishable from command failures (S15).
Every Kart result carries a `sandbox` block: bound roots, `allow_net`, PATH dirs present. Add a cheap pre-flight: if the task text references an absolute path or a bare binary not reachable in the sandbox, annotate the result (`note: ~/.claude not mounted` / `note: cursor-agent not on sandbox PATH`) instead of returning a bare empty/failure. Files: `core/kart_sandbox.py`, `core/kart_execute.py`, `sap/sap_mcp.py`.

**KP4 — Bind or document the transcript stores** *(S5)*
Either ro-bind `~/.claude` + `~/.cursor`, or codify "transcripts are read host-side via `session_query`, never Kart" in `wiki/kart-and-tasks.md` + `willow/fylgja/skills/kart.md`. Decision needed (operator): bind vs. document.

**KP5 — PATH completeness** *(S6)*
Append known user bin dirs (`~/.local/bin`, npm global) to `kart_env` PATH. Files: `core/kart_sandbox.py`.

**KP6 — Symlink generalization + bind-skip logging** *(S8, S9)*
Auto-emit `--symlink` for any configured symlinked bind; warn on skipped `bind_read_write` targets. Files: `core/kart_sandbox.py`.

**KP7 — Durable failure artifacts** *(S10)*
`.kart-logs/<task_id>/` with full output + env/argv fingerprint, path referenced in `result`. Files: `core/kart_sandbox.py`, `core/kart_execute.py`.

Suggested order: **KP1, KP2 first** (security, small, high-value), then **KP3** (the visibility disease), then KP4–KP7.

---

## Autonomy / dogfood note

KP1, KP2, KP5, KP6 are verifiable (a test asserts the flag/bind), reversible (config + argv), and scoped — clean Tier-1 trial candidates. KP3 and KP4 carry a design decision (manifest shape; bind-vs-document) and want operator sign-off before build.

*ΔΣ=42 — audit only; nothing in the codebase has been changed.*
