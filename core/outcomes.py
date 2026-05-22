"""
outcomes.py — Anthropic Managed Agents Outcomes API client.

Wraps the three-step Outcomes flow:
  1. POST /v1/sessions          — create a session
  2. POST /v1/sessions/{id}/events — fire user.define_outcome
  3. Poll GET /v1/sessions/{id}   — wait for terminal evaluation

Beta header: managed-agents-2026-04-01
"""
import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

_BASE   = "https://api.anthropic.com/v1"
_BETA   = "managed-agents-2026-04-01"
_VER    = "2023-06-01"
_POLL_INTERVAL = int(os.environ.get("WILLOW_OUTCOMES_POLL_S", "10"))
_TIMEOUT_S     = int(os.environ.get("WILLOW_OUTCOMES_TIMEOUT_S", "600"))

_TERMINAL = {"satisfied", "needs_revision", "max_iterations_reached", "failed", "interrupted"}
_SUCCESS  = {"satisfied"}


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def _headers() -> dict:
    return {
        "x-api-key":         _api_key(),
        "anthropic-version": _VER,
        "anthropic-beta":    _BETA,
        "Content-Type":      "application/json",
    }


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{_BASE}{path}",
        data=json.dumps(body).encode(),
        headers=_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _get(path: str) -> dict:
    req = urllib.request.Request(
        f"{_BASE}{path}",
        headers=_headers(),
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def create_session(agent_id: str, environment_id: str, title: str = "") -> str:
    """Create a Managed Agent session. Returns session_id."""
    body = {"agent": agent_id, "environment_id": environment_id}
    if title:
        body["title"] = title
    resp = _post("/sessions", body)
    return resp["id"]


def fire_define_outcome(session_id: str, description: str, rubric: str,
                         max_iterations: int = 3) -> dict:
    """Fire user.define_outcome event. Agent starts immediately on receipt."""
    body = {"events": [{
        "type":           "user.define_outcome",
        "description":    description,
        "rubric":         {"type": "text", "content": rubric},
        "max_iterations": max_iterations,
    }]}
    return _post(f"/sessions/{session_id}/events", body)


def poll_outcome(session_id: str,
                 timeout_s: int = _TIMEOUT_S,
                 poll_interval: int = _POLL_INTERVAL) -> dict:
    """Poll until terminal outcome evaluation. Returns last evaluation dict."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        session = _get(f"/sessions/{session_id}")
        evals   = session.get("outcome_evaluations", [])
        if evals:
            latest = evals[-1]
            if latest.get("result") in _TERMINAL:
                return latest
        time.sleep(poll_interval)
    return {"result": "timeout", "explanation": f"exceeded {timeout_s}s poll window"}


def run_outcome(agent_id: str, environment_id: str, prompt: str, rubric: str,
                max_iterations: int = 3, title: str = "",
                timeout_s: int = _TIMEOUT_S) -> dict:
    """Full Outcomes flow. Returns {session_id, result, explanation, success, iterations}."""
    session_id = create_session(agent_id, environment_id, title or prompt[:60])
    fire_define_outcome(session_id, prompt, rubric, max_iterations)
    evaluation = poll_outcome(session_id, timeout_s=timeout_s)
    return {
        "session_id":   session_id,
        "result":       evaluation.get("result"),
        "explanation":  evaluation.get("explanation", ""),
        "success":      evaluation.get("result") in _SUCCESS,
        "iterations":   evaluation.get("iteration", 0) + 1,
    }
