#!/usr/bin/env python3
"""
willow/hooks/completion_hook.py — Post-pytest atom extraction hook.

Called after pytest completes (via tests/conftest.py or hook runner).
Tracks which tests were fixed and which regressions appeared.
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import Atom
from willow.fylgja.willow_home import willow_home


@dataclass
class PytestCaseResult:
    """Single test result from a pytest JSON report."""
    name: str
    status: str  # passed|failed|skipped
    duration: float
    error_msg: Optional[str] = None


def load_test_results(path: str) -> Optional[dict]:
    """Load test results from pytest JSON report."""
    try:
        if not Path(path).exists():
            return None
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _outcome_sets(data: dict) -> dict[str, set]:
    """Nodeid sets per outcome from a pytest JSON report."""
    tests = data.get("tests", [])
    sets: dict[str, set] = {"passed": set(), "failed": set(), "all": set()}
    for t in tests:
        nodeid = t.get("nodeid")
        if not nodeid:
            continue
        sets["all"].add(nodeid)
        outcome = t.get("outcome")
        if outcome in ("passed", "failed"):
            sets[outcome].add(nodeid)
    return sets


def last_commit_touching(test_name: str) -> Optional[str]:
    """Last commit that touched the test's file — context, not causation."""
    import subprocess

    if "::" not in test_name:
        return None

    test_file = test_name.split("::")[0]

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", test_file],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def _bullet_list(names: list[str], cap: int = 5) -> str:
    text = "\n".join(f"  • {n}" for n in names[:cap])
    if len(names) > cap:
        text += f"\n  ... and {len(names) - cap} more"
    return text


def extract_test_atoms(
    before_results: Optional[dict],
    after_results: dict,
    test_run_id: Optional[str] = None,
) -> list[Atom]:
    """Extract atoms by diffing nodeid SETS between runs.

    Count-based diffing masked regressions (1 new pass + 1 new fail netted
    to zero) and labeled every currently-passing test "fixed"
    (2026-07-05 audit). Sets make both directions visible independently.
    """
    atoms = []

    if not before_results:
        return atoms

    before = _outcome_sets(before_results)
    after = _outcome_sets(after_results)

    newly_passing = sorted(after["passed"] - before["passed"])
    # Passing→failing on tests present in both runs; removed tests are not
    # regressions.
    regressed = sorted(before["passed"] & after["failed"])
    added = sorted(after["all"] - before["all"])

    if newly_passing:
        details = []
        for name in newly_passing[:5]:
            commit = last_commit_touching(name)
            details.append(f"{name} (last change: {commit[:7]})" if commit else name)
        summary = (
            f"{len(newly_passing)} test(s) newly passing.\n\n"
            "Newly passing:\n" + _bullet_list(details + newly_passing[5:])
        )
        atoms.append(
            Atom(
                title=f"Tests: {len(newly_passing)} newly passing",
                summary=summary,
                category="test",
                source_type="test_event",
                content={
                    "newly_passing": len(newly_passing),
                    "nodeids": newly_passing[:50],
                    "run_id": test_run_id,
                },
            )
        )

    if regressed:
        summary = (
            f"⚠️  {len(regressed)} test(s) regressed (were passing, now failing).\n\n"
            "Regressed:\n" + _bullet_list(regressed)
            + "\n\nNeed investigation. Check latest commits for what broke these."
        )
        atoms.append(
            Atom(
                title=f"REGRESSION: {len(regressed)} tests now failing",
                summary=summary,
                category="test",
                source_type="test_event",
                content={
                    "regressions": len(regressed),
                    "nodeids": regressed[:50],
                    "run_id": test_run_id,
                    "severity": "high" if len(regressed) > 3 else "medium",
                },
            )
        )

    if added:
        atoms.append(
            Atom(
                title=f"Added {len(added)} test(s)",
                summary=(
                    f"Test coverage grew by {len(added)} new test(s).\n\n"
                    + _bullet_list(added)
                ),
                category="test",
                source_type="test_event",
                content={
                    "new_tests": len(added),
                    "nodeids": added[:50],
                    "total_before": len(before["all"]),
                    "total_after": len(after["all"]),
                },
            )
        )

    return atoms


def write_atoms_to_kb(atoms: list[Atom]) -> int:
    """Write all atoms to knowledge base. Returns count written.

    Dedup key = title + run_id + involved nodeids, so identical re-runs
    dedup but tomorrow's "Tests: 2 newly passing" is a distinct event
    (title-only keying swallowed those forever — 2026-07-05 audit).
    """
    if not atoms:
        return 0

    import hashlib

    from willow.hooks.kb_writer import write_atom_to_kb

    count = 0
    for atom in atoms:
        raw = "|".join([
            atom.title,
            str(atom.content.get("run_id", "")),
            *atom.content.get("nodeids", []),
        ])
        dedup_key = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if write_atom_to_kb(atom, dedup_key=dedup_key):
            count += 1

    return count


def main() -> None:
    """Entry point for test completion hook."""
    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return

    report_path = os.environ.get("PYTEST_REPORT", "pytest-report.json")

    current = load_test_results(report_path)
    if not current:
        return

    prev_path = willow_home() / "last_test_results.json"
    previous = None
    if prev_path.exists():
        try:
            with open(prev_path) as f:
                previous = json.load(f)
        except Exception:
            pass

    run_id = current.get("run_id") or datetime.now(timezone.utc).isoformat()
    atoms = extract_test_atoms(previous, current, test_run_id=run_id)

    if atoms:
        count = write_atoms_to_kb(atoms)
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[test-completion] Created {count} atom(s)")

    prev_path.parent.mkdir(parents=True, exist_ok=True)
    with open(prev_path, "w") as f:
        json.dump(current, f)


if __name__ == "__main__":
    main()
