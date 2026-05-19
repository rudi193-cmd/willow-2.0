from sap.handoff_index import latest_handoff_sort_key, select_latest_handoff


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
