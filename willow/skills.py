# willow/skills.py — Willow Skills registry. b17: SKLS1  ΔΣ=42
from __future__ import annotations
from core.store_port import StorePort

_COLLECTION = "willow/skills"


def skill_put(
    store: StorePort,
    name: str,
    domain: str,
    content: str,
    trigger: str,
    auto_load: bool = True,
    model_agnostic: bool = True,
    risk: str = "low",
) -> str:
    """Store or update a skill. Returns skill ID (= name)."""
    store.put(_COLLECTION, {
        "id": name,
        "name": name,
        "domain": domain,
        "content": content,
        "trigger": trigger,
        "auto_load": auto_load,
        "model_agnostic": model_agnostic,
        "risk": risk,
    })
    return name


def skill_load(
    store: StorePort,
    context: str,
    max_skills: int = 3,
    *,
    mastery_bias: float = 0.0,
) -> list[dict]:
    """Return up to max_skills auto-loadable skills relevant to context.

    mastery_bias: optional BKT re-rank weight (#3). When non-zero, the sort key
    becomes ``trigger_overlap + mastery_bias * p_known`` — a positive bias
    favours skills the agent has demonstrably mastered (core/skill_mastery),
    breaking ties toward reliability. Default 0.0 keeps the historical
    overlap-only ordering byte-for-byte; the mastery lookup is skipped entirely.
    """
    all_skills = store.list(_COLLECTION)
    context_words = set(context.lower().split())

    scored = []
    for record in all_skills:
        data = record.get("data", record)
        if not data.get("auto_load", False):
            continue
        trigger_words = set(data.get("trigger", "").lower().split())
        score = len(context_words & trigger_words)
        if score > 0:
            scored.append((score, data))

    if mastery_bias:
        from core import skill_mastery as _sm

        def _key(item):
            score, data = item
            sid = data.get("id") or data.get("name")
            rec = _sm.mastery(sid) if sid else None
            p_known = float(rec.get("p_known", 0.0)) if rec else 0.0
            return score + mastery_bias * p_known

        scored.sort(key=_key, reverse=True)
    else:
        scored.sort(key=lambda x: x[0], reverse=True)

    from core import skill_mastery as _sm
    result = []
    for _, data in scored[:max_skills]:
        sid = data.get("id") or data.get("name")
        risk = data.get("risk", "low")
        scrutiny = _sm.needs_scrutiny(sid, risk) if sid else False
        result.append({**data, "needs_scrutiny": scrutiny})
    return result


def skill_list(
    store: StorePort,
    domain: str | None = None,
) -> list[dict]:
    """List all skills, optionally filtered by domain."""
    all_skills = store.list(_COLLECTION)
    result = []
    for record in all_skills:
        data = record.get("data", record)
        if domain and data.get("domain") != domain:
            continue
        result.append(data)
    return result
