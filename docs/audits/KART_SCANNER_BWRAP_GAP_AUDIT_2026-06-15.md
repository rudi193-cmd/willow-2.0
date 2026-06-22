@markdownai v1.0

# Kart Execution Plane — Security Scanner & Sandbox Gap Audit

**b17:** AUDIT · ΔΣ=42

**Date:** 2026-06-15
**Agent:** willow (Loki voice)
**Mode:** read-only audit
**Scope:** Kart shell-execution path (`agent_task_submit` → subprocess) vs. the Fylgja security scanner and the bubblewrap sandbox.
**Instrument:** `codebase-memory-mcp` code knowledge graph (14,498 nodes / 47,007 edges), every finding verified against source before recording.

## Executive Summary

The Fylgja command scanner (`scan_bash` / `scan_write` / `scan_output`) guards the **interactive agent's own tool calls** via PreToolUse/PostToolUse hooks. It does **not** sit on the **Kart execution plane**: a command submitted through `agent_task_submit(script_body=…)` is executed by `run_shell` without ever passing the scanner. Kart's only containment is the bubblewrap sandbox — and the intended fail-closed guard for "bwrap missing" is **unreachable dead code**, so a host without `bwrap` installed silently degrades to plain, unsandboxed, unscanned execution. Highest-priority finding: **Finding 1b (fail-open sandbox fallback).**

## Live Inventory

| Area | Observed state |
|------|----------------|
| Classic injection sinks (`eval`/`exec`/`shell=True`/`os.system`/`pickle`/`yaml.load`/`verify=False`) | **None** in production code (verified by grep + graph) |
| `md5` usages | All non-security (hash-ring placement, sender color, record IDs) |
| Scanner production call sites | `pre_tool.py:513` `_scan_bash`, `pre_tool.py:531` `_scan_write`, `post_tool.py:248` `_scan_output` — all on the **agent tool-call** path |
| Scanner on Kart path | **Absent** — `core/` has zero references to `security_scan` |
| Kart sandbox toggle | `use_bwrap()` = ON if `bwrap` binary present, OFF if `WILLOW_KART_NO_BWRAP∈{1,true,yes}` **or** `bwrap` not installed |
| Kart fail-closed guard | `_run_one_shell`: `if use_bwrap() and not bwrap_available()` — **never evaluates True** |

## Working Well

- No `eval`/`exec`/`shell=True`/`pickle`/`os.system` anywhere in production code — for a fleet that shells out constantly, a clean result, not an absence of looking.
- The scanner itself is well-tested: 60+ cases covering reverse shells, `curl|bash`, AWS-credential exfil, `rm -rf /`, prompt-injection in output. The detection logic is sound; the issue is **where it is wired**, not whether it works.
- The agent's direct `Bash` and `Write` tool calls *are* scanned (PreToolUse), and tool output *is* scanned (PostToolUse).
- Bubblewrap, **when active**, provides real filesystem/network namespace isolation with explicit bind-mount declarations (`sandbox_manifest`).

## Degraded or Not Working

| Issue | Impact |
|-------|--------|
| Scanner not on Kart path | Commands `scan_bash` would block as a direct Bash call are unscanned when routed via `agent_task_submit` |
| `use_bwrap()` fails open when `bwrap` absent | Kart silently runs plain `bash -c` — no sandbox, no scanner |
| Fail-closed guard unreachable | The one check meant to prevent unsandboxed execution can never fire |

## Findings

### Finding 1 — The command scanner guards the agent's Bash tool, not Kart task bodies

**Severity:** medium
**Evidence:**
- Scanner call sites (grep, verified): `pre_tool.py:513` → `_scan_bash(command)` (PreToolUse **Bash** branch); `pre_tool.py:531` → `_scan_write(...)` (Write branch); `post_tool.py:248` → `_scan_output(...)` (PostToolUse).
- Kart path (graph callee trace + grep): `agent_task_submit(script_body=…)` is an MCP call → queue → `core.kart_execute.run_shell_task` → `_run_one_shell` → `core.kart_sandbox.run_shell_result_for_task` → `run_shell` → subprocess. `core/` contains **zero** references to `security_scan`.
- The PreToolUse `_scan_bash` invocation is gated on the `Bash` tool branch; an MCP `agent_task_submit` call never enters it, so the embedded `script_body` is not command-scanned.
**Recommendation:** Decide the intended contract. If Kart is meant to be scanned, call `scan_bash` inside `run_shell_task` (or at queue time in `prepare_task_command`) and fail closed on `SEV_HIGH`. If Kart is intentionally scanner-free and relies on the sandbox, document that explicitly so the 60+ scanner tests are not read as covering Kart.

### Finding 1b — `use_bwrap()` fails open when bwrap is absent; the fail-closed guard is unreachable

**Severity:** high (deployment-dependent) — **latent on this host:** `bwrap` is installed (`/usr/bin/bwrap`) and `WILLOW_KART_NO_BWRAP` is unset, so Kart is currently sandboxed. The gap bites on any host where `bwrap` is absent.
**Evidence:**
- `core/kart_sandbox.py:41` —
  ```python
  def use_bwrap() -> bool:
      if os.environ.get("WILLOW_KART_NO_BWRAP", "").strip().lower() in ("1","true","yes"):
          return False
      return bwrap_available()
  ```
  So `use_bwrap()` is True **only when** `bwrap_available()` is already True.
- `run_shell` (`core/kart_sandbox.py:566–583`): `sandbox = "plain"`; `if use_bwrap(): … sandbox = "bwrap" else: full = argv` — when `use_bwrap()` is False it runs plain `bash -c cmd`, no namespace isolation.
- `_run_one_shell` (`core/kart_execute.py:99`) fail-closed guard: `if use_bwrap() and not bwrap_available(): return "failed", {...}`. Because `use_bwrap()` ⟹ `bwrap_available()`, the term `not bwrap_available()` is always False inside this branch. **The guard can never fire.**
- Net: on a host where `bwrap` is not installed, `use_bwrap()` returns False, the guard is skipped, and Kart executes plain + unscanned — silently, with no error.
**Recommendation:** Make the intent explicit and enforce it. Either (a) fail closed: if a sandbox is required, raise when `bwrap` is unavailable instead of relying on the unreachable guard; or (b) make plain-mode an explicit, logged opt-in (`WILLOW_KART_NO_BWRAP=1`) and have the absence of `bwrap` (without that env var) be a hard startup error rather than a silent downgrade. Add a test asserting that a missing `bwrap` binary + unset env var does **not** result in plain execution.

### Finding 2 — The code graph's CALLS resolver is blind to aliased imports (tool limitation, not a willow defect)

**Severity:** informational (audit-methodology)
**Evidence:** The graph reported `scan_bash`/`scan_write`/`scan_output` with 77 callers, **all tests, zero production**. False. The production callers import under alias (`from …security_scan import scan_bash as _scan_bash`) and call `_scan_bash(...)`. The CALLS edge resolver does not follow import aliases; grep recovered the true call sites.
**Recommendation:** Treat `codebase-memory-mcp` in-degree as a pointer to *where to look*, never as ground truth — especially in the hook layer, which aliases heavily. Every "zero callers ⇒ dead/unguarded" inference must be confirmed against source. (This audit nearly shipped a false "scanner is dead scaffolding" finding off the raw graph; verification caught it.)

## Resolution / Follow-up

| Action | Owner | Target |
|--------|-------|--------|
| Decide Kart scanning contract (Finding 1) | Sean + builder | next session |
| Fix fail-open sandbox fallback + unreachable guard (Finding 1b) | builder (Hanuman) on authorization | worktree + PR |
| Test: missing `bwrap` + unset env ⇒ not plain execution | builder | with 1b fix |
| File `codebase-memory-mcp` alias-resolution gap upstream (Finding 2) | willow | when convenient |

## Receipts

| Type | Ref |
|------|-----|
| Tools | `codebase-memory-mcp` (`query_graph`, `trace_path`, `search_graph`, `get_code_snippet`, `search_code`), `grep` |
| Source | `core/kart_sandbox.py:37-44,485-583`, `core/kart_execute.py:99-113`, `willow/fylgja/events/pre_tool.py:23-25,267-287,513,531`, `willow/fylgja/events/post_tool.py:22,248` |
| Graph | project `home-sean-campbell-github-willow-2.0`, 14,498 nodes / 47,007 edges, status `ready` |
| Base | `origin/master` `7d859b06` |
| Related | `SECURITY_AUDIT.md`, `docs/audits/KART_SANDBOX_AUDIT_2026-06-11.md`, `docs/audits/KART_DEEP_AUDIT_2026-06-04.md` |

---

*b17: AUDIT · ΔΣ=42*

## Agent Notes for Human

- The two Kart-path findings are **defense-in-depth gaps**, not a confirmed live exploit. **Live posture on this host (checked): `bwrap` is installed at `/usr/bin/bwrap` and `WILLOW_KART_NO_BWRAP` is unset, so `use_bwrap()` is True and Kart is sandboxed right now.** Finding 1b is latent — it bites on any host where `bwrap` is absent, not this one.
- Finding 1b is the one to fix first: it converts a missing dependency into a silent security downgrade, and the guard written to prevent exactly that is dead code.
- Finding 2 is about the *new tool*, not willow — but it is the single most important caveat for anyone who audits with `codebase-memory-mcp`: alias imports break in-degree. Verify against source.
- This audit is read-only. No code changed. Remediation (1b) needs explicit authorization and its own worktree + PR.

## Human Notes to Agent

<!-- operator writes here after review -->

-
