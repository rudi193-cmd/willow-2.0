"""LoCoMo memory layer for Willow Path A — rich ingest + hybrid retrieval.

Phase 1b: dialog turns + entity subqueries + token-overlap rerank on top-30 pool.
"""
from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional, Set

from locomo_dataset import LocomoConversation, LocomoObservation, LocomoTurn

TEMPORAL_CUES = frozenset(
    {
        "when",
        "date",
        "year",
        "month",
        "day",
        "time",
        "ago",
        "before",
        "after",
        "week",
        "weeks",
        "last",
        "next",
        "recently",
        "since",
        "until",
    }
)

_QUERY_STOP = frozenset(
    {
        "when",
        "what",
        "where",
        "who",
        "how",
        "which",
        "did",
        "does",
        "do",
        "was",
        "were",
        "is",
        "are",
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "with",
        "from",
        "that",
        "this",
        "have",
        "has",
        "had",
        "would",
        "could",
        "about",
        "their",
        "they",
        "them",
        "she",
        "her",
        "his",
        "him",
        "he",
    }
)

_DIA_RE = re.compile(r"\bD\d+:\d+\b", re.I)
_RERANK_POOL = 30


def project_id(sample_id: str) -> str:
    return f"willow/bench/locomo/{sample_id}"


def _dia_ref_parts(dia_ref) -> List[str]:
    """Split observation dia_ref (str, list, or comma-separated) into dialog ids."""
    if isinstance(dia_ref, list):
        return [str(d) for d in dia_ref if d]
    if not dia_ref:
        return []
    return [p.strip() for p in str(dia_ref).split(",") if p.strip()]


def stable_obs_id(sample_id: str, dia_ref: str, session_id: str) -> str:
    raw = f"{project_id(sample_id)}:{dia_ref or session_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8].upper()


def stable_turn_id(sample_id: str, dia_id: str) -> str:
    raw = f"{project_id(sample_id)}:turn:{dia_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8].upper()


def stable_summary_id(sample_id: str, session_id: str) -> str:
    raw = f"{project_id(sample_id)}:summary:{session_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8].upper()


def _session_dates(conv: LocomoConversation) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for turn in conv.turns:
        if turn.session_id and turn.session_date and turn.session_id not in out:
            out[turn.session_id] = turn.session_date.strip()
    return out


def format_observation_line(
    obs: LocomoObservation,
    session_date: str,
) -> str:
    meta: List[str] = []
    if session_date:
        meta.append(session_date)
    if obs.session_id:
        meta.append(obs.session_id.replace("_", " "))
    if obs.speaker:
        meta.append(obs.speaker)
    parts = _dia_ref_parts(obs.dia_ref)
    if parts:
        meta.append(",".join(parts))
    prefix = " · ".join(meta)
    return f"[{prefix}] {obs.text}" if prefix else obs.text


def format_turn_line(turn: LocomoTurn, session_date: str) -> str:
    meta: List[str] = []
    if session_date:
        meta.append(session_date)
    if turn.session_id:
        meta.append(turn.session_id.replace("_", " "))
    if turn.speaker:
        meta.append(turn.speaker)
    if turn.dia_id:
        meta.append(turn.dia_id)
    prefix = " · ".join(meta)
    return f"[{prefix}] {turn.text}" if prefix else turn.text


def observation_keywords(
    conv: LocomoConversation,
    obs: LocomoObservation,
    session_date: str,
) -> List[str]:
    kws = ["locomo", conv.sample_id, obs.session_id, obs.speaker]
    for dia in _dia_ref_parts(obs.dia_ref):
        kws.append(f"dia:{dia}")
    if session_date:
        kws.append(f"session_date:{session_date}")
        for token in re.findall(
            r"\b(?:\d{1,2}\s+\w+\s+\d{4}|\d{4}|June|July|May|January|February|March|April|August|September|October|November|December)\b",
            session_date,
            re.I,
        ):
            kws.append(token.lower())
    return kws


def turn_keywords(
    conv: LocomoConversation,
    turn: LocomoTurn,
    session_date: str,
) -> List[str]:
    kws = ["locomo", conv.sample_id, turn.session_id, turn.speaker, "dialog_turn"]
    if turn.dia_id:
        kws.append(f"dia:{turn.dia_id}")
    if session_date:
        kws.append(f"session_date:{session_date}")
    return kws


def build_ingest_records(
    conv: LocomoConversation,
    *,
    profile: str = "v2",
) -> List[dict]:
    """Observations + session summaries + raw dialog turns (v2)."""
    dates = _session_dates(conv)
    records: List[dict] = []

    for obs in conv.observations:
        sd = dates.get(obs.session_id, "")
        summary = format_observation_line(obs, sd) if profile == "v2" else obs.text
        records.append(
            {
                "id": stable_obs_id(conv.sample_id, obs.dia_ref, obs.session_id),
                "project": project_id(conv.sample_id),
                "title": f"{conv.sample_id}:{obs.dia_ref or obs.session_id}",
                "summary": summary,
                "source_type": "benchmark",
                "category": "locomo_observation",
                "content": {
                    "keywords": observation_keywords(conv, obs, sd),
                    "speaker": obs.speaker,
                    "session_id": obs.session_id,
                    "session_date": sd,
                    "dia_ref": obs.dia_ref,
                    "memory_profile": profile,
                },
                "tier": "frontier",
                "confidence": 1.0,
            }
        )

    if profile == "v2":
        for turn in conv.turns:
            sd = dates.get(turn.session_id, "")
            records.append(
                {
                    "id": stable_turn_id(conv.sample_id, turn.dia_id),
                    "project": project_id(conv.sample_id),
                    "title": f"{conv.sample_id}:{turn.dia_id}",
                    "summary": format_turn_line(turn, sd),
                    "source_type": "benchmark",
                    "category": "locomo_turn",
                    "content": {
                        "keywords": turn_keywords(conv, turn, sd),
                        "speaker": turn.speaker,
                        "session_id": turn.session_id,
                        "session_date": sd,
                        "dia_ref": turn.dia_id,
                        "memory_profile": profile,
                    },
                    "tier": "frontier",
                    "confidence": 1.0,
                }
            )

        for sid, text in conv.summaries.items():
            sd = dates.get(sid, "")
            line = (
                f"[session summary · {sd} · {sid}] {text}"
                if sd
                else f"[session summary · {sid}] {text}"
            )
            records.append(
                {
                    "id": stable_summary_id(conv.sample_id, sid),
                    "project": project_id(conv.sample_id),
                    "title": f"{conv.sample_id}:summary:{sid}",
                    "summary": line,
                    "source_type": "benchmark",
                    "category": "locomo_session_summary",
                    "content": {
                        "keywords": [
                            "locomo",
                            conv.sample_id,
                            sid,
                            "session_summary",
                            *([f"session_date:{sd}"] if sd else []),
                        ],
                        "session_id": sid,
                        "session_date": sd,
                        "memory_profile": profile,
                    },
                    "tier": "frontier",
                    "confidence": 1.0,
                }
            )
    return records


_COUNTERFACTUAL_CUES = frozenset(
    {
        "would",
        "hadn't",
        "hadnt",
    }
)


def _is_temporal_query(question: str) -> bool:
    words = {w.lower().strip("?.,!") for w in question.split()}
    return bool(words & TEMPORAL_CUES)


def _is_counterfactual_query(question: str) -> bool:
    words = {w.lower().strip("?.,!'") for w in question.split()}
    return bool(words & _COUNTERFACTUAL_CUES)


def _extract_dia_refs(question: str) -> List[str]:
    return [m.group(0).upper().replace("d", "D") for m in _DIA_RE.finditer(question)]


def extract_query_terms(question: str) -> List[str]:
    """Entity / anchor terms for subquery retrieval (names + salient nouns)."""
    names = re.findall(r"\b[A-Z][a-z]{2,}\b", question)
    words: List[str] = []
    for raw in question.split():
        w = raw.strip("?.,!'\"")
        low = w.lower()
        if len(w) < 4 or low in _QUERY_STOP:
            continue
        if low not in {n.lower() for n in names}:
            words.append(w)
    terms = list(dict.fromkeys(names + words))
    return terms[:6]


def _dedupe_atoms(atoms: List[dict]) -> List[dict]:
    seen: Set[str] = set()
    out: List[dict] = []
    for atom in atoms:
        aid = atom.get("id") or ""
        if aid in seen:
            continue
        seen.add(aid)
        out.append(atom)
    return out


def _token_overlap_score(question: str, text: str) -> float:
    q_tokens = {
        w.lower()
        for w in re.findall(r"\w+", question)
        if w.lower() not in _QUERY_STOP and len(w) > 2
    }
    if not q_tokens:
        q_tokens = {w.lower() for w in re.findall(r"\w+", question)}
    t_tokens = {w.lower() for w in re.findall(r"\w+", text)}
    if not q_tokens:
        return 0.0
    return len(q_tokens & t_tokens) / len(q_tokens)


def _rerank_atoms(question: str, atoms: List[dict], max_k: int) -> List[dict]:
    scored: List[tuple[float, dict]] = []
    for atom in atoms:
        text = f"{atom.get('title') or ''} {atom.get('summary') or ''}"
        score = _token_overlap_score(question, text)
        content = atom.get("content") or {}
        if isinstance(content, dict) and content.get("dia_ref"):
            score += 0.05
        scored.append((score, atom))
    scored.sort(key=lambda x: (-x[0], x[1].get("id") or ""))
    return [a for _, a in scored[:max_k]]


def search_kb(
    pg,
    question: str,
    sample_id: str,
    max_k: int,
    semantic: bool,
    conv: Optional[LocomoConversation] = None,
    *,
    profile: str = "v2",
) -> List[dict]:
    """Hybrid retrieval + entity subqueries + overlap rerank."""
    proj = project_id(sample_id)
    fetch_k = _RERANK_POOL if profile == "v2" else max(max_k * 3, 15)

    if semantic:
        try:
            pool = pg.knowledge_search_semantic(question, limit=fetch_k, project=proj)
        except Exception:
            pool = pg.knowledge_search(question, project=proj, limit=fetch_k)
    else:
        pool = pg.knowledge_search(question, project=proj, limit=fetch_k)

    if profile != "v2" or conv is None:
        return pool[:max_k]

    extra: List[dict] = []

    for term in extract_query_terms(question):
        extra.extend(pg.knowledge_search(term, project=proj, limit=5))

    if _is_temporal_query(question):
        for sd in _session_dates(conv).values():
            if sd:
                extra.extend(pg.knowledge_search(sd, project=proj, limit=5))
        extra.extend(
            pg.knowledge_search(
                "session summary " + question,
                project=proj,
                limit=8,
            )
        )

    if _is_counterfactual_query(question):
        extra.extend(
            pg.knowledge_search("session summary", project=proj, limit=8)
        )

    for dia in _extract_dia_refs(question):
        extra.extend(pg.knowledge_search(dia, project=proj, limit=5))

    merged = _dedupe_atoms(pool + extra)
    return _rerank_atoms(question, merged, max_k)


def context_lines(atoms: List[dict]) -> List[str]:
    lines: List[str] = []
    for atom in atoms:
        summary = (atom.get("summary") or "").strip()
        if summary:
            lines.append(summary)
    return lines
