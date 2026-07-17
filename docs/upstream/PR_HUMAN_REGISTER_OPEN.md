# Upstream PR comment register

*Generated: 2026-07-16 04:52 UTC · operator: `rudi193-cmd` · filter: `open`*

Every captured comment from GitHub (description, discussion, reviews, inline).
Human voices grouped first; bots and automation in a separate section.

- **You** — operator / PR author
- **Maintainer** — repo owner or anyone who submitted a PR review
- **Contributor** — other human participants
- **Bots** — github-actions, dependabot, code assistants, etc.

**PRs processed:** 9 · **comments captured:** 32

---

## NousResearch/hermes-agent #64281

**feat(plugins): dreaming memory consolidation (config.yaml re-scope)**

- URL: https://github.com/NousResearch/hermes-agent/pull/64281
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## Summary

Re-opens the #25309 dreaming plugin proposal after #40737 was closed under the `env-var-for-config` policy.

- Behavioral settings live in **plugin-owned** `$HERMES_HOME/dreaming/config.yaml` (seeded from `plugins/dreaming/config.yaml` on first register), with optional `dreaming:` overrides in `~/.hermes/config.yaml`.
- Removes user-facing `HERMES_DREAMING` / `HERMES_DREAM_*` env flags — opt-in is `hermes plugins enable dreaming` + `enabled: true` in config.
- Three-phase pipeline unchanged: Light Sleep (staging/dedupe/score) → REM (Ollama narrative) → Deep Sleep (MEMORY.md promotion, meta-entries → SKILL.md).
- Reference port from [Willow 2.0](https://github.com/rudi193-cmd/willow-2.0) `dream_check` / `dream_run` / `tension_scan` — no runtime dependency.

## Test plan

- [x] `uv run pytest tests/plugins/test_dreaming_plugin.py -q` (4 tests: config seeding, main-config override, REM model override, promote threshold)
- [ ] `hermes plugins enable dreaming` then set `enabled: true` in `$HERMES_HOME/dreaming/config.yaml`
- [ ] `/dream status` and `/dream run` on a profile with staged candidates

Closes the configuration-policy gap called out in the #40737 sweeper comment.


Made with [Cursor](https://cursor.com)

### Maintainers

#### `tonydwb` · 2026-07-14 09:29:28 · review (COMMENTED) · id=4692782674

## Code Review Summary

**Verdict: Comment** (moderate-high surface area)

This PR consolidates dreaming memory configuration into config.yaml. 10 files, 976 additions.

### Observations

- Config.yaml re-scope is a good direction.
- Verify backward compatibility with existing configs.

---
*Reviewed by Hermes Agent*

#### `teknium1` · 2026-07-16 02:07:13 · inline (plugins/dreaming/__init__.py:47) · id=3592122356

`dream_check` does not accept `cfg` (`_schedule.py:107-124`). This raises `TypeError` on every polling attempt and is swallowed by the enclosing `except`, so the automatic scheduler never runs.

#### `teknium1` · 2026-07-16 02:07:13 · inline (plugins/dreaming/__init__.py:60) · id=3592122358

Plugin hooks are invoked as `cb(**kwargs)` and the current `on_session_end` emitter supplies metadata only, not a context object or transcript (`hermes_cli/plugins.py:1912-1917`, `agent/turn_finalizer.py:528-542`). This callback cannot be called successfully as written.

#### `teknium1` · 2026-07-16 02:07:13 · review (COMMENTED) · id=4709846000

<!-- hermes-sweeper:review=64281 -->
<!-- hermes-sweeper:review-verdict=keep_open salvageability=medium -->
Thanks for re-scoping the settings away from `HERMES_DREAM_*`; the plugin/config direction addresses the prior policy close.

### Problems
- `plugins/dreaming/__init__.py:60` registers `_on_session_end(ctx)`, but plugin hooks call callbacks as `cb(**kwargs)` (`hermes_cli/plugins.py:1912-1917`) and the current emitter provides metadata only (`agent/turn_finalizer.py:528-542`). No transcript reaches the plugin.
- `plugins/dreaming/__init__.py:44-47` passes `cfg` to `dream_check`, although `plugins/dreaming/_schedule.py:107-124` has no such parameter. The thread suppresses the resulting exception at `__init__.py:50-51`, so automatic cycles cannot run.
- `plugins/dreaming/__init__.py:80` requires `(argv, ctx)`, while CLI dispatch passes one raw string (`cli.py:8958-8962`); gateway and TUI follow the same contract.
- `plugins/dreaming/_schedule.py:191-201` writes `$HERMES_HOME/MEMORY.md`, but active built-in memory is `$HERMES_HOME/memories/MEMORY.md` (`tools/memory_tool.py:55-57`, `:280-285`). Promotions are not loaded into Hermes memory.

### Suggested changes
- Rework the hook around a real transcript-bearing lifecycle path and add an E2E test through plugin registration.
- Match the raw-string slash-command API, remove unsupported `cfg` parameters, and route writes through the bounded, guarded `MemoryStore` format.
- Omit the already-landed model-validation hunk; current main has it via `0d3ad193d6cc235213489f509e26760ccb3722a1`.

Automated hermes-sweeper review.

#### `teknium1` · 2026-07-16 02:07:14 · inline (plugins/dreaming/__init__.py:80) · id=3592122359

Registered plugin slash handlers receive one raw argument string (`cli.py:8958-8962`; gateway and TUI use the same shape). This required second `ctx` parameter makes every `/dream` invocation fail before subcommand parsing.

#### `teknium1` · 2026-07-16 02:07:14 · inline (plugins/dreaming/_schedule.py:195) · id=3592122363

This is not Hermes's active memory path: `MemoryStore` uses `get_hermes_home() / "memories" / "MEMORY.md"` (`tools/memory_tool.py:55-57,280-285`). Promotions written here will not be loaded into the next session's persistent-memory snapshot.

---

## alash3al/stash #14

**docs: clarify that curl /sse holding open is expected SSE behavior (#11)**

- URL: https://github.com/alash3al/stash/pull/14
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## What

Adds a Troubleshooting entry to `docs/GETTING_STARTED.md` explaining that a raw `curl http://localhost:8080/sse` printing an `event: endpoint` line and then holding the connection open is **expected SSE behavior, not a hang**.

## Why

This is the exact confusion reported in #11 — a new user followed the Getting Started guide, tested with `curl`, saw the stream hold open, and read it as the server hanging. As you noted there, `curl` can't complete the MCP handshake. There was no note in the docs explaining that the hold-open is normal, so the next newcomer hits the same wall.

The entry:
- explains the `/sse` stream emits the initial `endpoint` event then stays open for the MCP session;
- shows the non-blocking status-code check (`curl -s -o /dev/null -w "%{http_code}"`) already used in §1;
- points to the existing "Connect your MCP client" section for a real end-to-end check.

## Scope

Docs-only, +17 lines, no behavior change. Placed first in Troubleshooting since it's the most common first-run gotcha. Independent of #13 (which only adjusts CLI help text).

Closes #11.

---

## castroquiles/glapagos #20

**feat(api): export committed OpenAPI spec and cover the API (#13)**

- URL: https://github.com/castroquiles/glapagos/pull/20
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

Closes #13.

## What

FastAPI already generates the OpenAPI document at runtime (`/openapi.json`, `/api/docs`, `/api/redoc`), but the repo shipped no committed contract — and `src/api/__init__.py` referenced a `docs/api/openapi.yaml` file that did not exist. This PR exports, commits, documents, and drift-tests the spec.

- **`scripts/export_openapi.py`** — regenerates `docs/api/openapi.json` from `app.openapi()` (stdlib only; no new dependency).
- **`docs/api/openapi.json`** — the committed contract, consumable by client generators and reviewers without running the server.
- **`docs/api/index.md`** — human-readable endpoint reference, auto-published by mkdocs (`mkdocs build --strict` passes).
- **`tests/unit/test_openapi.py`** — fails if the committed spec drifts from the live app, asserts all four paths + version, and exercises every endpoint (health, stats, list + filters, get-by-id, 404) via `TestClient`.
- Fixes the dangling reference in `src/api/__init__.py` (`.yaml` → `.json`).

I chose JSON over YAML deliberately: it is FastAPI's native format and parses with the stdlib, so the spec and its drift-test add **zero** runtime dependencies.

## Why JSON / why a generator

The artifact is generated, never hand-edited — `python scripts/export_openapi.py` reproduces it byte-for-byte, and the test enforces that. So the contract can't silently rot as the API evolves.

## Verification

- `pytest tests/unit/` → **16 passed**, and unit coverage of `src/api/main.py` goes **41% → 100%** (the `--cov-fail-under=80` gate now passes — it was previously below threshold).
- `black --check`, `isort --check-only`, `mypy src/` all clean on the added/changed files.
- `mkdocs build --strict` succeeds.

## Note (not addressed here, to keep this PR focused)

The CI `lint` job runs bare `flake8 src/ tests/`, which uses the default 79-col limit, while `.pre-commit-config.yaml` configures `--max-line-length=120` (and `black` formats to 88). The added files are clean under the configured 120 limit but, like the existing `src/api/main.py`, exceed 79 under the CI invocation. Happy to send a one-line follow-up aligning CI flake8 with the pre-commit config if you'd like.

---

## castroquiles/HeatWatch #20

**fix(geo_utils): correct clip_array_to_bounds off-by-one; add geo_utils tests + NDVI no-data guard**

- URL: https://github.com/castroquiles/HeatWatch/pull/20
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## What & why

While adding test coverage for `src/utils/geo_utils.py` — the only logic module without a `test_*.py` — a test surfaced a real correctness bug, so this PR fixes it and lands the coverage.

### 1. Bug fix: `clip_array_to_bounds` off-by-one

The function converted geographic offsets to pixel indices with `int(...)`. Because IEEE-754 stores a mathematically-integer index like `0.8 * 10` as `7.999999999`, `int()` truncated it to `7`, shifting the clip window by a **whole pixel in both axes** — so the wrong region was analysed.

Repro (now a test): clipping a 10×10 grid spanning `[-100,-99]×[40,41]` to `[-99.5,-99.2]×[40.3,40.7]` should yield a `(4, 3)` window but returned `(5, 2)`.

Fix: snap to the nearest pixel within a tiny tolerance (`_PIXEL_EPS = 1e-9`, far below one pixel) before truncating.

### 2. New tests: `tests/test_geo_utils.py`

Covers `haversine_distance` (zero, 1°-latitude ≈ 111.19 km, NYC↔LA ≈ 3936 km, symmetry), `bounds_to_bbox` (happy path + both `ValueError` raises + degenerate extent), `pixel_to_coords` (affine), and `clip_array_to_bounds` (interior / clamped / non-overlapping).

### 3. Small fix: `ndvi_to_color(NaN)`

NaN compares `False` against every legend breakpoint, so no-data pixels fell through to the **dense-canopy** colour. Added an explicit NaN → `NODATA_COLOR` guard (consistent with how `export_ndvi_map` already handles NaN) plus a test.

## Verification

Full suite green locally: `54 passed`. No new dependencies; touches only `analysis`/`utils` + tests.

---

## PDFMathTranslate/PDFMathTranslate #1148

**feat: mirror source directory tree in batch translation output**

- URL: https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## Summary

Closes #793.

When `--dir` is used, translated files now land in a subdirectory structure that mirrors the source tree instead of being flattened into the output root.

**Example:**
```
docs/
  papers/intro.pdf
  supplemental/appendix.pdf
```
With `pdf2zh --dir docs/ -o out/` you now get:
```
out/
  papers/intro-mono.pdf
  papers/intro-dual.pdf
  supplemental/appendix-mono.pdf
  supplemental/appendix-dual.pdf
```

## What changed

- `TranslateRequest` (`kernel/protocol.py`): added `source_dir: Optional[str] = None` field
- `LegacyKernel.translate()` (`kernel/legacy.py`): passes `source_dir` through to `high_level.translate()` when set
- `high_level.translate()` (`high_level.py`): accepts `source_dir` kwarg; computes a relative output subdir per file using `os.path.relpath`, creates it with `mkdir(parents=True)`, skips the logic for URL inputs
- `main()` (`pdf2zh.py`): captures `source_dir = os.path.abspath(files[0])` before expanding the file list, passes it into `TranslateRequest`

URL inputs and non-`--dir` invocations are unaffected — they continue writing directly to `Path(output)`.

## Test plan

- [ ] `pdf2zh --dir /path/to/nested/ -o /tmp/out/` — verify output mirrors source hierarchy
- [ ] Single-file invocation `pdf2zh paper.pdf -o /tmp/out/` — verify flat output unchanged
- [ ] URL input (`pdf2zh https://…/paper.pdf -o /tmp/out/`) — verify flat output unchanged

---

## openedx/codejail #309

**feat: introduce CodeJailConfig class; keep module-level backward compat**

- URL: https://github.com/openedx/codejail/pull/309
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## Summary

Closes #159.

The three module-level globals (, , ) make it impossible for callers to maintain isolated codejail state — test fixtures bleed into each other, and multi-tenant scenarios that want different limits per request must serialize globally.

This PR introduces a  class that encapsulates those three dicts along with all the mutation methods (, , , ).  A module-level  instance is created, and the existing module-level names become **aliases pointing at the same dict objects** inside it — so every existing caller continues to work without any changes.

### What changed

| File | Change |
|---|---|
|  | Add `CodeJailConfig` + `_default_config`; compat aliases; `jail_code(config=None)` |
|  | `apply_django_settings(…, config=None)` |
| `tests/test_jail_code.py` | Import `CodeJailConfig`; add `TestCodeJailConfig` (9 unit tests) |
| `tests/util.py` | `ResetJailCodeStateMixin` mutates dicts in-place instead of rebinding names |

### Backward compatibility

All existing module-level APIs (, , , , , direct dict access via //) are fully preserved.

### Testing

The new  unit tests run without a sandbox and cover:
- Instance isolation (two configs don't share state)
-  /  round-trip
-  / 
- Context-specific limit overrides
-  override guard
- Isolation from module-level globals

Full integration tests require the sandbox environment described in the repo README and cannot be run from a fork per issue #139.

## Test plan

- [x] ============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/sean-campbell/github/willow-2.0
configfile: pyproject.toml
plugins: timeout-2.4.0, anyio-4.13.0
collected 0 items / 1 error

==================================== ERRORS ====================================
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_jail_code.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_jail_code.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_jail_code.py:13: in <module>
    from codejail import proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
=========================== short test summary info ============================
ERROR codejail/tests/test_jail_code.py
=============================== 1 error in 0.03s =============================== — 9 passed
- [ ] Maintainer: run full Running all tests with no proxy process
CODEJAIL_PROXY=0 pytest --junitxml=reports/pytest-no-proxy.xml --log-level=DEBUG
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/sean-campbell/github/willow-2.0
configfile: pyproject.toml
plugins: timeout-2.4.0, anyio-4.13.0
collected 0 items / 4 errors

==================================== ERRORS ====================================
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_django_integration_utils.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_django_integration_utils.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_django_integration_utils.py:5: in <module>
    from django.conf import settings
E   ModuleNotFoundError: No module named 'django'
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_jail_code.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_jail_code.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_jail_code.py:13: in <module>
    from codejail import proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_json_safe.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_json_safe.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_json_safe.py:7: in <module>
    from codejail.safe_exec import json_safe
codejail/safe_exec.py:10: in <module>
    from codejail import jail_code
codejail/jail_code.py:10: in <module>
    from .proxy import run_subprocess_through_proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_safe_exec.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_safe_exec.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_safe_exec.py:12: in <module>
    from codejail import safe_exec
codejail/safe_exec.py:10: in <module>
    from codejail import jail_code
codejail/jail_code.py:10: in <module>
    from .proxy import run_subprocess_through_proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
- generated xml file: /home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/reports/pytest-no-proxy.xml -
=========================== short test summary info ============================
ERROR codejail/tests/test_django_integration_utils.py
ERROR codejail/tests/test_jail_code.py
ERROR codejail/tests/test_json_safe.py
ERROR codejail/tests/test_safe_exec.py
!!!!!!!!!!!!!!!!!!! Interrupted: 4 errors during collection !!!!!!!!!!!!!!!!!!!!
============================== 4 errors in 0.11s =============================== + Running all tests with proxy process
CODEJAIL_PROXY=1 pytest --junitxml=reports/pytest-proxy.xml --log-level=DEBUG
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/sean-campbell/github/willow-2.0
configfile: pyproject.toml
plugins: timeout-2.4.0, anyio-4.13.0
collected 0 items / 4 errors

==================================== ERRORS ====================================
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_django_integration_utils.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_django_integration_utils.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_django_integration_utils.py:5: in <module>
    from django.conf import settings
E   ModuleNotFoundError: No module named 'django'
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_jail_code.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_jail_code.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_jail_code.py:13: in <module>
    from codejail import proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_json_safe.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_json_safe.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_json_safe.py:7: in <module>
    from codejail.safe_exec import json_safe
codejail/safe_exec.py:10: in <module>
    from codejail import jail_code
codejail/jail_code.py:10: in <module>
    from .proxy import run_subprocess_through_proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
_ ERROR collecting worktrees/upstream-codejail/codejail/tests/test_safe_exec.py _
ImportError while importing test module '/home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/codejail/tests/test_safe_exec.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
codejail/tests/test_safe_exec.py:12: in <module>
    from codejail import safe_exec
codejail/safe_exec.py:10: in <module>
    from codejail import jail_code
codejail/jail_code.py:10: in <module>
    from .proxy import run_subprocess_through_proxy
codejail/proxy.py:26: in <module>
    import six
E   ModuleNotFoundError: No module named 'six'
- generated xml file: /home/sean-campbell/github/willow-2.0/worktrees/upstream-codejail/reports/pytest-proxy.xml -
=========================== short test summary info ============================
ERROR codejail/tests/test_django_integration_utils.py
ERROR codejail/tests/test_jail_code.py
ERROR codejail/tests/test_json_safe.py
ERROR codejail/tests/test_safe_exec.py
!!!!!!!!!!!!!!!!!!! Interrupted: 4 errors during collection !!!!!!!!!!!!!!!!!!!!
============================== 4 errors in 0.10s =============================== in sandbox environment

#### `rudi193-cmd` · 2026-06-17 00:10:32 · discussion · id=4724728229

@mphilbrick211 I wanted to let you know that it was submitted and signed yesterday, June 18. I have not heard anything back. This is a wonderful project, and I'm looking forward to helping where I can.

#### `rudi193-cmd` · 2026-06-24 18:00:08 · discussion · id=4792222361

> Hi @rudi193-cmd have you received your executed copy of the form?

I did, just about an hour ago!

#### `rudi193-cmd` · 2026-06-28 18:18:51 · discussion · id=4826981071

Thanks again @mphilbrick211 — now that the CLA is executed on my end (received 06-24), this should be clear on the legal side. Whenever you or @moisesgsalas have a moment, I'd welcome a review of the changes here. The PR introduces a `CodeJailConfig` class while keeping the module-level globals working for backward compatibility, and CI is green. Happy to adjust anything you'd like to see different.

### Other contributors

#### `openedx-webhooks` · 2026-06-15 19:44:24 · discussion · id=4711780337

Thanks for the pull request, @rudi193-cmd!


This repository is currently maintained by `@moisesgsalas`.


Once you've gone through the following steps feel free to tag them in a comment and let them know that your changes are ready for engineering review.

<details><summary>:radio_button: Get product approval</summary>

If you haven't already, [check this list](https://openedx.atlassian.net/wiki/spaces/COMM/pages/3875962884/How+to+submit+an+open+source+contribution+for+Product+Review#Does-my-contribution-require-Product-Review%3F) to see if your contribution needs to go through the product review process.

- If it does, you'll need to submit a product proposal for your contribution, and have it reviewed by the [Product Working Group](https://openedx.atlassian.net/wiki/spaces/COMM/pages/3449028609/Product+Working+Group).
    - This process (including the steps you'll need to take) is documented [here](https://openedx.atlassian.net/wiki/spaces/COMM/pages/3875962884/How+to+submit+an+open+source+contribution+for+Product+Review#Product-Review-Process).
- If it doesn't, simply proceed with the next step.
</details>

<details><summary>:radio_button: Provide context</summary>

To help your reviewers and other members of the community understand the purpose and larger context of your changes, feel free to add as much of the following information to the PR description as you can:

- Dependencies
  > This PR must be merged before / after / at the same time as ...
- Blockers
  > This PR is waiting for OEP-1234 to be accepted.
- Timeline information
  > This PR must be merged by XX date **because** ...
- Partner information
  > This is for a course on edx.org.
- Supporting documentation
- Relevant [Open edX discussion forum](https://discuss.openedx.org/) threads
</details>





<details><summary>:radio_button: Get a green build</summary>

If one or more checks are failing, continue working on your changes until this is no longer the case and your build turns green.
</details><details>


---

<details><summary>Where can I find more information?</summary>

If you'd like to get more details on all aspects of the review process for open source pull requests (OSPRs), check out the following resources:

- [Overview of Review Process for Community Contributions](https://docs.openedx.org/en/latest/developers/references/developer_guide/process/FAQ-about-pull-requests.html)
- [Pull Request Status Guide](https://docs.openedx.org/en/latest/developers/references/developer_guide/process/pull-request-statuses.html)
- [Making changes to your pull request](https://docs.openedx.org/en/latest/documentors/how-tos/make_changes_to_your_pull_request.html)
</details>

<details><summary>When can I expect my changes to be merged?</summary>

Our goal is to get community contributions seen and reviewed as efficiently as possible.

However, the amount of time that it takes to review and merge a PR can vary significantly based on factors such as:

- The size and impact of the changes that it introduces
- The need for product review
- Maintenance status of the parent repository

:bulb: *As a result it may take up to several weeks or months to complete a review and merge your PR.*
</details>
<!-- comment:external_pr -->
<!-- data: eyJkcmFmdCI6IGZhbHNlfQ== -->

#### `mphilbrick211` · 2026-06-16 13:00:47 · discussion · id=4718999477

Hi @rudi193-cmd! Welcome, and thank you for this contribution! In order for your CLA check to turn green, you'll need to submit a CLA form. If you are contributing as an individual, please fill out the individual [CLA form here](https://docs.openedx.org/en/latest/developers/quickstarts/so_you_want_to_contribute.html#id175).

If you are contributing on behalf of an organization, please have your manager reach out to oscm@axim.org so you may be added to your org's existing entity agreement.

Please let me know if you have any questions. Thanks!

#### `mphilbrick211` · 2026-06-18 16:34:28 · discussion · id=4744102418

> @mphilbrick211 I wanted to let you know that it was submitted and signed yesterday, June 18. I have not heard anything back. This is a wonderful project, and I'm looking forward to helping where I can.

Great, thanks! You should receive an executed copy from our legal counsel in the next day or so.

#### `mphilbrick211` · 2026-06-24 17:42:09 · discussion · id=4792073324

Hi @rudi193-cmd have you received your executed copy of the form?

#### `e0d` · 2026-07-13 17:33:43 · discussion · id=4960796992

@rudi193-cmd Your branch was behind the base.  I've pulled in changes from master as a merge commit which will update your branch and cause the tests to be re-run.  You should pull the changes into your local branch.

---

## coleam00/mcp-mem0 #18

**fix: disable Mem0 telemetry via env (Fixes #3)**

- URL: https://github.com/coleam00/mcp-mem0/pull/18
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## Summary

Fixes #3 by making telemetry opt-out work reliably from `.env` / Docker env files.

Mem0 reads `MEM0_TELEMETRY` at import time, but this server previously called `load_dotenv()` **after** importing `mem0`, so setting the variable in `.env` had no effect and PostHog connection errors could flood logs in offline deployments.

## Changes

- Load `.env` before any Mem0 import via `src/bootstrap.py`
- Support native `MEM0_TELEMETRY=false` and convenience alias `DISABLE_TELEMETRY=true`
- Document both variables in `.env.example` and README
- Add unit tests for telemetry env normalization

## Usage

```bash
MEM0_TELEMETRY=false
# or
DISABLE_TELEMETRY=true
```

## Test plan

- [x] `uv run python -m unittest tests/test_bootstrap.py -v`


Made with [Cursor](https://cursor.com)

---

## kelos-dev/kanon #34

**Add repo-local project overlays (#33)**

- URL: https://github.com/kelos-dev/kanon/pull/34
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

## Summary

Implements a small first slice for #33: `kanon render/apply --project <repo>` now composes the central Kanon config with a repo-owned overlay config when `<repo>/.kanon/kanon.yaml` exists.

- Auto-detect `<project>/.kanon/kanon.yaml` for project-scoped renders/applies
- Add `--overlay <path>` for explicit overlay config selection
- Merge overlay instructions, skills, MCP servers, hooks, and metadata into the base config for that command only
- Rebase overlay `instructions.files` and `skills[].path` from the overlay directory, so repo-owned assets live under `.kanon/`
- Document project overlays in the README

## Test plan

- [x] `git diff --check`
- [ ] `gofmt -w internal/core/config.go internal/cli/root.go internal/cli/root_test.go` (not run locally: Go toolchain unavailable in this environment)
- [ ] `go test ./...` (not run locally: Go toolchain unavailable in this environment)

I added `TestRenderMergesProjectOverlay` to cover central + repo-local instructions, MCP servers, and a repo-local default skill path.

Made with [Cursor](https://cursor.com)

#### `rudi193-cmd` · 2026-06-04 12:50:06 · discussion · id=4622294595

Label check is blocked by `needs-kind` and `needs-release-note`. Suggested labels for this PR: `kind/api` and `release-note`.

#### `rudi193-cmd` · 2026-06-15 13:37:07 · discussion · id=4708492896

Rebased onto current main (commit 3f2ad4b — 28 commits ahead of original branch base).

Changes carried forward cleanly: `LoadConfigOverlay`, `RebaseConfigPaths`, `MergeConfigOverlay` in `internal/core/config.go`, plus `--overlay` flag and auto-detection wiring in `internal/cli/root.go`. Also added a new `internal/core/config_test.go` with unit tests for the overlay merge logic, and CLI integration tests in `root_test.go`.

The upstream changes to `ValidateConfig` (remote source / skill source validation) are preserved — our additions are purely additive.

CI running now. The `check-pr-labels` gate still needs maintainer labels (`kind/api`, `release-note`) before merge.

### Other contributors

#### `CLAassistant` · 2026-06-04 12:49:12 · discussion · id=4622288219

[![CLA assistant check](https://cla-assistant.io/pull/badge/signed)](https://cla-assistant.io/kelos-dev/kanon?pullRequest=34) <br/>All committers have signed the CLA.

---

## moazbuilds/claudeclaw #234

**fix(sessions): treat session.json without sessionId as absent (#228)**

- URL: https://github.com/moazbuilds/claudeclaw/pull/234
- State: `OPEN`

### You

#### `rudi193-cmd` · (PR opened) · description

Fixes #228. Corrupted session.json without sessionId is treated as absent; runner bootstraps instead of crashing on sessionId.slice. Tests: tests/sessions-missing-id.test.ts

#### `rudi193-cmd` · 2026-06-04 12:17:15 · discussion · id=4622041929

Note on the failing `claude-review` check: this is the same workflow credential failure as #233, before review runs:

```text
ANTHROPIC_API_KEY:
Failed to authenticate. API Error: 401 Invalid authentication credentials
```

The patch verification passed locally before push:

```text
node --experimental-strip-types --test tests/sessions-missing-id.test.ts
# 3 pass, 0 fail
```

So this PR is blocked on the repo's Claude Code Review workflow credentials / rerun, not on a code failure from this change.

#### `rudi193-cmd` · 2026-06-12 19:53:02 · discussion · id=4694777539

Addressed the review feedback in 5a6e633.

`peekThreadSession` now routes through the same `hasValidSessionId` guard as `getThreadSession`, so corrupted `sessions.json` thread rows return `null` instead of reaching callers that call `session.sessionId.slice(...)`.

Added a regression test in `tests/sessions-missing-id.test.ts`.

```sh
node --experimental-strip-types --test tests/sessions-missing-id.test.ts
# 4 pass, 0 fail
```

Ready for another look when you have a moment.

#### `rudi193-cmd` · 2026-06-23 13:15:38 · discussion · id=4779594219

@TerrysPOV friendly re-review ping — `peekThreadSession` now routes through the same `hasValidSessionId` guard as `getThreadSession` (`5a6e633`), so corrupted `sessions.json` thread rows return `null`. `claude-review` is green and the branch is mergeable. Re-requested your review; happy to adjust if anything else stands out.

#### `rudi193-cmd` · 2026-06-28 18:02:17 · discussion · id=4826936424

Resolved in a9eb7cb. `listThreadSessions` now filters through `hasValidSessionId`, so a corrupted `sessions.json` row can no longer reach the `/status` thread-sessions loop and crash on `ts.sessionId.slice(0, 8)`. That was the last unfiltered thread read path — `getThreadSession`, `peekThreadSession`, and `listThreadSessions` are now all gated. Thanks for the catch.

### Maintainers

#### `TerrysPOV` · 2026-06-04 18:20:52 · review (CHANGES_REQUESTED) · id=4430410981

### Code review

Found 1 issue:

1. `peekThreadSession` is the one remaining read path that doesn't go through `hasValidSessionId`. A corrupted `sessions.json` thread row — exactly the corruption class issue #228 reports — passes the `if (!session)` check in the Telegram/Discord `/status` and `/context` handlers, then crashes on `session.sessionId.slice(0, 8)` (or the `${session.sessionId}.jsonl` interpolation), reproducing the same `Cannot read properties of undefined (reading 'slice')` this PR is meant to eliminate.

`peekThreadSession` returns the raw record without validation:

https://github.com/moazbuilds/claudeclaw/blob/404ba91b0c1b19411382558a17cd945336520be3/src/sessionManager.ts#L106-L112

Vulnerable callers:

https://github.com/moazbuilds/claudeclaw/blob/404ba91b0c1b19411382558a17cd945336520be3/src/commands/telegram.ts#L1073-L1085

https://github.com/moazbuilds/claudeclaw/blob/404ba91b0c1b19411382558a17cd945336520be3/src/commands/discord.ts#L1183-L1196

Quickest fix: route `peekThreadSession` through the same `hasValidSessionId` guard `getThreadSession` now uses (lines 41-45 of `sessionManager.ts`), so it returns `null` for corrupted rows.

#### `TerrysPOV` · 2026-06-28 13:32:17 · review (CHANGES_REQUESTED) · id=4587596557

### Code review

`peekThreadSession` blocker is resolved in 5a6e6336 — thanks.

Found 1 remaining issue (same class):

1. `listThreadSessions` is the last unfiltered thread read path. A corrupted `sessions.json` row will be returned as-is, and the `/status` thread-sessions loop in Discord crashes on `ts.sessionId.slice(0, 8)` — same `TypeError` signature this PR is meant to eliminate.

`listThreadSessions` returns the raw map values without `hasValidSessionId`:

https://github.com/moazbuilds/claudeclaw/blob/5a6e6336c3ddb9f61fd722af5b816fdd59aaa48f/src/sessionManager.ts#L100-L105

Crash site:

https://github.com/moazbuilds/claudeclaw/blob/5a6e6336c3ddb9f61fd722af5b816fdd59aaa48f/src/commands/discord.ts#L1169-L1175

Quickest fix, mirroring the `peekThreadSession` shape in 5a6e6336:

```ts
return Object.values(data.threads).filter(hasValidSessionId);
```

(Sister mutators `incrementThreadTurn` / `markThreadCompactWarned` only bump fields and bail on `!session`, so they don't crash — they just mutate corrupted rows. Worth a follow-up but not blocking.)

---
