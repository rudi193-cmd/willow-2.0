"""WCE handoff-pair tasks — thread recall and next-bite fidelity.

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
        rows.append({
            "filename": path.name,
            "date": parsed.get("handoff_date") or "",
            "summary": summary,
            "open_threads": open_threads,
            "questions": questions,
            "what_was_done": _extract_bullets(content, ("## What Was Done", "**What Was Done**")),
            "understand": _extract_paragraph(content, "## What I Now Understand"),
            "next_bite": extract_next_bite(questions, summary),
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


def run_handoff_tasks(
    agent: str,
    *,
    tasks: list[str],
    handoffs_root: Optional[Path] = None,
    pair_limit: int = 0,
) -> dict[str, Any]:
    handoffs = load_handoffs(agent, handoffs_root)
    pairs = consecutive_pairs(handoffs)
    if pair_limit > 0:
        pairs = pairs[-pair_limit:]

    results_list: list[dict[str, Any]] = []
    thread_results: list[dict[str, Any]] = []
    bite_results: list[dict[str, Any]] = []

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

    return {"summary": summary, "pairs": results_list}
