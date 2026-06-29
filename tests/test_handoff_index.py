import tempfile
from pathlib import Path

from sap.handoff_index import (
    extract_next_bite,
    handoff_is_empty_stub,
    handoff_richness_score,
    latest_handoff_sort_key,
    scan_markdown_handoffs,
    select_best_handoff,
    select_latest_handoff,
)
from sap.handoff_paths import handoffs_root


def test_latest_handoff_prefers_semantic_session_recency_over_mtime():
    rows = [
        {
            "filename": "session_handoff-2026-05-18d_heimdallr.md",
            "handoff_date": "2026-05-18",
            "mtime": "2026-05-18T20:51:52.314538",
        },
        {
            "filename": "session_handoff-2026-05-19a_heimdallr.md",
            "handoff_date": "2026-05-19",
            "mtime": "2026-05-18T20:50:57.267328",
        },
    ]

    latest = select_latest_handoff(rows)

    assert latest is not None
    assert latest["filename"] == "session_handoff-2026-05-19a_heimdallr.md"


def test_latest_handoff_prefers_lettered_same_day_session():
    plain = latest_handoff_sort_key(
        "session_handoff-2026-05-19.md",
        "2026-05-19",
        "2026-05-18T21:07:12.521964",
    )
    lettered = latest_handoff_sort_key(
        "session_handoff-2026-05-19a_heimdallr.md",
        "2026-05-19",
        "2026-05-18T20:50:57.267328",
    )

    assert lettered > plain


def test_select_latest_handoff_returns_none_for_empty_rows():
    assert select_latest_handoff([]) is None


def test_select_best_handoff_prefers_substance_over_empty_kb():
    empty_kb = {
        "filename": "kb_EMPTY.json",
        "date": "2026-05-26",
        "summary": "Session ended",
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-05-26T23:59:00",
    }
    rich_md = {
        "filename": "session_handoff-2026-05-26b_hanuman.md",
        "date": "2026-05-26",
        "summary": "Post-merge infra landed",
        "open_threads": ["Binder wiring", "Jeles migrations"],
        "questions": ["Q17: What is the next single bite? Wire crown.py"],
        "_valid_at": "2026-05-26",
    }
    best = select_best_handoff([empty_kb, rich_md])
    assert best is not None
    assert best["filename"] == "session_handoff-2026-05-26b_hanuman.md"


def test_extract_next_bite_from_q17():
    questions = [
        "Q1: migrations applied?",
        "Q17: What is the next single bite? Wire Ctrl+S in ask-jeles.",
    ]
    bite = extract_next_bite(questions)
    assert "Wire Ctrl+S" in bite


def test_handoff_richness_score_orders_by_open_threads():
    sparse = {"filename": "a.md", "open_threads": [], "questions": [], "summary": "x", "date": "2026-05-25"}
    rich = {
        "filename": "b.md",
        "open_threads": ["one", "two"],
        "questions": ["Q17: bite"],
        "summary": "longer summary text",
        "date": "2026-05-25",
    }
    assert handoff_richness_score(rich) > handoff_richness_score(sparse)


def test_empty_kb_stub_loses_to_richer_markdown_same_day():
    empty_kb = {
        "filename": "kb_C4A81DCA.json",
        "date": "2026-06-04",
        "summary": "Long upstream sweep summary with no structured continuity fields.",
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-06-04T12:00:00",
    }
    rich_md = {
        "filename": "session_handoff-2026-06-04g_hanuman.md",
        "date": "2026-06-04",
        "summary": "Audit complete",
        "open_threads": ["phase-0-kart", "identity-drift"],
        "questions": ["Q17: Open worktree fix/kart-phase0-state-machine"],
        "_valid_at": "2026-06-04",
    }
    assert handoff_is_empty_stub(empty_kb)
    assert not handoff_is_empty_stub(rich_md)
    best = select_best_handoff([empty_kb, rich_md])
    assert best is not None
    assert best["filename"] == "session_handoff-2026-06-04g_hanuman.md"


def test_select_best_handoff_prefers_newer_same_day_kb_atom():
    older = {
        "filename": "kb_BE69F92D.json",
        "date": "2026-06-10",
        "summary": "Older same-day handoff atom with lexically larger id.",
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-06-10T09:00:00-06:00",
    }
    newer = {
        "filename": "kb_3CC79359.json",
        "date": "2026-06-10",
        "summary": "Newer same-day handoff atom with lexically smaller id.",
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-06-10T16:12:00-06:00",
    }

    best = select_best_handoff([older, newer])

    assert best is not None
    assert best["filename"] == "kb_3CC79359.json"


def test_select_best_handoff_prefers_sort_timestamp_over_longer_summary():
    older = {
        "filename": "kb_014B8ABB.json",
        "date": "2026-06-14",
        "summary": "Much longer older same-day handoff atom. " * 40,
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-06-14",
        "_sort_at": "2026-06-14T14:57:06-06:00",
    }
    newer = {
        "filename": "kb_7D81F13A.json",
        "date": "2026-06-14",
        "summary": "Shorter newer carry-forward atom.",
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-06-14",
        "_sort_at": "2026-06-14T16:52:00-06:00",
    }

    best = select_best_handoff([older, newer])

    assert best is not None
    assert best["filename"] == "kb_7D81F13A.json"


def test_select_best_handoff_uses_sort_timestamp_for_same_day_kb_atoms():
    older = {
        "filename": "kb_014B8ABB.json",
        "date": "2026-06-14",
        "summary": "Older same-day handoff atom with date-only valid_at.",
        "open_threads": [],
        "questions": [],
        "_valid_at": "2026-06-14",
        "_sort_at": "2026-06-14T14:57:06-06:00",
    }
    newer = {
        "filename": "kb_7D81F13A.json",
        "date": "2026-06-14",
        "summary": "Newer carry-forward handoff atom written later the same day.",
        "open_threads": ["share-the-stage follow-up optional"],
        "questions": ["Q17: Draft the follow-up or lift MAP-ONLY."],
        "_valid_at": "2026-06-14",
        "_sort_at": "2026-06-14T16:52:00-06:00",
    }

    best = select_best_handoff([older, newer])

    assert best is not None
    assert best["filename"] == "kb_7D81F13A.json"


def test_select_best_handoff_rich_yesterday_beats_thin_stub_today():
    """A rich handoff from yesterday must beat a thin stub from today."""
    thin_today = {
        "filename": "session_handoff-2026-06-29a_hanuman.md",
        "date": "2026-06-29",
        "summary": "I stopped.",
        "open_threads": [],
        "questions": [],
    }
    rich_yesterday = {
        "filename": "session_handoff-2026-06-28z_hanuman.md",
        "date": "2026-06-28",
        "summary": "Security fixes shipped, two new PRs in review",
        "open_threads": ["relgate-promotion watch", "kart-sandbox-phase0"],
        "questions": ["Q17: Open the verify_transport PR and check CI."],
    }
    best = select_best_handoff([thin_today, rich_yesterday])
    assert best is not None
    assert best["filename"] == "session_handoff-2026-06-28z_hanuman.md"


def test_handoff_is_empty_stub_catches_thin_markdown():
    """A markdown stub with no threads, questions, or next-bite should be flagged."""
    thin_md = {
        "filename": "session_handoff-2026-06-29a_hanuman.md",
        "date": "2026-06-29",
        "summary": "I stopped.",
        "open_threads": [],
        "questions": [],
    }
    assert handoff_is_empty_stub(thin_md)


def test_handoff_is_empty_stub_spares_long_summary_markdown():
    """A markdown handoff with a substantive summary (>= 25 words) is not a stub."""
    legacy_md = {
        "filename": "session_handoff-2026-06-29a_hanuman.md",
        "date": "2026-06-29",
        "summary": (
            "Completed a thorough security audit of the write-path sanitizer and "
            "confirmed the write-path injection gate was silently returning None. "
            "Fixed the attribute access bug and added regression tests."
        ),
        "open_threads": [],
        "questions": [],
    }
    assert not handoff_is_empty_stub(legacy_md)


def test_scan_markdown_handoffs_finds_hanuman_session_files():
    root = handoffs_root()
    if not (root / "hanuman").is_dir():
        return
    found = scan_markdown_handoffs("hanuman", root)
    names = {c["filename"] for c in found}
    assert any(n.startswith("session_handoff-2026-06-04") for n in names)
    rich = select_best_handoff(found)
    assert rich is not None
    assert rich.get("open_threads") or rich.get("questions")


_HANDOFF_TEMPLATE = """\
---
agent: {agent}
date: {date}
session: {session}
runtime: claude-code
format: v2
---

# HANDOFF: test

## What I Now Understand

Test session.

## Open Threads

- **item** — something open.

## What We Agreed On

- agreed.

## 17 Questions

Q1: Is this working?
Q17: Run the test.
"""


def test_scan_markdown_handoffs_excludes_other_agents():
    """scan_markdown_handoffs must not return files belonging to a different agent."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "hanuman").mkdir()
        (root / "willow").mkdir()

        # hanuman file — older session
        (root / "hanuman" / "session_handoff-2026-06-09a_hanuman.md").write_text(
            _HANDOFF_TEMPLATE.format(agent="hanuman", date="2026-06-09", session="2026-06-09a")
        )
        # willow file — newer session (would win a naive recency sort)
        (root / "willow" / "session_handoff-2026-06-09d_willow.md").write_text(
            _HANDOFF_TEMPLATE.format(agent="willow", date="2026-06-09", session="2026-06-09d")
        )

        hanuman_candidates = scan_markdown_handoffs("hanuman", root)
        names = {c["filename"] for c in hanuman_candidates}

        assert "session_handoff-2026-06-09d_willow.md" not in names
        assert "session_handoff-2026-06-09a_hanuman.md" in names

        best = select_best_handoff(hanuman_candidates)
        assert best is not None
        assert best["filename"] == "session_handoff-2026-06-09a_hanuman.md"
