#!/usr/bin/env python3
"""
willow/hooks/test_completion.py — Test completion hook entry point.

Called after pytest completes (via conftest.py hook or CI integration).
Tracks which tests were fixed and which regressions appeared.
Compares before/after test results to create atoms for changes.
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.atom_extractor import Atom
from core.pg_bridge import PgBridge


@dataclass
class TestResult:
    """Single test result."""
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
    """Find which commit fixed a failing test.

    Strategy: run git blame on the test file, find recent modifications.
    This is approximate — the "fix" might be in the code, not the test.
    """
    import subprocess

    # Extract file path from test name (e.g., "tests/test_foo.py::test_bar" -> "tests/test_foo.py")
    if "::" not in test_name:
        return None

    test_file = test_name.split("::")[0]

    try:
        # Get the most recent commit that modified this test file
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", test_file],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def extract_test_atoms(
    before_results: Optional[dict],
    after_results: dict,
    test_run_id: Optional[str] = None
) -> list[Atom]:
    """Extract atoms from test results changes.

    Args:
        before_results: Previous test run (or None for initial)
        after_results: Current test run
        test_run_id: ID for this test run (for tracking)
    """
    atoms = []

    if not before_results:
        # First run, no comparisons to make
        return atoms

    before = parse_pytest_json(before_results)
    after = parse_pytest_json(after_results)

    # Newly passing tests
    newly_passing = after["passed"] - before["passed"]
    if newly_passing > 0:
        summary = f"{newly_passing} test(s) newly passing.\n\n"

        # Try to link to fixing commits
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
            summary += f"Fixed:\n" + "\n".join(f"  • {t}" for t in tests_list[:5])
            if len(tests_list) > 5:
                summary += f"\n  ... and {len(tests_list)-5} more"

        atom = Atom(
            title=f"Tests: {newly_passing} newly passing",
            summary=summary,
            category="test",
            source_type="test_event",
            content={
                "newly_passing": newly_passing,
                "test_count": len(tests_list),
                "run_id": test_run_id,
            }
        )
        atoms.append(atom)

    # Regressions (tests that were passing, now failing)
    regressions = before["passed"] - after["passed"]
    if regressions > 0:
        summary = f"⚠️  {regressions} test(s) regressed (were passing, now failing).\n\n"
        summary += "Need investigation. Check latest commits for what broke these."

        atom = Atom(
            title=f"REGRESSION: {regressions} tests now failing",
            summary=summary,
            category="test",
            source_type="test_event",
            content={
                "regressions": regressions,
                "run_id": test_run_id,
                "severity": "high" if regressions > 3 else "medium",
            }
        )
        atoms.append(atom)

    # Test count growth (tracking productivity)
    if after["total"] > before["total"]:
        new_tests = after["total"] - before["total"]
        atom = Atom(
            title=f"Added {new_tests} test(s)",
            summary=f"Test coverage improved by {new_tests} new test(s).",
            category="test",
            source_type="test_event",
            content={
                "new_tests": new_tests,
                "total_before": before["total"],
                "total_after": after["total"],
            }
        )
        atoms.append(atom)

    return atoms


def write_atoms_to_kb(atoms: list[Atom]) -> int:
    """Write all atoms to knowledge base. Returns count written."""
    if not atoms:
        return 0

    try:
        bridge = PgBridge()
        cur = bridge.conn.cursor()

        for atom in atoms:
            cur.execute("""
                INSERT INTO knowledge
                (id, title, summary, category, source_type, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                atom.id,
                atom.title,
                atom.summary,
                atom.category,
                atom.source_type,
                atom.created_at,
            ))

        bridge.conn.commit()
        bridge.conn.close()
        return len(atoms)

    except Exception as e:
        if Path(Path.home() / ".willow").exists():
            # Queue to file if KB unavailable
            pending_path = Path(Path.home() / ".willow" / "pending_test_atoms.jsonl")
            with open(pending_path, "a") as f:
                for atom in atoms:
                    f.write(json.dumps(atom.to_dict()) + "\n")
        return 0


def main():
    """Entry point for test completion hook."""
    import os

    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return

    # Look for pytest JSON report
    report_path = os.environ.get("PYTEST_REPORT", "pytest-report.json")

    # Load current results
    current = load_test_results(report_path)
    if not current:
        return

    # Load previous results (if exists)
    prev_path = Path.home() / ".willow" / "last_test_results.json"
    previous = None
    if prev_path.exists():
        try:
            with open(prev_path) as f:
                previous = json.load(f)
        except Exception:
            pass

    # Extract atoms
    atoms = extract_test_atoms(previous, current, test_run_id=current.get("duration"))

    # Write to KB
    if atoms:
        count = write_atoms_to_kb(atoms)
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[test-completion] Created {count} atom(s)")

    # Save current results as "previous" for next run
    prev_path.parent.mkdir(parents=True, exist_ok=True)
    with open(prev_path, "w") as f:
        json.dump(current, f)


if __name__ == "__main__":
    main()
