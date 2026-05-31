"""
outcomes.py — Outcomes evaluation client.

Primary path: Anthropic Managed Agents Outcomes API (managed-agents-2026-04-01 beta).
  1. POST /v1/sessions          — create a session
  2. POST /v1/sessions/{id}/events — fire user.define_outcome
  3. Poll GET /v1/sessions/{id}   — wait for terminal evaluation

Fallback path: local Groq rubric evaluator.
  Activates when ANTHROPIC_API_KEY is unset OR the API returns 401/403.
  Uses GROQ_API_KEY + llama-3.3-70b-versatile:
    execute(prompt) → grade(output, rubric) → revise if needed → loop
"""
import json
import os
import time
import urllib.error
import urllib.request

_BASE   = "https://api.anthropic.com/v1"
_BETA   = "managed-agents-2026-04-01"
_VER    = "2023-06-01"
_POLL_INTERVAL = int(os.environ.get("WILLOW_OUTCOMES_POLL_S", "10"))
_TIMEOUT_S     = int(os.environ.get("WILLOW_OUTCOMES_TIMEOUT_S", "600"))

_GROQ_BASE  = "https://api.groq.com/openai/v1"
_GROQ_MODEL = os.environ.get("WILLOW_OUTCOMES_GROQ_MODEL", "llama-3.3-70b-versatile")

_TERMINAL = {"satisfied", "needs_revision", "max_iterations_reached", "failed", "interrupted"}
_SUCCESS  = {"satisfied"}


# ── Groq local evaluator ──────────────────────────────────────────────────────

def _groq_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return key


def _groq_chat(messages: list, model: str = _GROQ_MODEL) -> str:
    """Call Groq chat completions. Returns assistant content string."""
    body = json.dumps({"model": model, "messages": messages}).encode()
    req  = urllib.request.Request(
        f"{_GROQ_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {_groq_key()}",
            "Content-Type":  "application/json",
            "User-Agent":    "willow/2.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _grade(output: str, rubric: str) -> dict:
    """Ask Groq to grade output against rubric. Returns {satisfied, feedback}."""
    system = (
        "You are a strict output evaluator. "
        "Evaluate whether the OUTPUT satisfies ALL criteria in the RUBRIC. "
        "Reply with a JSON object: {\"satisfied\": true/false, \"feedback\": \"<one sentence>\"}"
    )
    user = f"RUBRIC:\n{rubric}\n\nOUTPUT:\n{output}"
    raw  = _groq_chat([{"role": "system", "content": system},
                        {"role": "user",   "content": user}])
    try:
        # strip markdown fences if present
        cleaned = raw.strip().strip("```json").strip("```").strip()
        return json.loads(cleaned)
    except Exception:
        satisfied = any(w in raw.lower() for w in ("satisfied: true", '"satisfied": true', "yes", "pass"))
        return {"satisfied": satisfied, "feedback": raw[:200]}


def run_outcome_local(prompt: str, rubric: str, max_iterations: int = 3,
                       title: str = "") -> dict:
    """Local Groq-based outcome evaluator loop.

    execute → grade → revise → … until satisfied or max_iterations.
    Returns same shape as run_outcome(): {result, explanation, success, iterations, session_id=None}.
    """
    messages = [{"role": "user", "content": prompt}]
    last_output  = ""
    last_grade: dict = {}

    for iteration in range(1, max_iterations + 1):
        last_output = _groq_chat(messages)
        last_grade  = _grade(last_output, rubric)

        if last_grade.get("satisfied"):
            return {
                "session_id":  None,
                "result":      "satisfied",
                "explanation": last_grade.get("feedback", ""),
                "success":     True,
                "iterations":  iteration,
            }

        # Inject feedback and ask for revision
        messages.append({"role": "assistant", "content": last_output})
        messages.append({
            "role": "user",
            "content": (
                f"Your response did not satisfy the rubric.\n"
                f"Feedback: {last_grade.get('feedback', '')}\n\n"
                f"Rubric:\n{rubric}\n\nPlease revise your response."
            ),
        })

    return {
        "session_id":  None,
        "result":      "max_iterations_reached",
        "explanation": last_grade.get("feedback", ""),
        "success":     False,
        "iterations":  max_iterations,
    }


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


_KB_DEFAULT_RUBRIC = """\
- Must be factual and specific — no vague language ("things", "various", "could be")
- Must be self-contained — a reader with no prior context should understand the main point
- Must focus on a single clear topic; no stream-of-consciousness or tangents
- Must not contain placeholder text, "TODO", incomplete thoughts, or raw code dumps
- Must be under 400 words
- Must use precise terminology relevant to the subject matter""".strip()


def refine_content(content: str, rubric: str = "", max_iterations: int = 2) -> dict:
    """Grade content against a rubric and rewrite if it fails.

    Returns:
        {content, original_content, satisfied, iterations, explanation, refined}
        refined=True means Groq rewrote the content.
    """
    effective_rubric = rubric or _KB_DEFAULT_RUBRIC
    original         = content
    last_grade: dict = {}

    for iteration in range(1, max_iterations + 1):
        last_grade = _grade(content, effective_rubric)

        if last_grade.get("satisfied"):
            return {
                "content":          content,
                "original_content": original,
                "satisfied":        True,
                "iterations":       iteration,
                "explanation":      last_grade.get("feedback", ""),
                "refined":          content != original,
            }

        # Ask Groq to rewrite to meet the rubric
        rewrite_prompt = (
            f"The following content does not meet the required rubric.\n\n"
            f"RUBRIC:\n{effective_rubric}\n\n"
            f"ISSUE:\n{last_grade.get('feedback', '')}\n\n"
            f"ORIGINAL CONTENT:\n{content}\n\n"
            f"Rewrite the content so it satisfies all rubric criteria. "
            f"Return only the rewritten content — no preamble, no explanation."
        )
        content = _groq_chat([{"role": "user", "content": rewrite_prompt}])

    # One last grade on final rewrite
    last_grade = _grade(content, effective_rubric)
    return {
        "content":          content,
        "original_content": original,
        "satisfied":        last_grade.get("satisfied", False),
        "iterations":       max_iterations,
        "explanation":      last_grade.get("feedback", ""),
        "refined":          content != original,
    }


def run_outcome(agent_id: str, environment_id: str, prompt: str, rubric: str,
                max_iterations: int = 3, title: str = "",
                timeout_s: int = _TIMEOUT_S) -> dict:
    """Full Outcomes flow. Returns {session_id, result, explanation, success, iterations}.

    Tries the Anthropic Managed Agents API first. Falls back to the local Groq evaluator
    when ANTHROPIC_API_KEY is unset or the API returns 401/403 (beta not enabled).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return run_outcome_local(prompt, rubric, max_iterations, title)

    try:
        session_id = create_session(agent_id, environment_id, title or prompt[:60])
        fire_define_outcome(session_id, prompt, rubric, max_iterations)
        evaluation = poll_outcome(session_id, timeout_s=timeout_s)
        return {
            "session_id":  session_id,
            "result":      evaluation.get("result"),
            "explanation": evaluation.get("explanation", ""),
            "success":     evaluation.get("result") in _SUCCESS,
            "iterations":  evaluation.get("iteration", 0) + 1,
        }
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            # Beta not enabled — fall through to local evaluator
            return run_outcome_local(prompt, rubric, max_iterations, title)
        raise
