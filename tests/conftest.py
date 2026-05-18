"""Shared test fixtures — isolated test database, fresh schema each session."""
import os
import sys
from pathlib import Path
import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
sys.path = [REPO_ROOT] + [p for p in sys.path if "willow-1.7" not in p]

os.environ["WILLOW_PG_DB"] = "willow_19_test"

# PGUSER is the standard psycopg2/libpq env var — use it as a fallback so CI
# workflows that set PGUSER=postgres but not WILLOW_PG_USER still connect correctly.
if not os.environ.get("WILLOW_PG_USER") and os.environ.get("PGUSER"):
    os.environ["WILLOW_PG_USER"] = os.environ["PGUSER"]

_PG_USER = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
_PG_HOST = os.environ.get("WILLOW_PG_HOST")
_PG_PORT = os.environ.get("WILLOW_PG_PORT")

print(f"[conftest] pg user={_PG_USER!r} host={_PG_HOST!r} port={_PG_PORT!r}", flush=True)


def _ensure_test_db():
    """Create willow_19_test if it doesn't exist."""
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
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'willow_19_test'")
            if not cur.fetchone():
                cur.execute("CREATE DATABASE willow_19_test")
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


def pytest_sessionfinish(session, exitstatus):
    """Hook: after test session completes, trigger atom extraction."""
    if not os.environ.get("WILLOW_ATOM_EXTRACTION"):
        return

    try:
        # Generate pytest JSON report
        report_path = Path(REPO_ROOT) / ".pytest_results.json"
        results = {
            "total": session.testsfailed + session.testspassed + session.testswarned,
            "passed": session.testspassed,
            "failed": session.testsfailed,
            "skipped": session.testswarned,
            "duration": session.duration or 0,
            "tests": [],  # Stub; full extraction would parse test items
        }

        # Write report
        with open(report_path, "w") as f:
            import json
            json.dump(results, f)

        # Trigger atom extraction
        from willow.hooks.test_completion import main as test_completion_main
        os.environ["PYTEST_REPORT"] = str(report_path)
        test_completion_main()

    except Exception as e:
        if os.environ.get("WILLOW_ATOM_VERBOSE"):
            print(f"[conftest] test_completion error: {e}")
