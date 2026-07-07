"""Task templates + output validators for the lane-4 SLM corpus.

Each entry mirrors a production call site exactly — same system prompt,
same user-message construction, same output contract — so a model trained
on this corpus drops into the existing code without prompt changes.

Provenance (file:line refers to repo state at harvest time):
  orin_summarize    agents/orin/tasks.py:84   (mistral:7b)
  orin_classify     agents/orin/tasks.py:108  (mistral:7b)
  orin_extract      agents/orin/tasks.py:147  (mistral:7b)
  orin_tension      agents/orin/tasks.py:173  (mistral:7b)
  intake_route      core/intake_promote.py:52 (classify specialization)
  jeles_corroborate agents/hanuman/bin/extract_jeles_corpus.py:90
  stop_summary      willow/fylgja/events/stop.py:303 (llama3.2:3b)
  dream_tension     agents/hanuman/bin/auto_dream.py:119 (llama3.2:3b)
  dream_synthesis   agents/hanuman/bin/auto_dream.py:135 (mistral:7b)
  drift_verdict     agents/hanuman/bin/kb_truth_drift.py:181 (llama3.2:3b)
  drift_redraft     agents/hanuman/bin/kb_truth_drift.py:483 (llama3.2:3b)
"""
from __future__ import annotations

import json
from typing import Callable

from agents.orin.tasks import _parse_json

# ── payload budgets (match production truncation) ────────────────────────────

EXTRACT_CONTENT_BUDGET = 3_600   # agents/orin/tasks.py:_EXTRACT_CONTENT_BUDGET
ROUTE_CONTENT_BUDGET = 800       # core/intake_promote.py:llm_route

OBLIGATION_VALUES = ["task", "decision", "reference", "fyi", "none"]
EXTRACT_CATEGORIES = ["general", "code", "governance", "architecture"]
ROUTE_CATEGORIES = ["jeles_atoms", "knowledge", "opus", "binder_queue"]
CORROBORATE_CATEGORIES = ["corroborates", "unrelated", "contradicts"]

ROUTE_CONTEXT = (
    "You are routing a knowledge record to the right storage tier.\n"
    "jeles_atoms: externally sourced, has URL or institution, web search result, cited fact.\n"
    "knowledge: internal project fact, agent observation, session history, decision, code note.\n"
    "opus: agent reasoning process, feedback principle, meta-observation about the system itself.\n"
    "binder_queue: uncertain, sensitive, needs human review, or does not fit the others."
)

CORROBORATE_CONTEXT = (
    "Does the citation list corroborate, contradict, or is it unrelated "
    "to the claim? Score corroborates=1.0, unrelated=0.1, contradicts=0.0."
)

DRIFT_PROMPT = """\
You are checking whether a knowledge base claim still accurately describes code.

CLAIM (KB atom):
Title: {title}
Summary: {summary}

CURRENT CODE ({file_path}):
{file_content}

Does this claim still accurately describe the code above?

Answer with exactly one of:
  current     — the claim is still accurate
  drifted     — the claim is no longer accurate (specific mismatch found)
  uncertain   — cannot determine from this file alone

Then on a new line, write one sentence of evidence (minimum 30 characters). Be specific.

Format:
VERDICT: <current|drifted|uncertain>
EVIDENCE: <one sentence>"""

DRAFT_PROMPT = """\
You are updating a knowledge base atom because the code it describes has changed.

ORIGINAL ATOM TITLE: {title}
ORIGINAL ATOM SUMMARY: {summary}

DRIFT EVIDENCE (what changed):
{evidence}

CURRENT CODE ({file_path}):
{file_content}

Write a concise updated summary (2-4 sentences) that accurately describes what the
code does now. Be specific. Do not mention that this is an update or reference the
original atom. Output only the summary text, nothing else."""


# ── message builders ──────────────────────────────────────────────────────────

def _classify_messages(content: str, categories: list[str], context: str) -> list[dict]:
    cats = ", ".join(f'"{c}"' for c in categories)
    obs = ", ".join(f'"{o}"' for o in OBLIGATION_VALUES)
    system = (
        "You are a precise classifier. "
        "Respond ONLY with valid JSON, no prose. "
        f'Format: {{"category": <one of [{cats}]>, "confidence": <0.0-1.0>, "reason": "...", "obligation": <one of [{obs}]>}}'
    )
    user = (
        f"Classify the following text.\n"
        f"Categories: [{cats}]\n"
        f"Obligation: what does this content want from the reader? [{obs}]\n\n"
        f"Text:\n{content}"
    )
    if context:
        user = f"Context:\n{context}\n\n{user}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_messages(task_type: str, payload: dict) -> list[dict]:
    """Return the exact chat messages production would send for this payload."""
    if task_type == "orin_summarize":
        system = (
            "You are a concise knowledge summarizer. "
            "Respond ONLY with valid JSON, no prose before or after. "
            'Format: {"bullets": ["...", "..."], "one_line": "..."}'
        )
        user = f"Summarize the following into 3-5 key bullet points:\n\n{payload['content']}"
        if payload.get("context"):
            user = f"Context:\n{payload['context']}\n\n{user}"
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    if task_type == "orin_classify":
        return _classify_messages(
            payload["content"], payload["categories"], payload.get("context", "")
        )

    if task_type == "intake_route":
        return _classify_messages(
            payload["content"][:ROUTE_CONTENT_BUDGET], ROUTE_CATEGORIES, ROUTE_CONTEXT
        )

    if task_type == "jeles_corroborate":
        return _classify_messages(
            payload["content"], CORROBORATE_CATEGORIES, CORROBORATE_CONTEXT
        )

    if task_type == "orin_extract":
        system = (
            "You are a knowledge extraction engine. "
            "Extract factual, self-contained knowledge atoms from the provided text. "
            "Respond ONLY with a valid JSON array, no prose. "
            'Each element: {"title": "...", "summary": "...", "category": "general|code|governance|architecture"}'
        )
        user = (
            "Extract up to 5 knowledge atoms from the following. "
            "Each atom must be self-contained and factual:\n\n"
            f"{payload['content'][:EXTRACT_CONTENT_BUDGET]}"
        )
        if payload.get("context"):
            user = f"Context:\n{payload['context']}\n\n{user}"
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    if task_type == "orin_tension":
        system = (
            "You detect logical contradictions between knowledge claims. "
            "Respond ONLY with valid JSON, no prose. "
            'Format: {"conflict": true|false, "score": <0.0-1.0>, "reason": "..."}'
        )
        user = (
            f"Do these two claims contradict each other?\n\n"
            f"Claim A: {payload['atom_a']}\n\n"
            f"Claim B: {payload['atom_b']}"
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    if task_type == "stop_summary":
        user = (
            "Summarize in one sentence, then list up to 5 keyword phrases.\n"
            'Respond as JSON only: {"one_line": "...", "bullets": ["...", ...]}\n\n'
            f"{payload['content']}"
        )
        return [{"role": "user", "content": user}]

    if task_type == "dream_tension":
        user = (
            f"A: {payload['title_a']}\n{payload['summary_a'][:200]}\n\n"
            f"B: {payload['title_b']}\n{payload['summary_b'][:200]}\n\n"
            "Reply TENSION or COMPATIBLE (one word), then one sentence."
        )
        return [
            {"role": "system", "content": "You are a knowledge graph auditor."},
            {"role": "user", "content": user},
        ]

    if task_type == "dream_synthesis":
        user = (
            f"Reflecting on {payload['atom_count']} recent knowledge atoms "
            f"for agent {payload['agent']}:\n\n"
            f"{payload['atom_digest']}\n\n"
            "In 3-4 sentences: what patterns, connections, or gaps do you notice? "
            "What should be explored or reconciled next?"
        )
        return [
            {"role": "system",
             "content": "You are a thoughtful knowledge synthesist. Be concise and specific."},
            {"role": "user", "content": user},
        ]

    if task_type == "drift_verdict":
        user = DRIFT_PROMPT.format(
            title=payload["title"],
            summary=payload["summary"][:1500],
            file_path=payload["file_path"],
            file_content=payload["file_content"],
        )
        return [
            {"role": "system",
             "content": "You are a precise code auditor. Follow the output format exactly."},
            {"role": "user", "content": user},
        ]

    if task_type == "drift_redraft":
        user = DRAFT_PROMPT.format(
            title=payload["title"],
            summary=payload["summary"][:500],
            evidence=payload["evidence"],
            file_path=payload["file_path"],
            file_content=payload["file_content"],
        )
        return [
            {"role": "system",
             "content": "You are a precise technical writer updating knowledge base documentation."},
            {"role": "user", "content": user},
        ]

    raise ValueError(f"unknown task_type: {task_type!r}")


# ── output validators ─────────────────────────────────────────────────────────
# Each returns (ok, reason). ok means the output satisfies the production
# contract strictly — no fallback-parser leniency, since training targets
# should be exactly what the strict path expects.

def _v_summarize(text: str) -> tuple[bool, str]:
    parsed = _parse_json(text)
    if not isinstance(parsed, dict):
        return False, "not a JSON object"
    if not isinstance(parsed.get("bullets"), list) or not parsed["bullets"]:
        return False, "missing/empty bullets"
    if not isinstance(parsed.get("one_line"), str) or not parsed["one_line"].strip():
        return False, "missing one_line"
    if len(parsed["bullets"]) > 5:
        return False, "more than 5 bullets"
    return True, ""


def _v_classify(categories: list[str]) -> Callable[[str], tuple[bool, str]]:
    def check(text: str) -> tuple[bool, str]:
        parsed = _parse_json(text)
        if not isinstance(parsed, dict):
            return False, "not a JSON object"
        if parsed.get("category") not in categories:
            return False, f"category not in {categories}"
        try:
            conf = float(parsed.get("confidence"))
        except (TypeError, ValueError):
            return False, "confidence not a number"
        if not 0.0 <= conf <= 1.0:
            return False, "confidence out of range"
        if not isinstance(parsed.get("reason"), str) or not parsed["reason"].strip():
            return False, "missing reason"
        if parsed.get("obligation", "none") not in OBLIGATION_VALUES:
            return False, "bad obligation"
        return True, ""
    return check


def _v_extract(text: str) -> tuple[bool, str]:
    parsed = _parse_json(text)
    if not isinstance(parsed, list):
        return False, "not a JSON array"
    if not parsed or len(parsed) > 5:
        return False, "must contain 1-5 atoms"
    for a in parsed:
        if not isinstance(a, dict) or not a.get("title") or not a.get("summary"):
            return False, "atom missing title/summary"
        if a.get("category") not in EXTRACT_CATEGORIES:
            return False, "atom category invalid"
    return True, ""


def _v_tension(text: str) -> tuple[bool, str]:
    parsed = _parse_json(text)
    if not isinstance(parsed, dict):
        return False, "not a JSON object"
    if not isinstance(parsed.get("conflict"), bool):
        return False, "conflict not boolean"
    try:
        score = float(parsed.get("score"))
    except (TypeError, ValueError):
        return False, "score not a number"
    if not 0.0 <= score <= 1.0:
        return False, "score out of range"
    if not isinstance(parsed.get("reason"), str) or not parsed["reason"].strip():
        return False, "missing reason"
    return True, ""


def _v_stop_summary(text: str) -> tuple[bool, str]:
    parsed = _parse_json(text)
    if not isinstance(parsed, dict):
        return False, "not a JSON object"
    if not isinstance(parsed.get("one_line"), str) or not parsed["one_line"].strip():
        return False, "missing one_line"
    bullets = parsed.get("bullets")
    if not isinstance(bullets, list) or len(bullets) > 5:
        return False, "bullets missing or >5"
    if any(not isinstance(b, str) for b in bullets):
        return False, "non-string bullet"
    return True, ""


def _v_dream_tension(text: str) -> tuple[bool, str]:
    first = text.strip().split("\n")[0].strip()
    word = first.split()[0].rstrip(".,:;").upper() if first.split() else ""
    if word not in ("TENSION", "COMPATIBLE"):
        return False, "first word must be TENSION or COMPATIBLE"
    rest = text.strip()[len(first.split()[0]):].strip(" .,:;\n")
    if len(rest) < 15:
        return False, "missing one-sentence justification"
    return True, ""


def _v_dream_synthesis(text: str) -> tuple[bool, str]:
    t = text.strip()
    if not t:
        return False, "empty"
    sentences = [s for s in t.replace("\n", " ").split(". ") if s.strip()]
    if len(sentences) < 2 or len(sentences) > 6:
        return False, "expected roughly 3-4 sentences"
    return True, ""


def _v_drift_verdict(text: str) -> tuple[bool, str]:
    verdict, evidence = "", ""
    for line in text.splitlines():
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip().lower()
        elif line.startswith("EVIDENCE:"):
            evidence = line.split(":", 1)[1].strip()
    if verdict not in ("current", "drifted", "uncertain"):
        return False, "bad or missing VERDICT line"
    if len(evidence) < 30:
        return False, "EVIDENCE under 30 chars"
    return True, ""


def _v_drift_redraft(text: str) -> tuple[bool, str]:
    t = text.strip()
    if len(t) < 40:
        return False, "too short"
    if t.lower().startswith(("update", "the original", "this atom")):
        return False, "references the update/original atom"
    return True, ""


VALIDATORS: dict[str, Callable[[str], tuple[bool, str]]] = {
    "orin_summarize": _v_summarize,
    "orin_classify": None,  # per-record: needs the record's categories
    "intake_route": _v_classify(ROUTE_CATEGORIES),
    "jeles_corroborate": _v_classify(CORROBORATE_CATEGORIES),
    "orin_extract": _v_extract,
    "orin_tension": _v_tension,
    "stop_summary": _v_stop_summary,
    "dream_tension": _v_dream_tension,
    "dream_synthesis": _v_dream_synthesis,
    "drift_verdict": _v_drift_verdict,
    "drift_redraft": _v_drift_redraft,
}

TASK_TYPES = sorted(VALIDATORS)


def validate_output(task_type: str, payload: dict, text: str) -> tuple[bool, str]:
    """Validate a candidate assistant output against the task's contract."""
    if not isinstance(text, str) or not text.strip():
        return False, "empty output"
    if task_type == "orin_classify":
        return _v_classify(payload["categories"])(text)
    fn = VALIDATORS.get(task_type)
    if fn is None:
        return False, f"unknown task_type {task_type!r}"
    return fn(text)


def canonicalize_output(task_type: str, text: str) -> str:
    """Normalize a valid output to its cleanest training form.

    JSON tasks are re-serialized bare (no fences, no prose) so the model
    learns the strict format; text tasks are stripped.
    """
    json_tasks = {
        "orin_summarize", "orin_classify", "intake_route", "jeles_corroborate",
        "orin_extract", "orin_tension", "stop_summary",
    }
    if task_type in json_tasks:
        parsed = _parse_json(text)
        return json.dumps(parsed, ensure_ascii=False)
    return text.strip()
