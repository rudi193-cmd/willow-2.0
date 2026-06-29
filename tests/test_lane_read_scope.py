"""Default-deny KB read scoping (lane_read_scope)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.canonical_lanes import (
    LaneReadScope,
    apply_lane_scope_sql,
    atom_in_lane_scope,
    resolve_lane_read_scope,
)
from core.pg_bridge import PgBridge


@pytest.fixture(autouse=True)
def _enable_read_scope(monkeypatch):
    monkeypatch.setenv("WILLOW_LANE_READ_SCOPE", "1")
    monkeypatch.delenv("WILLOW_LANE_GRANTS", raising=False)


def test_resolve_orchestrator_excludes_personal():
    scope = resolve_lane_read_scope("willow")
    assert scope.projects is None
    assert "personal" in scope.exclude


def test_resolve_orchestrator_star_includes_personal():
    scope = resolve_lane_read_scope("willow", scope="*")
    assert scope.projects is None
    assert scope.exclude == ()


def test_resolve_project_agent_home_lane():
    scope = resolve_lane_read_scope("vishwakarma")
    assert scope.projects == ("vishwakarma",)
    assert scope.exclude == ()


def test_resolve_hanuman_reads_willow_lane_not_god_view():
    scope = resolve_lane_read_scope("hanuman")
    assert scope.projects == ("willow",)
    assert scope.exclude == ()


def test_resolve_cross_lane_denied_without_grant():
    scope = resolve_lane_read_scope("vishwakarma", project="saps1")
    assert scope.projects == ()


def test_resolve_cross_lane_with_grant(monkeypatch):
    monkeypatch.setenv("WILLOW_LANE_GRANTS", "vishwakarma:saps1")
    scope = resolve_lane_read_scope("vishwakarma", project="saps1")
    assert scope.projects == ("saps1",)


def test_apply_lane_scope_sql_empty_denies():
    filters: list = []
    params: list = []
    apply_lane_scope_sql(filters, params, lane_scope=LaneReadScope(projects=(), exclude=()))
    assert "FALSE" in filters


def test_atom_in_lane_scope():
    scope = LaneReadScope(projects=("willow",), exclude=("personal",))
    assert atom_in_lane_scope({"project": "willow"}, scope)
    assert not atom_in_lane_scope({"project": "saps1"}, scope)
    assert not atom_in_lane_scope({"project": "personal"}, scope)


@pytest.fixture
def pg():
    bridge = PgBridge()
    with bridge.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id LIKE 'lrs_%'"
        )
    bridge.conn.commit()
    return bridge


def test_knowledge_search_default_deny(pg, monkeypatch):
    monkeypatch.setenv("WILLOW_LANE_READ_SCOPE", "1")
    pg.knowledge_put({"id": "lrs_w", "project": "willow",
                      "title": "lane read willow", "summary": "w"})
    pg.knowledge_put({"id": "lrs_v", "project": "vishwakarma",
                      "title": "lane read vish", "summary": "v"})
    scope = resolve_lane_read_scope("vishwakarma")
    hits = pg.knowledge_search(
        "lane read", lane_scope=scope,
    )
    assert hits
    assert all(r["project"] == "vishwakarma" for r in hits)


def test_knowledge_search_orchestrator_minus_personal(pg, monkeypatch):
    monkeypatch.setenv("WILLOW_LANE_READ_SCOPE", "1")
    pg.knowledge_put({"id": "lrs_p", "project": "personal",
                      "title": "lane read personal", "summary": "p"})
    pg.knowledge_put({"id": "lrs_g", "project": "global",
                      "title": "lane read global", "summary": "g"})
    scope = resolve_lane_read_scope("willow")
    hits = pg.knowledge_search("lane read", lane_scope=scope)
    projects = {r["project"] for r in hits}
    assert "personal" not in projects
    assert "global" in projects


def test_knowledge_get_off_lane_returns_none(pg, monkeypatch):
    monkeypatch.setenv("WILLOW_LANE_READ_SCOPE", "1")
    pg.knowledge_put({"id": "lrs_get", "project": "saps1",
                      "title": "secret saps1", "summary": "x"})
    scope = resolve_lane_read_scope("vishwakarma")
    assert pg.knowledge_get("lrs_get", lane_scope=scope) is None
    assert pg.knowledge_get("lrs_get", lane_scope=resolve_lane_read_scope("willow", project="saps1"))


def test_read_scope_disabled_skips_filter(monkeypatch):
    monkeypatch.setenv("WILLOW_LANE_READ_SCOPE", "0")
    scope = resolve_lane_read_scope("vishwakarma")
    assert scope.projects is None
    assert scope.exclude == ()
