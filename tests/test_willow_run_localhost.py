"""willow_run facade must expose and thread allow_localhost (loopback-only lane).

kart_sandbox has supported the '# allow_localhost' directive since it landed,
and agent_task_submit exposes it — but the willow_run facade (the primary
agent-facing entry point) did not, so 12.5% of failed Kart tasks were embedder
ConnectionErrors with no supported opt-in path. AST-level guard so the param
cannot silently drop out of the facade again.
"""
import ast
from pathlib import Path

SAP = Path(__file__).resolve().parents[1] / "sap" / "sap_mcp.py"


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _kwarg_names(call):
    return {kw.arg for kw in call.keywords}


def test_willow_run_exposes_allow_localhost():
    tree = ast.parse(SAP.read_text())
    fn = _func(tree, "willow_run")
    args = [a.arg for a in fn.args.args]
    assert "allow_localhost" in args


def test_willow_run_threads_allow_localhost_to_submit_and_detached():
    tree = ast.parse(SAP.read_text())
    fn = _func(tree, "willow_run")
    calls = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            target = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if target in ("agent_task_submit", "_willow_run_detached"):
                calls[target] = _kwarg_names(node)
    assert "allow_localhost" in calls.get("agent_task_submit", set())
    assert "allow_localhost" in calls.get("_willow_run_detached", set())


def test_detached_helper_threads_allow_localhost_to_launcher():
    tree = ast.parse(SAP.read_text())
    fn = _func(tree, "_willow_run_detached")
    assert "allow_localhost" in [a.arg for a in fn.args.kwonlyargs]
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            target = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if target == "launch_detached":
                assert "allow_localhost" in _kwarg_names(node)
                return
    raise AssertionError("launch_detached call not found in _willow_run_detached")
