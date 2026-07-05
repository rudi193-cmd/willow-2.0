"""Shared test fixtures — isolated test database, fresh schema each session."""
import os
import sys
from pathlib import Path
import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
sys.path = [REPO_ROOT] + [p for p in sys.path if "willow-1.7" not in p]

os.environ["WILLOW_PG_DB"] = "willow_20_test"
os.environ.setdefault("WILLOW_HUMAN_GATE", "off")
os.environ["WILLOW_SUPPRESS_NOTIFY"] = "1"

# PGUSER is the standard psycopg2/libpq env var — use it as a fallback so CI
# workflows that set PGUSER=postgres but not WILLOW_PG_USER still connect correctly.
if not os.environ.get("WILLOW_PG_USER") and os.environ.get("PGUSER"):
    os.environ["WILLOW_PG_USER"] = os.environ["PGUSER"]

_PG_USER = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
_PG_HOST = os.environ.get("WILLOW_PG_HOST")
_PG_PORT = os.environ.get("WILLOW_PG_PORT")

print(f"[conftest] pg user={_PG_USER!r} host={_PG_HOST!r} port={_PG_PORT!r}", flush=True)


def _ensure_test_db():
    """Create willow_20_test if it doesn't exist."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname="postgres",
            user=_PG_USER,
            host=_PG_HOST,
            port=_PG_PORT,
            connect_timeout=10,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'willow_20_test'")
            if not cur.fetchone():
                cur.execute("CREATE DATABASE willow_20_test")
        conn.close()
    except Exception as e:
        print(f"  test db bootstrap warning: {e}")


@pytest.fixture(scope="session", autouse=True)
def init_pg_schema():
    """Bootstrap test database and initialize schema once per session."""
    _ensure_test_db()
    try:
        import importlib
        import core.pg_bridge as pgb
        importlib.reload(pgb)
        conn = pgb._connect()
        pgb.init_schema(conn)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  pg schema init warning: {e}")


# Per-test outcomes collected live. The old sessionfinish read
# session.testspassed / session.testswarned — attributes pytest's Session has
# never had — so it raised AttributeError on every run, invisibly, and the
# report it meant to write carried a hardcoded-empty "tests" list anyway
# (2026-07-03 audit, bugs 4 and 5). This is the real extraction.
_TEST_OUTCOMES: dict = {}


def pytest_runtest_logreport(report):
    if report.when == "call":
        _TEST_OUTCOMES[report.nodeid] = report.outcome
    elif report.when == "setup" and report.outcome != "passed":
        # setup-time skip or error is the test's outcome
        _TEST_OUTCOMES[report.nodeid] = report.outcome


def pytest_sessionfinish(session, exitstatus):
    """Hook: after test session completes, trigger atom extraction."""
    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return

    try:
        from datetime import datetime, timezone

        report_path = Path(REPO_ROOT) / ".pytest_results.json"
        tests = [
            {"nodeid": nodeid, "outcome": outcome}
            for nodeid, outcome in sorted(_TEST_OUTCOMES.items())
        ]
        results = {
            "total": len(tests),
            "passed": sum(1 for t in tests if t["outcome"] == "passed"),
            "failed": sum(1 for t in tests if t["outcome"] == "failed"),
            "skipped": sum(1 for t in tests if t["outcome"] == "skipped"),
            "run_id": datetime.now(timezone.utc).isoformat(),
            "tests": tests,
        }

        with open(report_path, "w") as f:
            import json
            json.dump(results, f)

        # Trigger atom extraction
        from willow.hooks.completion_hook import main as test_completion_main
        os.environ["PYTEST_REPORT"] = str(report_path)
        test_completion_main()

    except Exception as e:
        # Never silent: extraction failing must leave at least one line.
        print(f"[conftest] test_completion error: {e}", file=sys.stderr)


@pytest.fixture
def mock_norn_subpasses(monkeypatch):
    """Keep norn_pass unit tests off Postgres/migrations (community_pass, demote_stale_pass)."""
    from core import metabolic

    monkeypatch.setattr(metabolic, "compost_pass", lambda dry_run=False: 1)
    monkeypatch.setattr(metabolic, "community_pass", lambda dry_run=False: 2)
    monkeypatch.setattr(metabolic, "measure_heartbeat", lambda: 0.75)
    monkeypatch.setattr(metabolic, "demote_stale_pass", lambda dry_run=False: 0)
