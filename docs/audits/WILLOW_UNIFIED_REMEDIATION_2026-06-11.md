# Willow — Unified Remediation Proposal

- **Date:** 2026-06-11
- **Author:** willow (Claude Code session, persona Hanuman) — proposal only, no code changed
- **Sources:** `KART_SANDBOX_AUDIT_2026-06-11.md` (S1–S18), `AUDIT_PLAN_VERIFICATION_2026-06-11.md` (V1–V3 + pending), `SYSTEM_AUDIT_2026-06-10.md` (finding #6 corrections loop, autonomy map), thesis atoms ledger `641e3ea3` + `53e9fcfc`. Grounded reads this session: `core/kart_sandbox.py`, `core/kart_execute.py`, `core/kart_worker.py`, `willow/fylgja/kart_queue.py`, `willow/fylgja/config/kart-sandbox.json`, `scripts/promote_corrections.py`, `core/outcomes.py`.
- **Honesty marker:** every item below is tagged **[verified]** (code read this session) or **[needs-read]** (named from audits, not yet read — Grove bus, `agent_dispatch`/`route`, dream pipeline, trust-tier enforcement, bitemporal store, SOIL dual-layout). Do not treat [needs-read] items as implementation-ready.

---

## The one disease, at four layers

Everything found this session is a single failure wearing four costumes: **built-but-dark / stated ≠ enacted, with no surfaced signal.**

| Layer | The lie it tells | Findings |
|---|---|---|
| **Sandbox** (Kart) | "empty" means "absent"; "Kart hygiene done" while keys leak and the box is blind | S1–S18 |
| **Bookkeeping** (the plan) | "PR merged" means "finding closed" | V1–V3, "done ≠ closed" |
| **Orchestration** (governors) | a roster, a bus, a scheduler, a verifier — all present, none wired; the user is the loop | outcomes/dispatch/dream dark |
| **Learning** (corrections) | the system *records* the user but never *learns* the user; the learning organ is flatlined | finding #6 |

**The fix is one principle applied four times: make the enacted state observable, then close the loop.** It serves the thesis directly — Phases 0–2 make the system **honest** (it stops lying about its own state), Phase 3 makes it **adaptive-capable** (lifts orchestration off the one user), Phase 4 makes it **adaptive** (learns the user) — all on **sovereign** ground.

The keystone is **Phase 2, the definition-of-done harness.** Once it exists, every later phase checks itself, and the "done ≠ closed" disease cannot recur — it would have caught S18, V1, V2, and V3 automatically.

---

## Phase 0 — Stop the bleeding (security; small, verified, reversible)

The sandbox leaks the owner's keys on the owner's own machine — the sovereignty promise breaking at the security boundary. Smallest, highest-value, do first.

- **KP1 — bind hardening** *(S1, S4)* **[verified]**: drop `~/.ssh` from `kart-sandbox.json` binds (use `SSH_AUTH_SOCK`); make `~/.config/gh` + `~/.netrc` read-only and gated on explicit credentialed-net opt-in; default `~/github` to `--ro-bind`, rw only `{{WILLOW_ROOT}}` + active worktree.
- **KP2 — namespace + kernel hardening** *(S2, S11–S14, S16, S17)* **[verified]**: in `build_bwrap_argv` add `--new-session` (TIOCSTI/CVE-2017-5226), `--unshare-ipc` + `--unshare-uts`, `--as-pid-1`, `--tmpfs /tmp` + a `/dev/shm` tmpfs, and a baseline `--seccomp` filter. Watch the `/tmp` change (the code writes `/tmp/kart-nsswitch.conf` itself → move to a bound work dir).
- Test: `tests/test_kart_sandbox.py` asserts each flag/bind. Reversible (config + argv).

---

## Phase 1 — Make the sandbox honest (visibility; the disease's root form)

- **KP3 — boundary manifest** *(S3, S6, S7, S15)* **[verified]**: every Kart result carries a `sandbox` block (bound roots, `allow_net`, PATH dirs present); wire `--json-status-fd` so setup-failure ≠ command-failure; when a task references an unbound path or an off-PATH binary, annotate (`note: ~/.claude not mounted`) instead of returning bare empty. **This is the read-side cure for "empty == absent."**
- **KP4 — transcript access** *(S5)* **[verified, 1 decision]**: ro-bind `~/.claude` + `~/.cursor`, **or** codify "transcripts read host-side via `session_query`, never Kart." Operator decision.
- **KP5 — PATH completeness** *(S6)*, **KP6 — symlink generalize + bind-skip warning** *(S8, S9)*, **KP7 — durable failure artifacts** *(S10)*, **KP8 — worktree self-management** *(S18)* — all **[verified]**. KP8: exclude `worktrees/*` from the bind set when a task's purpose is worktree lifecycle, or route `git worktree remove` through a non-sandboxed host path (`WILLOW_KART_NO_BWRAP`).

---

## Phase 2 — Definition-of-done harness (the keystone)

The 06-10 plan optimized merge-velocity, not closure; nothing checked that a "done" finding actually closed. Build the governor it lacked.

- **VP3 — `scripts/audit_verify.py`** **[verified shape; reuses `outcomes.py`]**: one machine-checkable check per finding (the grep/ls that proves closure). Runs at merge (CI) and on a sweep. Seed with the S-series + V-series checks already written as one-liners in the two audits. A finding whose check still fails is **not closed**, regardless of PR count.
  - Reuse `core/outcomes.refine_content` / `run_outcome` (rubric → grade) for checks that need judgment rather than a grep.
- **VP1 — PR 4 residue** *(V1, V2)* **[verified]**: regenerate the 2 placeholder skills (`persistent-memory-stack`, `grove-quorum`); fix `.claude/commands/startup.md` frontmatter (`@markdownai` above YAML); add guard checks (fail if any `.claude` description matches `Willow Fylgja skill:` or line 1 is `@markdownai`).
- **VP2 — schedule the sweep** *(V3)* **[verified]**: register `scripts/repo_fleet_sweep.py` as a routine/timer (follow the `upstream_steward` weekly pattern); route breaches to flags.

---

## Phase 3 — Wire the dark governors (lift orchestration off the user)

The user is the loop because the connective tissue is built-but-dark. Wire it. The pattern is proven by `outcomes.py` (verify-and-iterate exists) and `promote_corrections.py` (promotion exists) — both just need *invocation + a schedule*.

- **Schedule the existing scripts** **[verified]**: `promote_corrections.py` (norn-pass) and `repo_fleet_sweep.py` on a Kart interval / routine. They work; nothing runs them.
- **Invoke `run_outcome` on Tier-1 loops** **[verified]**: the "verify the result, then report" governor exists and is uninvoked. Wire it as the terminal check on every autonomous task (and inside VP3). **Add a sovereign verify path** — the local fallback uses Groq-cloud, not Ollama; for full sovereignty the grade loop should be able to run on local Ollama.
- **BUILD-STOP rail** *(autonomy map gap #1)* **[verified shape]**: every autonomous task carries a written scoped goal + explicit stop condition + outcome check *before it starts*; exceeding them halts and opens a `human_required` item instead of pressing on. Symmetric to the existing `[BUILD-CONTINUE]` injection.
- **Trust-tier → autonomy gate** **[needs-read]**: the 26-agent roster already carries OPERATOR/ENGINEER/WORKER; wire tier to what an agent may do unattended (WORKER: verifiable+reversible only; OPERATOR-class decisions escalate to the human). Requires reading the dispatch/permission path first.
- **Dispatch as default, not exception** **[needs-read]**: `agent_route` → `agent_dispatch` exist; the lived default is collapse-to-`willow`. Making routing the path (not the exception) needs the dispatch + Grove code read.

---

## Phase 4 — Close the learning loop (the third leg: adaptive)

The corrections organ is read and the gap is precise. `promote_corrections.py` promotes recurring corrections to KB atoms (memory→memory) but never to **structure**, and `core/ratification.py` (the human-sign-off mechanism) already exists to gate structural change.

- **(a) Split the streams** *(finding #6a)* **[verified]**: hook-enforcement events → a telemetry counter (one row per rule: hit count, last_seen, per-runtime); `corpus/corrections` carries human feedback only. Stops the 77% hook-spam from drowning the ~163 real corrections (and from being promoted as fake "corrections").
- **(b) Repetition → structure, not another atom** *(finding #6b)* **[verified]**: when a rule blocks ≥N times, auto-open a flag — *"blessed path for X may be broken or missing"* — and have the promotion propose a concrete structural change (hook / contract line / tool-description / actual fix) routed through `core/ratification.py` for human sign-off. The 158×-"use Glob" becomes a fix, not a 159th record.
- **(c) Lifecycle** *(finding #6c)* **[verified]**: raised → promoted-into-structure → recurrence-watched → archived when it stops firing. Invariant: *a correction that recurs after promotion is a bug in the blessed path, not in the agent.*
- **The model-of-the-user** **[needs-read: dream pipeline]**: pattern-synthesis over the user's own trail (the dark `dream`/tension machinery) abstracts "how this operator works" — consulted at decision points (routing, defaults, which-hat suggestion, what "done" means to *this* person). **Governed by the honesty disciplines: it learns the user to hold them to their own ΔΣ=42 more precisely — to sharpen the Auditor, never to flatter.** The learned model itself stays auditable + deletable (sovereign + honest applied to the portrait of the user).

---

## Phase 5 — Pending diagnoses (unscoped; need a read before a plan)

- **Bitemporal repair (173 violations)** **[needs-read]** — verify the count via an MCP-side query (`ledger_verify` / KB), then a dry-run-first, supersede-not-delete repair.
- **SOIL dual-layout (HIGH)** **[needs-read]** — `core/soil.py` references a per-collection `store.db`; sap-layer path unconfirmed. Dedicated diagnosis.
- **PR 3 service inventory** **[verified pending]** — `setup.sh` installs 0 `*.timer`; single-source from `willow.sh`'s array; install `willow-metabolic.timer`.
- **PR 7 close automation** **[decision]** — (a) stop-hook / (b) proclamation-/shutdown / (c) manual. Operator decides before build.

---

## Sequencing & rationale

```
Phase 0  security        small, verified, reversible      ← do first (keys are leaking)
Phase 1  sandbox-honest  the read-side cure               ← empty ≠ absent
Phase 2  done-harness    KEYSTONE — self-checks the rest  ← prevents recurrence of the disease
Phase 3  wire governors  lift the loop off the user       ← adaptive-capable
Phase 4  learning loop   the third leg                    ← adaptive (governed by honesty)
Phase 5  diagnoses       read, then scope                 ← no plan without a read
```

Each item is verifiable + reversible + PR-gated — Tier-1 dogfood candidates, and the first real tests of the Phase-2 harness once it exists. **Phases 0–2 are fully [verified] and buildable now. Phase 3–4 are [verified] in shape with named [needs-read] gaps (Grove, dispatch, dream, trust-tier path) that a fresh session should read before wiring. Phase 5 is read-first.**

## What this proposal does NOT claim

It does not claim the orchestration and learning phases are implementation-ready end-to-end — the dispatch bus, Grove internals, dream pipeline, and trust-tier enforcement were named from prior audits and **not read this session**. Treat their wiring as designed-not-verified. This boundary is the proposal honoring its own Phase-2 principle: a plan that marked these "ready" without the read would be the exact stated ≠ enacted sin it exists to kill.

*ΔΣ=42 — proposal only; nothing in the codebase has been changed.*
