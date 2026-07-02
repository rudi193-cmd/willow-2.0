"""routing/shadow.py — complexity-ladder shadow instrumentation.

ADR-20260702-router-sensitivity-veto step 3. NO behavior change: this module
observes inference calls and records which rung of the (not-yet-built)
escalation ladder would have handled each task, plus which engine the two-axis
router would pick once the sensitivity veto is applied. Two weeks of these rows
inform the step-4 ladder design; nothing here routes anything.

Everything is deterministic — no ML in this path (mirrors the veto rule). The
complexity classifier is a rule-based token/structure heuristic, intentionally
crude: its job is to bucket tasks for distribution analysis, not to be the
final ladder.
b17: RTRSHDW · ΔΣ=42
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid

logger = logging.getLogger(__name__)

# Five rungs, cheapest first. Engine names are the inference_router chain labels.
RUNGS = ("r1_trivial", "r2_simple", "r3_moderate", "r4_complex", "r5_frontier")

# Complexity-only preference: which engine the ladder would reach for, ignoring
# sensitivity. Low rungs stay local; high rungs want cloud/frontier quality.
_RUNG_ENGINE = {
    "r1_trivial":  "local",
    "r2_simple":   "local",
    "r3_moderate": "local",
    "r4_complex":  "cloud",
    "r5_frontier": "cloud",
}

_CODE_FENCE = re.compile(r"```|\bdef \b|\bclass \b|=>|;\s*$", re.MULTILINE)
_STEP_MARKER = re.compile(r"\b(step \d|first,|then,|finally,|1\.|2\.|3\.)", re.IGNORECASE)
_REASON_WORD = re.compile(
    r"\b(why|prove|derive|analy[sz]e|trade-?off|compare|design|architect|"
    r"refactor|debug|optimi[sz]e|reconcile|synthesi[sz]e)\b",
    re.IGNORECASE,
)


def classify_complexity(prompt: str) -> dict:
    """Bucket a prompt into one of five complexity rungs. Pure, deterministic.

    Returns {rung, score, signals}. Score is an integer 0..N; rung is derived
    from thresholds. Signals lists which heuristics fired (for later analysis).
    """
    text = prompt or ""
    n = len(text)
    signals: list[str] = []
    score = 0

    if n > 4000:
        score += 3
        signals.append("very_long")
    elif n > 1200:
        score += 2
        signals.append("long")
    elif n > 300:
        score += 1
        signals.append("medium")

    if _CODE_FENCE.search(text):
        score += 2
        signals.append("code")
    if _STEP_MARKER.search(text):
        score += 1
        signals.append("multi_step")
    reason_hits = len(_REASON_WORD.findall(text))
    if reason_hits >= 2:
        score += 2
        signals.append("reasoning_heavy")
    elif reason_hits == 1:
        score += 1
        signals.append("reasoning")
    if text.count("?") >= 3:
        score += 1
        signals.append("multi_question")

    if score <= 0:
        rung = "r1_trivial"
    elif score <= 2:
        rung = "r2_simple"
    elif score <= 4:
        rung = "r3_moderate"
    elif score <= 6:
        rung = "r4_complex"
    else:
        rung = "r5_frontier"
    return {"rung": rung, "score": score, "signals": signals}


def resolve_shadow_engine(rung: str, sensitivity: str) -> dict:
    """Apply the two-axis rule: complexity picks an engine, sensitivity vetoes.

    Sensitive tasks are pinned local regardless of rung — this is the whole
    thesis (the most sensitive work must never reach the least sovereign
    engine). Returns both the complexity-only pick and the veto-applied pick so
    shadow analysis can measure how often the veto overrides complexity.
    """
    complexity_engine = _RUNG_ENGINE.get(rung, "cloud")
    sens = (sensitivity or "unknown").strip().lower()
    # Fail closed: anything not explicitly 'open' pins local.
    vetoed = sens != "open"
    router_engine = "local" if vetoed else complexity_engine
    return {
        "complexity_engine": complexity_engine,
        "router_engine": router_engine,
        "veto_applied": vetoed and complexity_engine != "local",
    }


def shadow_decision(prompt: str, sensitivity: str = "unknown",
                    actual_engine: str = "") -> dict:
    """Full shadow record for one inference call. Pure — does not touch the DB."""
    cx = classify_complexity(prompt)
    eng = resolve_shadow_engine(cx["rung"], sensitivity)
    return {
        "rung": cx["rung"],
        "score": cx["score"],
        "signals": cx["signals"],
        "sensitivity": (sensitivity or "unknown").strip().lower(),
        "complexity_engine": eng["complexity_engine"],
        "router_engine": eng["router_engine"],
        "veto_applied": eng["veto_applied"],
        "actual_engine": actual_engine or "",
    }


def log_shadow(conn, prompt: str, *, sensitivity: str = "unknown",
               actual_engine: str = "", session_id: str = "",
               source: str = "infer_chat") -> None:
    """Fire-and-forget insert into routing_decisions (kind='complexity_shadow').

    Never raises: shadow instrumentation must not break the inference path.
    """
    try:
        rec = shadow_decision(prompt, sensitivity=sensitivity, actual_engine=actual_engine)
        import json as _j
        payload = dict(rec)
        payload["source"] = source
        ph = hashlib.sha256((prompt or "").encode()).hexdigest()[:16]
        rid = uuid.uuid4().hex[:12]
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO routing_decisions"
                " (id, kind, prompt_hash, session_id, confidence, decision,"
                "  shadow_rung, shadow_engine, sensitivity)"
                " VALUES (%s,'complexity_shadow',%s,%s,%s,%s,%s,%s,%s)",
                (rid, ph, session_id or "", None, _j.dumps(payload),
                 rec["rung"], rec["router_engine"], rec["sensitivity"]),
            )
        conn.commit()
    except Exception as e:  # noqa: BLE001 — shadow must never break inference
        logger.debug("shadow log skipped: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
