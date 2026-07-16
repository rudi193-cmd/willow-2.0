#!/usr/bin/env python3
"""
host_divergence_watch.py — host-dependent test divergence watchdog (loop registry tenant).
b17: FLGHDW  ΔΣ=42

Runs the suite twice with private_config_available() pinned true then false,
and reports any test whose outcome differs between the two arms.

Why this exists: resolve_store_root() and metabolic_fleet_home() branch on
private_config_available(), which reads ~/github/.willow/willow.md off the
filesystem (#466). CI never has that file, so CI only ever exercises one side
of the branch. A test that silently depends on the other side passes in CI and
fails on an operator box forever, and nothing reports it — that is exactly how
three test_canonical_home.py tests sat red on the operator laptop and green in
CI until 2026-07-16 (PR #806).

CI answers "do the tests pass here". This answers "do the tests pass the same
way anywhere", which is the question that was going unasked.

One-shot by design — wire to a systemd timer or cron. No sleeps, no loops.

Usage:
    python3 host_divergence_watch.py [--path tests/] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", Path.home() / "github" / "willow-2.0"))
sys.path.insert(0, str(WILLOW_ROOT))

FLAG_COLLECTION = "willow/flags"

# tests/test_fylgja/ is where the private_config_available() branch lives, runs
# in ~10s, and is clean in both arms. The full suite is available via --path but
# costs ~25min and needs the warm-up pass to mean anything (see run_warmup).
DEFAULT_PATH = "tests/test_fylgja/"
PLUGIN = "willow.fylgja.host_divergence_plugin"

# Arm name -> the value private_config_available() is pinned to for that arm.
ARMS = {"private_config": True, "public_fallback": False}


def _python() -> str:
    """The suite's own interpreter — a bare python3 lacks the dev deps."""
    venv = WILLOW_ROOT / ".venv-dev" / "bin" / "python3"
    return str(venv) if venv.is_file() else (os.environ.get("WILLOW_PYTHON") or sys.executable)


def run_warmup(path: str) -> None:
    """Run the suite once and throw the result away, so both arms measure a warm box.

    Whichever arm runs first pays a startup tax — Postgres test-schema init
    contending with the live fleet — and errors on tests the second arm then
    passes. Measured 2026-07-16 on tests/: first arm 76-79 failed/error, second
    arm 19-22, and swapping the arm order swapped the counts with it. That is an
    ordering effect, and without this pass it lands in the report as host-config
    divergence: 55 of 58 findings in the first full baseline were exactly that.

    Outcomes here are discarded on purpose. This pass exists to be the victim.
    """
    print(f"host_divergence_watch: warm-up pass starting ({path})", flush=True)
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = ""
    cmd = [_python(), "-m", "pytest", path, "-q", "--tb=no", "-p", "no:cacheprovider"]
    try:
        subprocess.run(cmd, cwd=WILLOW_ROOT, env=env, capture_output=True, timeout=1800)
    except Exception as exc:  # noqa: BLE001
        # A failed warm-up is not fatal: the arms still run, they are just noisier.
        print(
            f"host_divergence_watch: warm-up pass failed ({type(exc).__name__}) "
            "— arms may report ordering noise",
            file=sys.stderr, flush=True,
        )
        return
    print(
        f"host_divergence_watch: warm-up pass done in {time.monotonic() - started:.0f}s "
        "(outcomes discarded)",
        flush=True,
    )


def run_arm(path: str, private: bool, report: Path) -> tuple[dict[str, str], str]:
    """Run pytest with private_config_available() pinned. Returns ({test_id: outcome}, error).

    Everything else about the environment is left exactly as it is: the arms
    must differ in one variable, or unrelated fixtures collapse and their
    wreckage reads as divergence.

    Prints before and after: a full-suite arm runs for minutes with pytest's
    output captured, so without these lines a live run and a wedged one look
    identical from outside.
    """
    print(f"host_divergence_watch: arm {report.stem} starting ({path})", flush=True)
    started = time.monotonic()
    env = os.environ.copy()
    env["WILLOW_FORCE_PRIVATE_CONFIG"] = "1" if private else "0"
    env["PYTEST_ADDOPTS"] = ""
    cmd = [
        _python(), "-m", "pytest", path,
        "-q", "--tb=no", "-p", "no:cacheprovider", "-p", PLUGIN,
        f"--junitxml={report}",
    ]
    try:
        subprocess.run(cmd, cwd=WILLOW_ROOT, env=env, capture_output=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return {}, "pytest timed out after 1800s"
    except Exception as exc:  # noqa: BLE001
        return {}, f"{type(exc).__name__}: {exc}"
    if not report.is_file():
        return {}, "pytest produced no junit report"
    outcomes = parse_report(report)
    failed = sum(1 for o in outcomes.values() if o in ("failed", "error"))
    print(
        f"host_divergence_watch: arm {report.stem} done in {time.monotonic() - started:.0f}s "
        f"— {len(outcomes)} test(s), {failed} failed/error",
        flush=True,
    )
    return outcomes, ""


def parse_report(report: Path) -> dict[str, str]:
    """Map each test to its outcome. Collection errors surface as their own ids."""
    outcomes: dict[str, str] = {}
    try:
        root = ET.parse(report).getroot()
    except ET.ParseError as exc:
        return {"__parse_error__": str(exc)[:200]}
    for case in root.iter("testcase"):
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        outcome = "passed"
        for child in case:
            tag = child.tag
            if tag in ("failure", "error", "skipped"):
                outcome = tag if tag != "failure" else "failed"
                break
        outcomes[test_id] = outcome
    return outcomes


def compare(arms: dict[str, dict[str, str]]) -> list[dict]:
    """Any test whose outcome is not identical across arms is a finding.

    A test missing from one arm counts as divergent too — it means collection
    itself moved, which is the same class of defect.
    """
    names = list(arms)
    all_ids: set[str] = set()
    for outcomes in arms.values():
        all_ids.update(outcomes)
    findings: list[dict] = []
    for test_id in sorted(all_ids):
        seen = {name: arms[name].get(test_id, "absent") for name in names}
        if len(set(seen.values())) > 1:
            findings.append({"test": test_id, **seen})
    return findings


def open_flag(findings: list[dict], counts: dict) -> None:
    """Best-effort: a store problem is reported to stderr, never fatal here."""
    try:
        from core import soil

        soil.put(
            FLAG_COLLECTION,
            f"flag-host-divergence-{int(time.time())}",
            {
                "type": "flag",
                "flag_state": "open",
                "title": (
                    f"Host-dependent test divergence: {len(findings)} test(s) "
                    "change outcome with private willow-config present"
                ),
                "source": "host_divergence_watch",
                "findings": findings[:20],
                "counts": counts,
                "opened_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"host_divergence_watch: flag write failed — {exc}", file=sys.stderr, flush=True)


def write_report(path: Path, findings: list[dict], counts: dict) -> None:
    """Dump the complete findings. The console prints only the first few, and a
    flag holds only 20 — a run that finds more than that must still leave the
    whole set somewhere durable or the evidence dies with the terminal."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "findings": findings,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"host_divergence_watch: report written — {path}", flush=True)
    except OSError as exc:
        print(f"host_divergence_watch: report write failed — {exc}", file=sys.stderr, flush=True)


def write_heartbeat(tick_ok: bool, counts: dict, error: str = "") -> None:
    """Prove this watchdog is alive — core/watchmen.py reads this via the loop registry."""
    try:
        from core.loop_heartbeat import write

        payload: dict = {"counts": counts}
        if error:
            payload["error"] = error
        if not write("host_divergence_watch", tick_ok=tick_ok, **payload):
            raise RuntimeError("write returned false")
    except Exception as exc:  # noqa: BLE001
        print(f"host_divergence_watch: heartbeat write failed — {exc}", file=sys.stderr, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="host-dependent test divergence watchdog (loop registry tenant)"
    )
    ap.add_argument("--path", default=DEFAULT_PATH, help="pytest target path")
    ap.add_argument("--dry-run", action="store_true", help="report only; do not open a SOIL flag")
    ap.add_argument("--report", type=Path, default=None,
                    help="write complete findings as JSON to this path")
    ap.add_argument("--no-warmup", action="store_true",
                    help="skip the discarded warm-up pass (faster; reports ordering noise)")
    args = ap.parse_args()

    if not args.no_warmup:
        run_warmup(args.path)

    arms: dict[str, dict[str, str]] = {}
    errors: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="host-divergence-") as tmp:
        base = Path(tmp)
        for arm, private in ARMS.items():
            outcomes, error = run_arm(args.path, private, base / f"{arm}.xml")
            arms[arm] = outcomes
            if error:
                errors[arm] = error

    counts = {arm: len(outcomes) for arm, outcomes in arms.items()}

    # A broken arm must not read as "no divergence found".
    if errors:
        detail = "; ".join(f"{arm}: {err}" for arm, err in errors.items())
        print(f"host_divergence_watch: arm FAILED to run — {detail}", file=sys.stderr, flush=True)
        write_heartbeat(tick_ok=False, counts=counts, error=detail)
        return 2

    findings = compare(arms)
    counts["diverged"] = len(findings)

    # Always print — a silent success is indistinguishable from a dead watchdog.
    print(
        f"host_divergence_watch: {counts.get('private_config', 0)} test(s) with private config, "
        f"{counts.get('public_fallback', 0)} without, {len(findings)} divergent",
        flush=True,
    )

    # Written on a clean pass too — "0 divergent, here is the run" is evidence.
    if args.report:
        write_report(args.report, findings, counts)

    if not findings:
        write_heartbeat(tick_ok=True, counts=counts)
        return 0

    shown = findings[:5]
    for f in shown:
        print(f"host_divergence_watch:   {f}", flush=True)
    if len(findings) > len(shown):
        rest = len(findings) - len(shown)
        where = f"see {args.report}" if args.report else "re-run with --report to capture all"
        print(f"host_divergence_watch:   … {rest} more not shown ({where})", flush=True)
    if not args.dry_run:
        open_flag(findings, counts)
    write_heartbeat(tick_ok=True, counts=counts)
    return 1


if __name__ == "__main__":
    sys.exit(main())
