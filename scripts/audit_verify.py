#!/usr/bin/env python3
"""audit_verify.py — definition-of-done harness for the Kart sandbox audit.

The 06-10 plan optimized merge-velocity, not closure: nothing checked that a
"done" finding actually closed, so partial closures looked identical to full
ones (AUDIT_PLAN_VERIFICATION_2026-06-11, "done != closed"). This is the
governor it lacked.

One machine-checkable check per finding. A finding is CLOSED only if its check
passes NOW — not because a PR referenced it. Findings shipped in Phase 0/1 are
**gated**: if any regresses to OPEN, the run exits non-zero (CI guard). Findings
still in flight report OPEN/DEFERRED for visibility without failing the run.

Usage:
    python3 scripts/audit_verify.py            # human table
    python3 scripts/audit_verify.py --json     # machine-readable
    python3 scripts/audit_verify.py --quiet     # summary line only

Exit code: 0 if no gated finding is OPEN and no check errored; 1 otherwise.

Reference: docs/audits/KART_SANDBOX_AUDIT_2026-06-11.md (S1-S18),
           docs/audits/AUDIT_PLAN_VERIFICATION_2026-06-11.md (V1-V3).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core import kart_sandbox as ks  # noqa: E402

CLOSED, OPEN, DEFERRED, ERROR = "CLOSED", "OPEN", "DEFERRED", "ERROR"


# ── helpers ───────────────────────────────────────────────────────────────────

def _mounts() -> dict[str, bool]:
    """host(str) -> read_only(bool)."""
    return {str(h): ro for h, _c, ro in ks.collect_bind_mounts()}


def _argv(allow_net: bool = False) -> list[str]:
    return ks.build_bwrap_argv(allow_net=allow_net)


def _source(rel: str) -> str:
    p = _REPO / rel
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _adjacent(argv: list[str], a: str, b: str) -> bool:
    return any(argv[i] == a and argv[i + 1] == b for i in range(len(argv) - 1))


# ── checks (each returns (state, evidence)) ─────────────────────────────────────

def chk_s1():
    """~/.ssh never bound; gh credentials absent on a no-net task."""
    ssh = str((Path.home() / ".ssh").resolve())
    if ssh in _mounts():
        return OPEN, f"{ssh} is bound"
    gh = str((Path.home() / ".config" / "gh"))
    if gh in _argv(allow_net=False):
        return OPEN, "~/.config/gh present without allow_net"
    return CLOSED, "~/.ssh unbound; gh gated on allow_net"


def chk_s2():
    return (CLOSED, "--new-session present") if "--new-session" in _argv() \
        else (OPEN, "--new-session missing (TIOCSTI/CVE-2017-5226 open)")


def chk_s4():
    m = _mounts()
    gh = str((Path.home() / "github").resolve())
    root = str(ks.willow_repo_root().resolve()) if ks.willow_repo_root() else None
    if gh in m and m[gh] is not True:
        return OPEN, "~/github is read-write"
    if root and m.get(root) is not False:
        return OPEN, "WILLOW_ROOT not read-write"
    return CLOSED, "~/github read-only; WILLOW_ROOT read-write"


def chk_gap_a():
    """SAFE store + systemd config not writable by an arbitrary task."""
    m = _mounts()
    sd = str((Path.home() / ".config" / "systemd").resolve())
    if sd in m and m[sd] is not True:
        return OPEN, "~/.config/systemd is read-write"
    bad = [h for h, ro in m.items() if "/SAFE" in h and ro is False]
    if bad:
        return OPEN, f"SAFE path read-write: {bad[0]}"
    return CLOSED, "SAFE + systemd config read-only"


def chk_gap_b():
    """Credential env-vars stripped without allow_net, present with it."""
    os.environ["ANTHROPIC_API_KEY"] = "probe-value"
    try:
        no_net = ks.kart_env(allow_net=False)
        with_net = ks.kart_env(allow_net=True)
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    if "ANTHROPIC_API_KEY" in no_net:
        return OPEN, "credential leaked to no-net task"
    if with_net.get("ANTHROPIC_API_KEY") != "probe-value":
        return OPEN, "credential missing on net task"
    return CLOSED, "stripped without net, present with net"


def chk_s11():
    argv = _argv()
    if "/tmp" in _mounts():
        return OPEN, "/tmp is a host bind"
    if not _adjacent(argv, "--tmpfs", "/tmp"):
        return OPEN, "/tmp tmpfs missing"
    return CLOSED, "/tmp is private tmpfs, not a host bind"


def chk_s12():
    argv = _argv()
    missing = [f for f in ("--unshare-ipc", "--unshare-uts") if f not in argv]
    return (CLOSED, "ipc+uts namespaces unshared") if not missing \
        else (OPEN, f"missing {missing}")


def chk_s14():
    return (CLOSED, "--as-pid-1 present (zombie reaper)") if "--as-pid-1" in _argv() \
        else (OPEN, "--as-pid-1 missing")


def chk_s16():
    return (CLOSED, "/dev/shm tmpfs present") if _adjacent(_argv(), "--tmpfs", "/dev/shm") \
        else (OPEN, "/dev/shm tmpfs missing")


def chk_kp3():
    """Boundary manifest attaches to results; unreachable-path note fires."""
    os.environ["WILLOW_KART_NO_BWRAP"] = "1"
    try:
        _status, result = ks.run_shell_result_for_task("echo x", timeout=10)
    finally:
        os.environ.pop("WILLOW_KART_NO_BWRAP", None)
    if "sandbox_manifest" not in result:
        return OPEN, "sandbox_manifest not attached to result"
    m = ks.sandbox_manifest(allow_net=False)
    if m.get("engine") == "bwrap":
        notes = ks.unreachable_notes(f"cat {Path.home()}/.claude/x", m)
        if not notes:
            return OPEN, "unreachable-path note did not fire under bwrap"
    return CLOSED, "manifest attached; empty != absent note fires"


def chk_s15():
    src = _source("core/kart_sandbox.py")
    if "--json-status-fd" in src and "sandbox_setup" in src:
        return CLOSED, "--json-status-fd wired; sandbox_setup reported"
    return OPEN, "setup-failure not distinguished from command-failure"


def chk_s6():
    env = ks.kart_env(ks.willow_repo_root())
    local_bin = str(Path.home() / ".local" / "bin")
    return (CLOSED, "~/.local/bin on sandbox PATH") if local_bin in env["PATH"].split(":") \
        else (OPEN, "~/.local/bin missing from PATH")


def chk_s9():
    """A missing required bind must log a warning, not fail silently.

    collect_bind_mounts (Tier-1, kart stage-5) now delegates to kartikeya, so the
    warning-emitting source may live there instead of in this repo. Check
    willow-2.0's own source first (pre-delegation / future re-inlining), then fall
    back to kartikeya's installed source.
    """
    needle = "required bind target missing"
    if needle in _source("core/kart_sandbox.py"):
        return CLOSED, "missing required bind logs a warning"
    try:
        import kartikeya.sandbox as _kk_sandbox
        kk_src = Path(_kk_sandbox.__file__).read_text(encoding="utf-8")
    except (ImportError, OSError):
        kk_src = ""
    if needle in kk_src:
        return CLOSED, "missing required bind logs a warning (kartikeya)"
    return OPEN, "silent bind skip"


def chk_s5():
    """Transcript stores ro-bound (KP4, operator decision 2026-06-12: bind).

    ~/.claude/projects + ~/.cursor in the optional-ro tier; the
    credential-bearing ~/.claude root in no bind list at all.
    """
    cfg = ks.load_sandbox_config(ks.willow_repo_root())
    optional_ro = cfg.get("bind_try_read_only", [])
    missing = [p for p in ("{{HOME}}/.claude/projects", "{{HOME}}/.cursor")
               if p not in optional_ro]
    if missing:
        return OPEN, f"not in bind_try_read_only: {missing}"
    for key in ("bind_read_only", "bind_read_write", "bind_try", "bind_try_read_only"):
        if "{{HOME}}/.claude" in cfg.get(key, []):
            return OPEN, f"~/.claude root bound via {key} (credential exposure)"
    m = _mounts()
    for rel in (".claude/projects", ".cursor"):
        host = str((Path.home() / rel).resolve())
        if host in m and m[host] is not True:
            return OPEN, f"{host} bound read-write"
    return CLOSED, "transcript stores ro; ~/.claude root unbound"


def chk_soil1():
    """SOIL layout unified: core/soil.py is the WillowStore shim and the legacy
    '/store' addressing is hard-rejected (operator decisions 2026-06-12)."""
    shim = _source("core/soil.py")
    if "WillowStore" not in shim:
        return OPEN, "core/soil.py is not the WillowStore shim"
    ws = _source("core/willow_store.py")
    if "Legacy '/store' collection addressing rejected" not in ws:
        return OPEN, "WillowStore does not reject legacy '/store' names"
    return CLOSED, "soil.py shims WillowStore; '/store' names rejected"


def chk_s10():
    """Durable per-task log artifacts (KP7): write_task_log exists, the
    unclipped output rides to it, and execute_task_row references log_dir."""
    ks_src = _source("core/kart_sandbox.py")
    if "def write_task_log" not in ks_src:
        return OPEN, "write_task_log missing from kart_sandbox"
    if "_full_stdout" not in ks_src:
        return OPEN, "unclipped output not captured for the artifact"
    ke_src = _source("core/kart_execute.py")
    if "log_dir" not in ke_src or "write_task_log" not in ke_src:
        return OPEN, "execute_task_row does not write/reference the artifact"
    return CLOSED, ".kart-logs/<id>/ artifact wired; log_dir in result"


def chk_s8():
    """Symlink binds generalized (KP6b): every configured bind path that is a
    host symlink is auto re-emitted as --symlink — no hand-maintained list."""
    if not hasattr(ks, "collect_config_symlinks"):
        return OPEN, "collect_config_symlinks missing"
    links = ks.collect_config_symlinks()
    argv = _argv()
    missing = [
        link for _target, link in links
        if not any(
            argv[i] == "--symlink" and argv[i + 2] == link
            for i in range(len(argv) - 2)
        )
    ]
    if missing:
        return OPEN, f"config symlinks not re-emitted: {missing}"
    return CLOSED, f"{len(links)} config symlink(s) auto re-emitted in argv"


# ── Felis-catus P0 (EA422361) — shipped #398–#403, gated 2026-06-16 ───────────

def chk_fcat1():
    """journal_watcher poll must rollback so PgBridge does not idle-in-txn."""
    jw = _source("agents/hanuman/bin/journal_watcher.py")
    if "pg.conn.rollback()" not in jw:
        return OPEN, "journal_watcher missing post-poll rollback"
    return CLOSED, "journal_watcher rolls back after poll read"


def chk_fcat2():
    """grove_listen reconnect must close the stale connection."""
    gl = _source("willow/grove_listen.py")
    if "stale.close()" not in gl:
        return OPEN, "grove_listen reconnect does not close stale connection"
    return CLOSED, "grove_listen closes stale connection on reconnect"


def chk_fcat3():
    """Kart must fail closed when bwrap is intended but absent."""
    ks_src = _source("core/kart_sandbox.py")
    use_fn = ks_src.split("def use_bwrap", 1)[-1].split("\ndef ", 1)[0]
    if "return bwrap_available()" in use_fn:
        return OPEN, "use_bwrap still conflates intent with bwrap_available()"
    ke = _source("core/kart_execute.py")
    if "bwrap not found" not in ke:
        return OPEN, "kart_execute missing fail-closed bwrap guard"
    return CLOSED, "use_bwrap expresses intent; kart_execute fails closed"


def chk_fcat4():
    """Kart hybrid security scan wired at queue + execute."""
    ke = _source("core/kart_execute.py")
    if "check_kart_task" not in ke:
        return OPEN, "kart_execute does not call check_kart_task"
    kts = _source("core/kart_task_scan.py")
    if "security_scan" not in kts:
        return OPEN, "kart_task_scan missing security_scan import"
    return CLOSED, "hybrid Kart security scan wired (kart_task_scan + execute)"


def chk_fcat5():
    """Fleet runners must import assert_grove (EA422361 P2 — fleet-wide chokepoint)."""
    from core.grove_gate import FLEET_GROVE_GATED

    missing: list[str] = []
    for rel in FLEET_GROVE_GATED:
        text = _source(rel)
        if not text.strip():
            missing.append(f"{rel} (file missing)")
            continue
        if "assert_grove" not in text and "_assert_grove" not in text:
            missing.append(rel)
    if missing:
        return OPEN, f"fleet scripts without assert_grove: {', '.join(missing)}"
    return CLOSED, f"{len(FLEET_GROVE_GATED)} fleet scripts Grove-gated"


def chk_fcat6():
    """grove_listen _PidLock must fail closed — no duplicate listeners on lock error."""
    gl = _source("willow/grove_listen.py")
    if "class _PidLock" not in gl:
        return OPEN, "_PidLock class missing"
    block = gl.split("class _PidLock", 1)[1].split("\ndef ", 1)[0]
    if "better to have monitoring than silence" in block:
        return OPEN, "_PidLock still proceeds on lock failure"
    if "lock failed" in block and "SystemExit(1)" in block:
        return CLOSED, "_PidLock fails closed on unexpected lock errors"
    return OPEN, "_PidLock missing fail-closed exit"


# ── V-series (verification class — file state) ─────────────────────────────────

def chk_v1():
    """No .claude skill still carries the placeholder description."""
    hits = []
    skills_dir = _REPO / ".claude" / "skills"
    for sk in skills_dir.glob("*/SKILL.md") if skills_dir.is_dir() else []:
        head = sk.read_text(encoding="utf-8")[:400]
        if "Willow Fylgja skill:" in head:
            hits.append(sk.parent.name)
    return (CLOSED, "no placeholder descriptions") if not hits \
        else (OPEN, f"placeholder description in: {', '.join(hits)}")


def chk_v2():
    """.claude/commands/startup.md must not open with @markdownai above YAML."""
    p = _REPO / ".claude" / "commands" / "startup.md"
    if not p.exists():
        return OPEN, "startup.md absent"
    first = p.read_text(encoding="utf-8").splitlines()[0].strip() if p.read_text(encoding="utf-8") else ""
    return (OPEN, "line 1 is @markdownai (frontmatter-detection bug)") \
        if first.startswith("@markdownai") else (CLOSED, "frontmatter ordering correct")


def chk_v3():
    """repo_fleet_sweep.py is scheduled (systemd / cron / routine)."""
    import subprocess
    try:
        out = subprocess.run(
            ["grep", "-rl", "repo_fleet_sweep", str(_REPO / "systemd")],
            capture_output=True, text=True, timeout=10,
        )
        scheduled = bool(out.stdout.strip())
    except Exception:
        scheduled = False
    return (CLOSED, "sweep scheduled") if scheduled \
        else (OPEN, "repo_fleet_sweep.py built but never scheduled")


# ── registry ────────────────────────────────────────────────────────────────

# gate=True → must stay CLOSED or the run fails (shipped Phase 0/1).
# gate=False, deferred → reported, never fails the run.
CHECKS = [
    # Phase 0 — security (gated)
    {"id": "S1",  "axis": "security",      "gate": True,  "fn": chk_s1,   "title": "~/.ssh dropped; gh gated"},
    {"id": "S2",  "axis": "security",      "gate": True,  "fn": chk_s2,   "title": "--new-session (CVE-2017-5226)"},
    {"id": "S4",  "axis": "security",      "gate": True,  "fn": chk_s4,   "title": "~/github read-only"},
    {"id": "GAP-A", "axis": "security",    "gate": True,  "fn": chk_gap_a, "title": "SAFE + systemd read-only"},
    {"id": "GAP-B", "axis": "security",    "gate": True,  "fn": chk_gap_b, "title": "credential env-vars gated"},
    {"id": "S11", "axis": "isolation",     "gate": True,  "fn": chk_s11,  "title": "/tmp private tmpfs"},
    {"id": "S12", "axis": "isolation",     "gate": True,  "fn": chk_s12,  "title": "ipc+uts unshared"},
    {"id": "S14", "axis": "robustness",    "gate": True,  "fn": chk_s14,  "title": "--as-pid-1 reaper"},
    {"id": "S16", "axis": "reliability",   "gate": True,  "fn": chk_s16,  "title": "/dev/shm tmpfs"},
    # Phase 1 — visibility (gated)
    {"id": "S3",  "axis": "visibility",    "gate": True,  "fn": chk_kp3,  "title": "boundary manifest (empty!=absent)"},
    {"id": "S15", "axis": "observability", "gate": True,  "fn": chk_s15,  "title": "setup-fail != command-fail"},
    {"id": "S6",  "axis": "reliability",   "gate": True,  "fn": chk_s6,   "title": "~/.local/bin on PATH"},
    {"id": "S9",  "axis": "maintainability", "gate": True, "fn": chk_s9,  "title": "bind-skip warning"},
    # Verification class — open work (informational)
    {"id": "V1",  "axis": "bookkeeping",   "gate": False, "fn": chk_v1,   "title": "no placeholder skill descriptions"},
    {"id": "V2",  "axis": "bookkeeping",   "gate": False, "fn": chk_v2,   "title": "startup.md frontmatter"},
    {"id": "V3",  "axis": "bookkeeping",   "gate": False, "fn": chk_v3,   "title": "repo_fleet_sweep scheduled"},
    # Phase 2 — KP4 transcript binds (gated; operator decision 2026-06-12)
    {"id": "S5",  "axis": "visibility",    "gate": True,  "fn": chk_s5,   "title": "transcript stores ro (KP4)"},
    # SOIL layout unification (gated; operator decisions 2026-06-12)
    {"id": "SOIL1", "axis": "maintainability", "gate": True, "fn": chk_soil1, "title": "SOIL dual-layout unified (shim + /store reject)"},
    # Felis-catus P0 remediation (gated; shipped #398–#403, EA422361)
    {"id": "FCAT1", "axis": "reliability",   "gate": True, "fn": chk_fcat1, "title": "journal_watcher idle-in-txn rollback"},
    {"id": "FCAT2", "axis": "reliability",   "gate": True, "fn": chk_fcat2, "title": "grove_listen reconnect closes stale conn"},
    {"id": "FCAT3", "axis": "security",      "gate": True, "fn": chk_fcat3, "title": "Kart bwrap fail-closed guard"},
    {"id": "FCAT4", "axis": "security",      "gate": True, "fn": chk_fcat4, "title": "Kart hybrid security scan wired"},
    {"id": "FCAT5", "axis": "reliability",   "gate": True, "fn": chk_fcat5, "title": "fleet scripts Grove-gated (FLEET_GROVE_GATED)"},
    {"id": "FCAT6", "axis": "reliability",   "gate": True, "fn": chk_fcat6, "title": "grove_listen PidLock fail-closed"},
    # Phase 2 — KP7 durable failure artifacts (gated)
    {"id": "S10", "axis": "observability", "gate": True,  "fn": chk_s10,  "title": "durable .kart-logs/<id>/ artifacts (KP7)"},
    # Phase 2 — KP6b symlink-bind generalization (gated)
    {"id": "S8",  "axis": "maintainability", "gate": True,  "fn": chk_s8,   "title": "config symlinks auto re-emitted (KP6b)"},
    # Deferred by design — named, not silent
    {"id": "S7",  "axis": "observability", "gate": False, "deferred": True, "title": "opaque &&-chain failures (partial)"},
    {"id": "S13", "axis": "security",      "gate": False, "deferred": True, "title": "seccomp syscall filter — declined 2026-06-12, --new-session accepted as CVE-2017-5226 coverage"},
    {"id": "S18", "axis": "maintainability", "gate": False, "deferred": True, "title": "worktree self-management (KP8)"},
]


def run_all() -> list[dict]:
    results = []
    for c in CHECKS:
        if c.get("deferred"):
            results.append({**_meta(c), "state": DEFERRED, "evidence": "deferred — see audit"})
            continue
        try:
            state, evidence = c["fn"]()
        except Exception as e:  # a check that errors is itself a failure signal
            state, evidence = ERROR, f"check raised: {e}"
        results.append({**_meta(c), "state": state, "evidence": evidence})
    return results


def _meta(c: dict) -> dict:
    return {"id": c["id"], "title": c["title"], "axis": c["axis"], "gate": c["gate"]}


def _exit_code(results: list[dict]) -> int:
    for r in results:
        if r["state"] == ERROR:
            return 1
        if r["gate"] and r["state"] != CLOSED:
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kart sandbox audit definition-of-done harness")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="summary line only")
    args = ap.parse_args(argv)

    results = run_all()
    code = _exit_code(results)

    if args.json:
        print(json.dumps({"results": results, "exit_code": code}, indent=2))
        return code

    closed = sum(1 for r in results if r["state"] == CLOSED)
    deferred = sum(1 for r in results if r["state"] == DEFERRED)
    open_or_err = [r for r in results if r["state"] in (OPEN, ERROR)]
    gated_open = [r for r in open_or_err if r["gate"]]

    if not args.quiet:
        glyph = {CLOSED: "✅", OPEN: "❌", DEFERRED: "⏸", ERROR: "\U0001f4a5"}
        print("Kart sandbox audit — definition of done")
        print("=" * 64)
        for r in results:
            gate = "gate" if r["gate"] else "    "
            print(f"  {glyph.get(r['state'],'?')} {r['id']:<6} [{gate}] {r['title']}")
            print(f"          {r['evidence']}")
        print("=" * 64)

    print(
        f"{closed} closed / {len(open_or_err)} open / {deferred} deferred"
        f"  —  gated regressions: {len(gated_open)}"
        f"  —  {'PASS' if code == 0 else 'FAIL'}"
    )
    if gated_open:
        print("  REGRESSED (gated, must be closed): " + ", ".join(r["id"] for r in gated_open))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
