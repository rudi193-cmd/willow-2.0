#!/usr/bin/env python3
"""
core/skill_mastery.py — live Bayesian-Knowledge-Tracing mastery, per skill.
b17: SKMS1  ΔΣ=42

Extension #1 of the BKT piece (core/bkt.py). Turns a stream of per-skill
correct/incorrect outcomes into a persisted mastery estimate — one record per
skill in the SOIL `bkt` collection (core/soil.py: sqlite, no Postgres,
Termux-safe).

Flow:
    core/outcomes.py terminal result  →  record_outcome(skill_id, outcome)
    explicit pass/fail                →  record(skill_id, correct)
        · bkt.update() advances p_known online after every opportunity
        · every `refit_every` opportunities, bkt.fit() re-estimates the four
          parameters from the skill's own history, then the forward filter is
          replayed (bkt.trace) so p_known stays consistent with the new params
    read                              →  mastery(skill_id) / all_mastery() / weakest(n)

The MCP read surface (#2) in sap/sap_mcp.py is a thin wrapper over mastery()
and weakest(); it is inert until `skill_mastery` is added to PERMISSION_GROUPS
in sap/core/gate.py (the gate is fail-closed — see scratch gate verification).
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from core import bkt, soil

# outcomes._SUCCESS is the single source of truth for "this run counts as correct".
try:
    from core.outcomes import _SUCCESS as _OUTCOME_SUCCESS
except Exception:  # pragma: no cover - outcomes optional / import-light fallback
    _OUTCOME_SUCCESS = {"satisfied"}

_COLLECTION = "bkt"
_DEFAULT_REFIT_EVERY = 25
_DEFAULT_HISTORY_CAP = 500
_MIN_REFIT_HISTORY = 2

_PARAM_FIELDS = ("prior", "learn", "guess", "slip", "forget")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_params(d: dict) -> bkt.BKTParams:
    """Build BKTParams from a stored params dict (tolerant of missing keys)."""
    return bkt.BKTParams(**{k: d[k] for k in _PARAM_FIELDS if k in d})


def _params_dict(p: bkt.BKTParams) -> dict:
    return asdict(p)


def record(
    skill_id: str,
    correct: bool,
    *,
    refit_every: int = _DEFAULT_REFIT_EVERY,
    history_cap: int = _DEFAULT_HISTORY_CAP,
) -> dict:
    """Record one outcome for a skill and return its updated mastery record.

    Loads the skill's BKT state from SOIL (seeding neutral defaults on first
    sight), advances p_known with bkt.update(), appends to a capped history, and
    periodically refits the parameters from that history. Persists and returns
    the full record.
    """
    correct = bool(correct)
    rec = soil.get(_COLLECTION, skill_id)
    if rec is None:
        params = bkt.BKTParams()
        p_known = params.prior
        history: list[int] = []
        opportunities = 0
        refit_at = None
    else:
        params = _to_params(rec.get("params", {}))
        p_known = float(rec.get("p_known", params.prior))
        history = [int(x) for x in rec.get("history", [])]
        opportunities = int(rec.get("opportunities", 0))
        refit_at = rec.get("refit_at")

    # Online update, then append to the (capped) history.
    p_known = bkt.update(p_known, correct, params)
    history.append(1 if correct else 0)
    if len(history) > history_cap:
        history = history[-history_cap:]
    opportunities += 1

    # Periodic refit from the skill's own observed sequence, replaying the
    # forward filter so the online p_known stays consistent with new params.
    if refit_every and opportunities % refit_every == 0 and len(history) >= _MIN_REFIT_HISTORY:
        params = bkt.fit([history], init=params)
        p_known = bkt.trace(history, params)[-1]
        refit_at = _now()

    out = {
        "skill_id": skill_id,
        "params": _params_dict(params),
        "p_known": p_known,
        "p_next_correct": bkt.predict_correct(p_known, params),
        "mastered": bkt.mastered(p_known),
        "opportunities": opportunities,
        "history": history,
        "last_outcome_at": _now(),
        "refit_at": refit_at,
    }
    soil.put(_COLLECTION, skill_id, out)
    return out


def record_outcome(skill_id: str, outcome: dict, **kw) -> dict:
    """Record a core/outcomes.py result dict against a skill.

    Prefers an explicit ``outcome["success"]`` bool; otherwise treats the run as
    correct when ``outcome["result"]`` is a success state (outcomes._SUCCESS).
    """
    if "success" in outcome:
        correct = bool(outcome["success"])
    else:
        correct = outcome.get("result") in _OUTCOME_SUCCESS
    return record(skill_id, correct, **kw)


def mastery(skill_id: str) -> dict | None:
    """Return the persisted mastery record for a skill, or None if never seen."""
    return soil.get(_COLLECTION, skill_id)


def all_mastery() -> list[dict]:
    """Return every persisted mastery record."""
    return soil.all_records(_COLLECTION)


def weakest(n: int = 5, *, threshold: float | None = None) -> list[dict]:
    """Return the N lowest-mastery skills (ascending), the drill list for #3.

    threshold: if given, only skills with p_known below it are returned.
    """
    records = all_mastery()
    if threshold is not None:
        records = [r for r in records if r.get("p_known", 1.0) < threshold]
    records.sort(key=lambda r: r.get("p_known", 1.0))
    return [{"skill_id": r.get("skill_id"), "mastery": r.get("p_known")}
            for r in records[:n]]


# ── mastery-aware behaviour (#3) ──────────────────────────────────────────────

_RISKY = ("medium", "high")
_MASTERY_THRESHOLD = 0.95  # Corbett & Anderson's mastery bar


def needs_scrutiny(skill_id: str, risk: str, *, threshold: float = _MASTERY_THRESHOLD) -> bool:
    """True when a risky skill is not yet mastered → caller should add a confirm
    step / extra review before running it.

    risk: the catalog risk level ('low' | 'medium' | 'high'); passed in so this
    module stays decoupled from the skill catalog. Mastery is read from SOIL; an
    unseen risky skill (no record) is treated as unmastered → scrutiny.
    """
    if risk not in _RISKY:
        return False
    rec = mastery(skill_id)
    p_known = float(rec.get("p_known", 0.0)) if rec else 0.0
    return p_known < threshold


def drills(n: int = 5, *, threshold: float = _MASTERY_THRESHOLD) -> list[dict]:
    """The practice list: lowest-mastery skills still below the mastery bar.

    BKT mirror of ACT-R decay surfacing stale atoms — thin alias over weakest()
    with a mastery ceiling.
    """
    return weakest(n, threshold=threshold)
