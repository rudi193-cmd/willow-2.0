"""trim_task_result — MCP task responses must not echo the bwrap mount table.

Regression: every willow_run/kart_task_run response carried the full
sandbox_manifest (~2k tokens), twice via the willow_run facade.
"""
from core.kart_execute import trim_task_result

MANIFEST = {"engine": "bwrap", "bound_ro": ["/etc"], "bound_rw": ["/home"]}


def _result(**extra):
    return {
        "returncode": 0,
        "stdout": "ok",
        "stderr": "",
        "sandbox_setup": "ok",
        "sandbox_manifest": dict(MANIFEST),
        **extra,
    }


def test_success_drops_manifest():
    out = trim_task_result(_result(), "completed")
    assert "sandbox_manifest" not in out
    assert out["sandbox_setup"] == "ok"
    assert out["stdout"] == "ok"


def test_failure_keeps_manifest():
    out = trim_task_result(_result(returncode=2), "failed")
    assert out["sandbox_manifest"] == MANIFEST


def test_stored_row_not_mutated():
    result = _result()
    trim_task_result(result, "completed")
    assert result["sandbox_manifest"] == MANIFEST


def test_non_dict_passthrough():
    assert trim_task_result(None, "completed") is None
    assert trim_task_result("text", "completed") == "text"
    assert trim_task_result({"stdout": "x"}, "completed") == {"stdout": "x"}
