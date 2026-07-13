"""Upstream steward triage + notification cursor helpers."""

from agents.hanuman.bin.upstream_watcher import _notifications_since, _to_notification
from agents.hanuman.lib.upstream.triage import Notification, classify


def _n(**overrides) -> Notification:
    base: Notification = {
        "id": "1",
        "reason": "comment",
        "subject_type": "Issue",
        "subject_title": "tooling: add ruff lint to CI",
        "subject_url": "https://api.github.com/repos/almanac-data/climate-almanac/issues/22",
        "repo": "almanac-data/climate-almanac",
        "updated_at": "2026-07-13T04:19:09Z",
        "unread": False,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_author_issue_with_latest_comment_is_draft():
    lane = classify(
        _n(
            reason="author",
            latest_comment_url=(
                "https://api.github.com/repos/almanac-data/climate-almanac/"
                "issues/comments/4954384862"
            ),
        )
    )
    assert lane == "draft"


def test_author_issue_without_comment_stays_watch():
    lane = classify(_n(reason="author"))
    assert lane == "watch"


def test_author_bot_title_stays_out_of_draft_even_with_comment():
    lane = classify(
        _n(
            reason="author",
            subject_title="chore(deps): bump lockfile",
            latest_comment_url="https://api.github.com/repos/x/y/issues/comments/1",
        )
    )
    assert lane == "noise"


def test_to_notification_carries_latest_comment_url():
    raw = {
        "id": "24406555961",
        "reason": "author",
        "updated_at": "2026-07-13T04:19:09Z",
        "unread": False,
        "repository": {"full_name": "almanac-data/climate-almanac"},
        "subject": {
            "type": "Issue",
            "title": "tooling: add ruff lint to CI",
            "url": "https://api.github.com/repos/almanac-data/climate-almanac/issues/22",
            "latest_comment_url": (
                "https://api.github.com/repos/almanac-data/climate-almanac/"
                "issues/comments/4954384862"
            ),
        },
    }
    n = _to_notification(raw)
    assert n["latest_comment_url"].endswith("4954384862")


def test_notifications_since_rewinds_one_second_and_strips_subseconds():
    assert _notifications_since("2026-07-13T04:19:09.983261+00:00") == "2026-07-13T04:19:08Z"


def test_notifications_since_handles_z_suffix():
    assert _notifications_since("2026-07-13T04:19:09Z") == "2026-07-13T04:19:08Z"


def test_notifications_since_none_when_unset():
    assert _notifications_since(None) is None
