"""Tests for core/public_demo.py — retrieval formatting and demo pack."""

from core.public_demo import (
    DEMO_ATOMS,
    SUGGESTED_QUESTION,
    _compact_query,
    chat_retrieval,
    demo_banner,
    format_retrieval_reply,
    concierge_greeting,
)


class _FakeBridge:
    def __init__(self, rows=None):
        self._rows = rows or []

    def knowledge_search(self, query, project=None, limit=5, exclude_superseded=True):
        if project and self._rows:
            return [r for r in self._rows if r.get("project") == project][:limit]
        return self._rows[:limit]


def test_demo_banner_honest():
    assert "Demo memory" in demo_banner()
    assert "real" in demo_banner().lower()


def test_concierge_includes_suggested_question():
    text = concierge_greeting(first_run=True)
    assert SUGGESTED_QUESTION in text


def test_format_retrieval_reply_lists_atoms():
    rows = [{"title": "Public launch tag", "summary": "v1.0.0-public"}]
    out = format_retrieval_reply("launch tag", rows)
    assert "Here's what I have about that" in out
    assert "Public launch tag" in out
    assert demo_banner() in out


def test_format_retrieval_reply_empty():
    out = format_retrieval_reply("nothing", [])
    assert "Nothing on file" in out


def test_chat_retrieval_uses_fake_bridge():
    rows = [
        {
            "id": "PUBDEMO01",
            "project": "willow-public-demo",
            "title": "Public launch tag",
            "summary": "v1.0.0-public",
        }
    ]
    bridge = _FakeBridge(rows)
    result = chat_retrieval(bridge, "public launch tag")
    assert result["mode"] == "retrieval"
    assert "v1.0.0-public" in result["reply"]
    assert result["atoms"][0]["id"] == "PUBDEMO01"


def test_demo_atom_pack_has_hero_hook():
    titles = {a["title"] for a in DEMO_ATOMS}
    assert "Public launch tag" in titles
    assert len(DEMO_ATOMS) >= 5


def test_compact_query_strips_stop_words_for_hero_question():
    assert _compact_query(SUGGESTED_QUESTION) == "public launch tag"
