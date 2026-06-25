"""WCE handoff-pair tasks — thread recall, next-bite, surfacing, staleness, decisions.

Measures session N → N+1 continuity from v2 handoff markdown (no LLM judge).
See docs/adrs/ADR-20260624-locomo-overfit-vs-continuity-eval.md appendix.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from sap.handoff_index import extract_next_bite, latest_handoff_sort_key
from willow.fylgja.willow_home import willow_home

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]{3,}")
_ISSUE_RE = re.compile(r"#\d+")
_PR_RE = re.compile(r"\bpr\s*#?\d+\b", re.I)
_ATOM_ID_RE = re.compile(r"\b([A-F0-9]{8})\b")
_STALE_MARKERS_RE = re.compile(
    r"\b(stale|superseded|outdated|obsolete|no longer|was wrong|incorrect|"
    r"unverified|supersede|deprecated|invalidated)\b",
    re.I,
)
_STOP = frozenset({
    "that", "this", "with", "from", "have", "will", "been", "were", "they",
    "what", "when", "then", "than", "into", "only", "also", "still", "next",
    "session", "should", "would", "could", "after", "before", "until", "about",
    "open", "threads", "thread", "handoff", "willow", "merge", "merged",
})


def default_handoffs_root() -> Path:
    return willow_home() / "handoffs"


def _parse_json_list(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(x) for x in val if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return []


def _extract_bullets(content: str, markers: tuple[str, ...]) -> list[str]:
    for marker in markers:
        if marker not in content:
            continue
        start = content.find(marker) + len(marker)
        block = re.split(r"\n(?=## |\n---)", content[start:])[0]
        items = re.findall(r"^[-*]\s+(.+)$", block, re.MULTILINE)
        return [i.strip() for i in items if i.strip()]
    return []


def _extract_paragraph(content: str, marker: str) -> str:
    if marker not in content:
        return ""
    start = content.find(marker) + len(marker)
    block = re.split(r"\n(?=## |\n---)", content[start:])[0].strip()
    return block.split("\n\n")[0].strip() if block else ""


def signatures(text: str) -> set[str]:
    """Keyword + issue/PR signatures for fuzzy thread matching."""
    low = (text or "").lower()
    sig = {t for t in _TOKEN_RE.findall(low) if t not in _STOP}
    sig.update(m.lower() for m in _ISSUE_RE.findall(text or ""))
    sig.update(m.lower().replace(" ", "") for m in _PR_RE.findall(text or ""))
    return sig


def texts_overlap(a: str, b: str, *, min_overlap: float = 0.2) -> bool:
    sa, sb = signatures(a), signatures(b)
    if not sa or not sb:
        return False
    shared = sa & sb
    return len(shared) >= max(1, int(len(sa) * min_overlap))


def load_handoffs(agent: str, handoffs_root: Optional[Path] = None) -> list[dict[str, Any]]:
    """Load and parse v2 session handoffs for one agent."""
    from sap.tools.build_handoff_db import (
        has_handoff_body_marker,
        has_valid_frontmatter,
        matches_agent_suffix,
        parse_session_handoff,
    )

    root = handoffs_root or default_handoffs_root()
    agent_dir = root / agent
    if not agent_dir.is_dir():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(agent_dir.glob("session_handoff-*.md")):
        if not matches_agent_suffix(path.name, agent):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not has_valid_frontmatter(content) and not has_handoff_body_marker(content):
            continue
        parsed = parse_session_handoff(content, path.name)
        questions = _parse_json_list(parsed.get("questions"))
        summary = str(parsed.get("summary") or "")
        open_threads = _parse_json_list(parsed.get("open_threads"))
        agreements = _parse_json_list(parsed.get("agreements"))
        atom_ids = _ATOM_ID_RE.findall(content.upper())
        deduped_atoms: list[str] = []
        for aid in atom_ids:
            if aid not in deduped_atoms:
                deduped_atoms.append(aid)
        rows.append({
            "filename": path.name,
            "date": parsed.get("handoff_date") or "",
            "summary": summary,
            "open_threads": open_threads,
            "agreements": agreements,
            "questions": questions,
            "what_was_done": _extract_bullets(content, ("## What Was Done", "**What Was Done**")),
            "understand": _extract_paragraph(content, "## What I Now Understand"),
            "next_bite": extract_next_bite(questions, summary),
            "surfaced_atom_ids": deduped_atoms[:10],
            "mtime": path.stat().st_mtime,
        })
    return rows


def consecutive_pairs(handoffs: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if len(handoffs) < 2:
        return []
    ordered = sorted(
        handoffs,
        key=lambda h: latest_handoff_sort_key(
            str(h.get("filename") or ""),
            str(h.get("date") or ""),
            str(h.get("mtime") or ""),
        ),
    )
    return [(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)]


def n_plus_one_corpus(n1: dict[str, Any]) -> str:
    parts = [
        str(n1.get("understand") or ""),
        str(n1.get("summary") or ""),
        "\n".join(n1.get("what_was_done") or []),
        "\n".join(n1.get("open_threads") or []),
    ]
    return "\n".join(p for p in parts if p)


def evaluate_thread_recall(n: dict[str, Any], n1: dict[str, Any]) -> dict[str, Any]:
    threads = [t for t in (n.get("open_threads") or []) if str(t).strip()]
    corpus = n_plus_one_corpus(n1)
    if not threads:
        return {"hit": None, "recall": None, "matched": [], "missed": [], "n_threads": 0}
    matched = [t for t in threads if texts_overlap(t, corpus)]
    missed = [t for t in threads if t not in matched]
    recall = len(matched) / len(threads)
    return {
        "hit": recall >= 0.5,
        "recall": round(recall, 4),
        "matched": matched,
        "missed": missed,
        "n_threads": len(threads),
    }


def evaluate_next_bite(n: dict[str, Any], n1: dict[str, Any]) -> dict[str, Any]:
    bite = str(n.get("next_bite") or "").strip()
    if not bite:
        return {"hit": None, "next_bite": "", "n1_corpus": ""}
    corpus_parts = [
        "\n".join(n1.get("what_was_done") or []),
        str(n1.get("understand") or ""),
        str(n1.get("summary") or ""),
    ]
    corpus = "\n".join(p for p in corpus_parts if p)
    hit = texts_overlap(bite, corpus) or bite.lower()[:48] in corpus.lower()
    return {
        "hit": hit,
        "next_bite": bite[:300],
        "n1_corpus_preview": corpus[:300],
    }


def boot_surfaced_items(
    n: dict[str, Any],
    *,
    max_threads: int = 5,
    max_atoms: int = 3,
    ledger_atom_ids: Optional[list[str]] = None,
) -> list[dict[str, str]]:
    """Bounded boot surfacing proxy: ≤5 threads + top-3 atoms."""
    items: list[dict[str, str]] = []
    for thread in (n.get("open_threads") or [])[:max_threads]:
        text = str(thread).strip()
        if text:
            items.append({"kind": "thread", "text": text})
    atom_ids = list(ledger_atom_ids or [])[:max_atoms]
    if len(atom_ids) < max_atoms:
        for aid in (n.get("surfaced_atom_ids") or []):
            if aid not in atom_ids:
                atom_ids.append(aid)
            if len(atom_ids) >= max_atoms:
                break
    for aid in atom_ids[:max_atoms]:
        items.append({"kind": "atom", "text": aid})
    return items


def _item_used(item: dict[str, str], n1: dict[str, Any]) -> bool:
    corpus = n_plus_one_corpus(n1)
    text = item.get("text") or ""
    if item.get("kind") == "atom":
        if text and text.upper() in corpus.upper():
            return True
    return texts_overlap(text, corpus)


def evaluate_surfacing_precision(
    n: dict[str, Any],
    n1: dict[str, Any],
    *,
    max_threads: int = 5,
    max_atoms: int = 3,
    ledger_atom_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    surfaced = boot_surfaced_items(
        n, max_threads=max_threads, max_atoms=max_atoms, ledger_atom_ids=ledger_atom_ids,
    )
    if not surfaced:
        return {
            "precision": None,
            "n_surfaced": 0,
            "n_used": 0,
            "surfaced": [],
            "used": [],
            "unused": [],
        }
    used = [item for item in surfaced if _item_used(item, n1)]
    unused = [item for item in surfaced if item not in used]
    precision = len(used) / len(surfaced)
    return {
        "precision": round(precision, 4),
        "n_surfaced": len(surfaced),
        "n_used": len(used),
        "surfaced": surfaced,
        "used": used,
        "unused": unused,
    }


def _n1_work_questions(n1: dict[str, Any]) -> list[str]:
    """Questions from N+1 excluding Q17 (next-bite prompt)."""
    qs = [str(q).strip() for q in (n1.get("questions") or []) if str(q).strip()]
    if len(qs) <= 1:
        return qs
    last = qs[-1].lower()
    if "next" in last and "bite" in last:
        return qs[:-1]
    return qs


def evaluate_decision_persistence(n: dict[str, Any], n1: dict[str, Any]) -> dict[str, Any]:
    agreements = [str(a).strip() for a in (n.get("agreements") or []) if str(a).strip()]
    if not agreements:
        return {
            "relitigation_rate": None,
            "n_agreements": 0,
            "relitigated": [],
            "persisted": [],
        }
    done_corpus = "\n".join(n1.get("what_was_done") or [])
    questions = _n1_work_questions(n1)
    question_corpus = "\n".join(questions)
    relitigated: list[str] = []
    persisted: list[str] = []
    for agreement in agreements:
        executed = texts_overlap(agreement, done_corpus)
        reasked = bool(questions) and texts_overlap(agreement, question_corpus)
        if reasked and not executed:
            relitigated.append(agreement)
        else:
            persisted.append(agreement)
    rate = len(relitigated) / len(agreements)
    return {
        "relitigation_rate": round(rate, 4),
        "n_agreements": len(agreements),
        "relitigated": relitigated,
        "persisted": persisted,
    }


def _atom_topic_text(atom: dict[str, Any]) -> str:
    return f"{atom.get('title') or ''} {atom.get('summary') or ''}".strip()


def _atom_mentioned(atom: dict[str, Any], corpus: str) -> bool:
    aid = str(atom.get("id") or "").upper()
    if aid and aid in corpus.upper():
        return True
    topic = _atom_topic_text(atom)
    return bool(topic) and texts_overlap(topic, corpus)


def evaluate_staleness_surfacing(
    n1: dict[str, Any],
    superseded_atoms: list[dict[str, Any]],
) -> dict[str, Any]:
    if not superseded_atoms:
        return {
            "stale_flag_rate": None,
            "acted_on_stale_rate": None,
            "n_superseded": 0,
            "n_mentioned": 0,
            "flagged": [],
            "acted_on": [],
            "silent": [],
        }
    corpus = n_plus_one_corpus(n1)
    flagged: list[str] = []
    acted_on: list[str] = []
    silent: list[str] = []
    for atom in superseded_atoms:
        topic = _atom_topic_text(atom)
        if not _atom_mentioned(atom, corpus):
            silent.append(str(atom.get("id") or topic[:40]))
            continue
        aid = str(atom.get("id") or "")
        if _STALE_MARKERS_RE.search(corpus):
            flagged.append(aid or topic[:40])
        else:
            acted_on.append(aid or topic[:40])
    mentioned = len(flagged) + len(acted_on)
    stale_flag_rate = (len(flagged) / mentioned) if mentioned else None
    acted_on_stale_rate = (len(acted_on) / mentioned) if mentioned else None
    return {
        "stale_flag_rate": round(stale_flag_rate, 4) if stale_flag_rate is not None else None,
        "acted_on_stale_rate": round(acted_on_stale_rate, 4) if acted_on_stale_rate is not None else None,
        "n_superseded": len(superseded_atoms),
        "n_mentioned": mentioned,
        "flagged": flagged,
        "acted_on": acted_on,
        "silent": silent,
    }


def run_handoff_tasks(
    agent: str,
    *,
    tasks: list[str],
    handoffs_root: Optional[Path] = None,
    pair_limit: int = 0,
    pg: Any = None,
    max_threads: int = 5,
    max_atoms: int = 3,
) -> dict[str, Any]:
    handoffs = load_handoffs(agent, handoffs_root)
    pairs = consecutive_pairs(handoffs)
    if pair_limit > 0:
        pairs = pairs[-pair_limit:]

    results_list: list[dict[str, Any]] = []
    thread_results: list[dict[str, Any]] = []
    bite_results: list[dict[str, Any]] = []
    precision_results: list[dict[str, Any]] = []
    decision_results: list[dict[str, Any]] = []
    staleness_results: list[dict[str, Any]] = []

    kb_helpers = None
    if pg is not None and any(t in tasks for t in ("surfacing_precision", "staleness")):
        from willow.bench.continuity import kb_eval as _kb_eval

        kb_helpers = _kb_eval

    for n, n1 in pairs:
        pair_id = f"{n.get('filename')} -> {n1.get('filename')}"
        row: dict[str, Any] = {"pair": pair_id}
        if "thread_recall" in tasks:
            tr = evaluate_thread_recall(n, n1)
            row["thread_recall"] = tr
            thread_results.append(tr)
        if "next_bite" in tasks:
            nb = evaluate_next_bite(n, n1)
            row["next_bite"] = nb
            bite_results.append(nb)
        if "surfacing_precision" in tasks:
            ledger_ids: list[str] = []
            if kb_helpers and pg is not None:
                t_n, _ = kb_helpers.pair_time_bounds(n, n1)
                ledger_ids = kb_helpers.ledger_atoms_written(pg, project=agent, before=t_n, limit=max_atoms)
            sp = evaluate_surfacing_precision(
                n, n1, max_threads=max_threads, max_atoms=max_atoms, ledger_atom_ids=ledger_ids,
            )
            row["surfacing_precision"] = sp
            precision_results.append(sp)
        if "decision_persistence" in tasks:
            dp = evaluate_decision_persistence(n, n1)
            row["decision_persistence"] = dp
            decision_results.append(dp)
        if "staleness" in tasks:
            superseded: list[dict[str, Any]] = []
            if kb_helpers and pg is not None:
                t_n, t_n1 = kb_helpers.pair_time_bounds(n, n1)
                superseded = kb_helpers.superseded_between(pg, valid_at=t_n, invalid_before=t_n1)
            st = evaluate_staleness_surfacing(n1, superseded)
            row["staleness"] = st
            staleness_results.append(st)
        results_list.append(row)

    def _mean(vals: list[Optional[float]]) -> Optional[float]:
        nums = [v for v in vals if isinstance(v, (int, float))]
        return round(sum(nums) / len(nums), 4) if nums else None

    summary: dict[str, Any] = {
        "agent": agent,
        "handoffs_loaded": len(handoffs),
        "pairs_evaluated": len(pairs),
    }
    if "thread_recall" in tasks:
        recalls = [r["recall"] for r in thread_results if r.get("recall") is not None]
        summary["thread_recall_mean"] = _mean(recalls)
        summary["thread_recall_pairs_scored"] = len(recalls)
    if "next_bite" in tasks:
        hits = [1.0 if r.get("hit") else 0.0 for r in bite_results if r.get("hit") is not None]
        summary["next_bite_hit_rate"] = _mean(hits)
        summary["next_bite_pairs_scored"] = len(hits)
    if "surfacing_precision" in tasks:
        precs = [r["precision"] for r in precision_results if r.get("precision") is not None]
        summary["surfacing_precision_mean"] = _mean(precs)
        summary["surfacing_precision_pairs_scored"] = len(precs)
    if "decision_persistence" in tasks:
        rates = [r["relitigation_rate"] for r in decision_results if r.get("relitigation_rate") is not None]
        summary["relitigation_rate_mean"] = _mean(rates)
        summary["decision_persistence_pairs_scored"] = len(rates)
    if "staleness" in tasks:
        flag_rates = [r["stale_flag_rate"] for r in staleness_results if r.get("stale_flag_rate") is not None]
        summary["stale_flag_rate_mean"] = _mean(flag_rates)
        acted = [r["acted_on_stale_rate"] for r in staleness_results if r.get("acted_on_stale_rate") is not None]
        summary["acted_on_stale_rate_mean"] = _mean(acted)
        summary["staleness_pairs_scored"] = len(flag_rates)

    return {"summary": summary, "pairs": results_list}
