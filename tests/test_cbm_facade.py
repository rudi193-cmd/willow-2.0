"""Tests for sap.cbm_facade bounded CBM wrapper."""
from __future__ import annotations

from unittest.mock import patch

from sap.cbm_facade import (
    _prepare_cypher,
    project_name,
    query,
    resolve_project,
    search,
    trace,
    verify_callers,
)


def test_prepare_cypher_appends_limit():
    q, warnings = _prepare_cypher("MATCH (f:Function) RETURN f", 10)
    assert "LIMIT 10" in q
    assert any("F-003" in w for w in warnings)


def test_prepare_cypher_warns_on_left_arrow():
    q, warnings = _prepare_cypher("MATCH (a)<-[r]-(b) RETURN a LIMIT 5", 5)
    assert any("F-001" in w or "risky" in w for w in warnings)


@patch("sap.cbm_facade.cli")
def test_resolve_project_exact_root(mock_cli):
    mock_cli.return_value = {
        "projects": [
            {
                "name": "home-sean-campbell-github-willow-2.0",
                "root_path": "/home/sean-campbell/github/willow-2.0",
                "nodes": 1,
                "edges": 2,
            }
        ]
    }
    from pathlib import Path

    out = resolve_project(Path("/home/sean-campbell/github/willow-2.0"))
    assert out["project"] == "home-sean-campbell-github-willow-2.0"


@patch("sap.cbm_facade.cli")
def test_search_filters_tests(mock_cli):
    mock_cli.return_value = {
        "results": [
            {"file_path": "core/pg_bridge.py", "name": "get_connection"},
            {"file_path": "tests/test_pg_bridge.py", "name": "test_x"},
        ],
        "total": 2,
    }
    with patch("sap.cbm_facade.project_name", return_value="proj"):
        out = search("get_connection", limit=10, exclude_tests=True)
    assert len(out["results"]) == 1
    assert out["results"][0]["file_path"] == "core/pg_bridge.py"
    assert "limitations" in out


@patch("sap.cbm_facade.cli")
def test_trace_truncates_callers(mock_cli):
    callers = [{"name": f"c{i}", "hop": 1} for i in range(80)]
    mock_cli.return_value = {"callers": callers}
    with patch("sap.cbm_facade.project_name", return_value="proj"):
        out = trace("foo", max_callers=10)
    assert len(out["callers"]) == 10
    assert out["callers_truncated"] == 70


@patch("sap.cbm_facade._grep_callers", return_value=[{"file": "core/x.py", "line": 1, "text": "foo()"}])
@patch("sap.cbm_facade.trace")
def test_verify_callers_merges_graph_and_grep(mock_trace, mock_grep):
    mock_trace.return_value = {
        "callers": [{"qualified_name": "mod.fn", "name": "fn"}],
        "project": "proj",
    }
    out = verify_callers("get_connection")
    assert out["graph_caller_count"] == 1
    assert out["grep_caller_count"] == 1
    assert "F-004" in out["verdict"]


@patch("sap.cbm_facade.cli")
def test_query_passes_bounded_cypher(mock_cli):
    mock_cli.return_value = {"rows": []}
    with patch("sap.cbm_facade.project_name", return_value="proj"):
        query("MATCH (n) RETURN n.name", max_rows=12)
    args = mock_cli.call_args[0]
    assert args[0] == "query_graph"
    payload = args[1]
    assert "LIMIT 12" in payload["query"]
    assert payload["max_rows"] == 12


@patch.dict("os.environ", {"WILLOW_CBM_PROJECT": "override-proj"}, clear=False)
def test_project_name_env_override():
    assert project_name() == "override-proj"
