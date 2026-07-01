"""mem_jeles_ask default-verification regression (Phase 4 of the Jeles roadmap).

verify_claims already existed and worked correctly (see test_jeles_verify.py) but
required an explicit verify=true from the caller. This checks the tool's default
flipped to verify=True (opt-out, not opt-in) without re-testing verify_claims
itself or fighting the @mcp.tool()/@sap_gate() decorator stack with a full async
mock harness — the actual branching logic (`if verify: result["verification"] = ...`)
is unconditional on the caller-supplied flag in all three mem_jeles_ask paths
(corpus-hit, single-answer, multi-perspective), so the default value is the only
thing this phase changes.
"""
import inspect
import os

os.environ.setdefault("WILLOW_AGENT_NAME", "test-agent")

import sap.sap_mcp as sap_mcp


def test_mem_jeles_ask_verify_defaults_true():
    sig = inspect.signature(sap_mcp.mem_jeles_ask)
    assert sig.parameters["verify"].default is True


def test_mem_jeles_ask_verify_still_overridable():
    """Callers can still pass verify=False for a cheaper/faster answer."""
    sig = inspect.signature(sap_mcp.mem_jeles_ask)
    assert sig.parameters["verify"].annotation in (bool, "bool")
