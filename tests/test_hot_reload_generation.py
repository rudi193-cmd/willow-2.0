"""Effect-asserting tests for sap/reload.py generation-swap hot reload.

These deliberately avoid shape-only assertions (the magma-layer rule): the
swap test edits a tool body ON DISK, reloads, and asserts the live instance
serves the NEW behavior through the SAME object; the poison test asserts a
broken merge leaves the OLD behavior serving.

The real-composition test runs in a subprocess: generation_reload purges
sap.*/core.*/willow.* from sys.modules, which must not contaminate the
pytest process hosting the rest of the suite.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from sap.reload import generation_reload

_MINI = "mini_gen_mcp"
_MTIME_BUMP = [0]


def _write_mini(dirpath: Path, body: str) -> None:
    import os
    import time

    path = dirpath / f"{_MINI}.py"
    path.write_text(textwrap.dedent(f"""
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("mini")
        pg = "live-pg-singleton"

        @mcp.tool()
        async def probe() -> str:
            {body}
    """), encoding="utf-8")
    # Bytecode cache validation is (mtime-seconds, size): two writes inside the
    # same second with same-length bodies would silently serve the stale .pyc.
    # Real reload triggers (git merge/checkout) always move mtime; force it here.
    _MTIME_BUMP[0] += 2
    stamp = time.time() + _MTIME_BUMP[0]
    os.utime(path, (stamp, stamp))


def _call_probe(mcp_obj) -> str:
    result = asyncio.run(mcp_obj.call_tool("probe", {}))
    return str(result)


@pytest.fixture
def mini(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_mini(tmp_path, 'return "generation-one"')
    import importlib
    importlib.invalidate_caches()
    mod = importlib.import_module(_MINI)
    yield tmp_path, mod
    sys.modules.pop(_MINI, None)


def test_swap_serves_new_body_on_same_instance(mini):
    tmp_path, mod = mini
    live = mod.mcp
    assert "generation-one" in _call_probe(live)

    _write_mini(tmp_path, 'return "generation-two"')
    result = generation_reload(
        live,
        composition_module=_MINI,
        tools_module=_MINI,
        purge_prefixes=(_MINI,),
    )
    assert result["status"] == "reloaded", result
    # Same live object, new behavior — the actual point of the ADR.
    assert "generation-two" in _call_probe(live)


def test_singletons_carry_across_generations(mini):
    tmp_path, mod = mini
    live = mod.mcp
    sentinel = object()
    mod.pg = sentinel  # simulate a lifespan-initialized singleton

    _write_mini(tmp_path, 'return "generation-two"')
    result = generation_reload(
        live,
        composition_module=_MINI,
        tools_module=_MINI,
        purge_prefixes=(_MINI,),
    )
    assert result["status"] == "reloaded", result
    assert "pg" in result["carried"]
    assert sys.modules[_MINI].pg is sentinel


def test_poisoned_module_rolls_back_to_old_generation(mini):
    tmp_path, mod = mini
    live = mod.mcp
    assert "generation-one" in _call_probe(live)

    (tmp_path / f"{_MINI}.py").write_text("this is not python (", encoding="utf-8")
    result = generation_reload(
        live,
        composition_module=_MINI,
        tools_module=_MINI,
        purge_prefixes=(_MINI,),
    )
    assert result["status"] == "rollback"
    assert "error" in result
    # Old module graph restored, old body still serving.
    assert sys.modules[_MINI] is mod
    assert "generation-one" in _call_probe(live)


def test_missing_tool_manager_refuses_cleanly():
    class NotFastMCP:
        pass

    result = generation_reload(NotFastMCP())
    assert result["status"] == "error"
    assert result["error"] == "fastmcp_internal_changed"


def test_real_composition_reloads_in_subprocess():
    """Full-stack: shadow-import the real sap.unified_mcp graph and swap.

    Subprocess-isolated because the purge would invalidate module identity
    for every other test in this pytest process.
    """
    script = textwrap.dedent("""
        import sys
        import sap.unified_mcp as unified
        from sap.reload import generation_reload

        before = len(unified.mcp._tool_manager._tools)
        result = generation_reload(unified.mcp)
        assert result["status"] == "reloaded", result
        assert result["generation_tools"] >= before, (result, before)
        assert "pg" in result["carried"] and "store" in result["carried"], result
        print("SUBPROCESS-OK", result["generation_tools"])
    """)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
        timeout=180,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "SUBPROCESS-OK" in proc.stdout
