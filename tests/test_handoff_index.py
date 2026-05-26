from sap.handoff_index import (
    extract_next_bite,
    handoff_richness_score,
    latest_handoff_sort_key,
    select_best_handoff,
    select_latest_handoff,
)


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
