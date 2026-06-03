"""Tests for metabolic.py — Norn pass runner."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_norn_pass_returns_report():
    from core.metabolic import norn_pass
    report = norn_pass(dry_run=True)
    assert "composted" in report
    assert "communities" in report
    assert "heartbeat" in report


def test_heartbeat_returns_float():
    from core.metabolic import measure_heartbeat
    score = measure_heartbeat()
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_compost_pass_dry_run_returns_count():
    from core.metabolic import compost_pass
    count = compost_pass(dry_run=True)
    assert isinstance(count, int)
    assert count >= 0


def test_community_pass_dry_run_returns_count():
    from core.metabolic import community_pass
    count = community_pass(dry_run=True)
    assert isinstance(count, int)
    assert count >= 0


def test_norn_pass_squeakdog_field():
    from core.metabolic import norn_pass
    report = norn_pass(dry_run=True)
    assert "squeakdog" in report
    assert isinstance(report["squeakdog"], bool)


def test_norn_pass_report_has_intelligence_fields():
    from core.metabolic import norn_pass
    report = norn_pass(dry_run=True)
    for field in ("draugr", "serendipity", "dark_matter", "revelations", "mirror", "mycorrhizal"):
        assert field in report, f"missing field: {field}"


def test_community_pass_continues_after_per_project_failure(monkeypatch):
    """A failure on one project must not abort the rest of the loop."""
    import types
    from core import metabolic

    call_count = 0

    class FakeCursor:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def execute(self, *a, **kw):
            pass
        def fetchall(self):
            return [("title_a",), ("title_b",)]

    class FakeBridge:
        def __init__(self):
            self.conn = types.SimpleNamespace(cursor=lambda: FakeCursor())

        def knowledge_put(self, record):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("simulated HNSW crash")

    fake_pgb = types.SimpleNamespace(PgBridge=FakeBridge)
    monkeypatch.setattr(metabolic, "_load_pg_bridge", lambda: fake_pgb)

    # Two projects — first raises, second must still be attempted
    original_community_pass = metabolic.community_pass

    def patched_get_projects(bridge):
        return [("proj_a", 10), ("proj_b", 10)]

    # Patch the initial query by monkeypatching bridge.conn.cursor fetchall for the project query
    class FakeBridgeWithProjects(FakeBridge):
        _project_query_done = False

        def __init__(self):
            super().__init__()
            outer_cursor = self

            class ProjectCursor(FakeCursor):
                def fetchall(self_inner):
                    if not FakeBridgeWithProjects._project_query_done:
                        FakeBridgeWithProjects._project_query_done = True
                        return [("proj_a", 10), ("proj_b", 10)]
                    return [("title_x",)]

            self.conn = types.SimpleNamespace(cursor=lambda: ProjectCursor())

    fake_pgb2 = types.SimpleNamespace(PgBridge=FakeBridgeWithProjects)
    monkeypatch.setattr(metabolic, "_load_pg_bridge", lambda: fake_pgb2)

    count = metabolic.community_pass(dry_run=False)
    # First project failed, second succeeded — expect 1 written
    assert count == 1
