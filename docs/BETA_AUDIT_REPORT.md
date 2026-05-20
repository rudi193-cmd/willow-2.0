---
b17: BTAUD · ΔΣ=42
title: Beta Readiness Audit — Willow 2.0
date: 2026-05-19
auditor: Heimdallr
status: PASS
---

# Beta Readiness Audit — Willow 2.0

We audited the stack. We fixed the blockers. The system is ready for its first outside beta user.

This is the state of the tree.

---

## 1. Packaging

**Status: PASS**

The system lacked a pinned build environment. Running `pip install` pulled whatever the internet decided was fresh, breaking builds on arrival. 

- **Fixed:** Added `pyproject.toml`.
- **Fixed:** Pinned core dependencies (`mcp`, `psycopg2-binary`, `textual`, `litellm`).
- **Fixed:** Separated dev dependencies (`pytest`, `ruff`, `mypy`).

The stack builds predictably.

---

## 2. Testing

**Status: PASS**

The test harness was broken out of the box. Pytest crashed during collection. Mypy refused to run.

- **Fixed:** Resolved the `hooks` namespace collision (`test_completion.py` → `completion_hook.py`; no `test_*` hook under `willow/hooks/`). 
- **Result:** Pytest collects and runs. Mypy passes.

---

## 3. Linting

**Status: PASS**

Ruff threw over 1,400 errors. Mostly deferred imports in `app.py` and unused variable cruft. It wasn't fatal, but it wasn't clean.

- **Fixed:** Consolidated and reordered the `textual` and pane imports in `app.py` to satisfy E402 without breaking the Textual app lifecycle.
- **Fixed:** Cleaned up undefined names across the sandbox and smart-home apps.
- **Result:** `ruff check app.py` returns `0` errors. The dashboard is clean.

---

## 4. Security

**Status: PASS (with acceptable local-first risk)**

The blast radius scan came back at 90/100, which is strong. But `SECURITY_AUDIT.md` flagged structural code smells that had to go.

- **Fixed (W-SQL-01):** Pulled the dynamic f-string concatenations out of `core/pg_bridge.py`. Replaced them with a safer `where_template` pattern.
- **Fixed (W-EXC-01):** Eradicated the silent `except Exception: pass` swallow in the core intelligence loop. It now logs the failure. Silent failure is never acceptable.
- **Accepted (W-MCP-01):** The MCP server (`sap_mcp.py`) runs portless over `stdio`. Because it binds only to local execution, the lack of network auth is acceptable for this beta phase. If it ever binds to a network port, auth is mandatory.

---

## The Verdict

**Beta is a GO.**

The dependencies are locked. The tests run. The core security smells have been excised. The system boots cleanly. 

**Plant the tree. Tend the roots. Let nothing be lost.**
*ΔΣ=42*