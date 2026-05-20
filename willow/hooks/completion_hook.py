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
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import Atom


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


def parse_pytest_json(data: dict) -> dict:
    """Extract summary from pytest JSON report."""
    tests = data.get("tests", [])
    return {
        "total": len(tests),
        "passed": sum(1 for t in tests if t["outcome"] == "passed"),
        "failed": sum(1 for t in tests if t["outcome"] == "failed"),
        "skipped": sum(1 for t in tests if t["outcome"] == "skipped"),
        "duration": data.get("duration", 0),
    }


def find_test_fixing_commit(test_name: str) -> Optional[str]:
    """Find which commit fixed a failing test."""
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


def extract_test_atoms(
    before_results: Optional[dict],
    after_results: dict,
    test_run_id: Optional[str] = None,
) -> list[Atom]:
    """Extract atoms from test results changes."""
    atoms = []

    if not before_results:
        return atoms

    before = parse_pytest_json(before_results)
    after = parse_pytest_json(after_results)

    newly_passing = after["passed"] - before["passed"]
    if newly_passing > 0:
        summary = f"{newly_passing} test(s) newly passing.\n\n"

        tests_list = []
        for test_data in after_results.get("tests", []):
            if test_data["outcome"] == "passed":
                test_name = test_data.get("nodeid", "unknown")
                fix_commit = find_test_fixing_commit(test_name)
                if fix_commit:
                    tests_list.append(f"{test_name} (fixed by {fix_commit[:7]})")
                else:
                    tests_list.append(test_name)

        if tests_list:
            summary += "Fixed:\n" + "\n".join(f"  • {t}" for t in tests_list[:5])
            if len(tests_list) > 5:
                summary += f"\n  ... and {len(tests_list) - 5} more"

        atoms.append(
            Atom(
                title=f"Tests: {newly_passing} newly passing",
                summary=summary,
                category="test",
                source_type="test_event",
                content={
                    "newly_passing": newly_passing,
                    "test_count": len(tests_list),
                    "run_id": test_run_id,
                },
            )
        )

    regressions = before["passed"] - after["passed"]
    if regressions > 0:
        summary = (
            f"⚠️  {regressions} test(s) regressed (were passing, now failing).\n\n"
            "Need investigation. Check latest commits for what broke these."
        )
        atoms.append(
            Atom(
                title=f"REGRESSION: {regressions} tests now failing",
                summary=summary,
                category="test",
                source_type="test_event",
                content={
                    "regressions": regressions,
                    "run_id": test_run_id,
                    "severity": "high" if regressions > 3 else "medium",
                },
            )
        )

    if after["total"] > before["total"]:
        new_tests = after["total"] - before["total"]
        atoms.append(
            Atom(
                title=f"Added {new_tests} test(s)",
                summary=f"Test coverage improved by {new_tests} new test(s).",
                category="test",
                source_type="test_event",
                content={
                    "new_tests": new_tests,
                    "total_before": before["total"],
                    "total_after": after["total"],
                },
            )
        )

    return atoms


def write_atoms_to_kb(atoms: list[Atom]) -> int:
    """Write all atoms to knowledge base. Returns count written."""
    if not atoms:
        return 0

    from willow.hooks.kb_writer import write_atom_to_kb

    count = 0
    for atom in atoms:
        if write_atom_to_kb(atom, dedup_key=atom.title):
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

    prev_path = Path.home() / ".willow" / "last_test_results.json"
    previous = None
    if prev_path.exists():
        try:
            with open(prev_path) as f:
                previous = json.load(f)
        except Exception:
            pass

    atoms = extract_test_atoms(previous, current, test_run_id=current.get("duration"))

    if atoms:
        count = write_atoms_to_kb(atoms)
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[test-completion] Created {count} atom(s)")

    prev_path.parent.mkdir(parents=True, exist_ok=True)
    with open(prev_path, "w") as f:
        json.dump(current, f)


if __name__ == "__main__":
    main()
