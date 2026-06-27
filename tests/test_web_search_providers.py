"""Tests for the web_search provider seam (Phase 1).

Covers the new SearchProvider abstraction and confirms the refactor is
behavior-preserving: an unconfigured call still returns exactly what the
DuckDuckGo HTML scrape returned before.
"""

from __future__ import annotations

from typing import Any

from core import web_search


def _hit(url: str, title: str = "t", hostname: str | None = None) -> dict[str, Any]:
    host = hostname if hostname is not None else url.split("//")[-1].split("/")[0]
    return {
        "title": title,
        "url": url,
        "snippet": "s",
        "source": host,
        "source_id": "web",
        "date": "",
        "hostname": host,
    }


class _FakeProvider:
    """Minimal provider for chain tests."""

    def __init__(self, name: str, results=None, available=True, raises=False):
        self.name = name
        self._results = results or []
        self._available = available
        self._raises = raises
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        self.calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return list(self._results)


# --------------------------------------------------------------------------- #
# Provider registry / chain construction
# --------------------------------------------------------------------------- #


def test_default_chain_is_ddg_only(monkeypatch):
    monkeypatch.delenv("WILLOW_SEARCH_PROVIDER_ORDER", raising=False)
    chain = web_search.build_providers()
    assert [p.name for p in chain] == ["ddg_html"]
    assert isinstance(chain[0], web_search.DDGHtmlProvider)


def test_provider_order_from_env(monkeypatch):
    monkeypatch.setenv("WILLOW_SEARCH_PROVIDER_ORDER", "brave, ddg_html")
    assert [p.name for p in web_search.build_providers()] == ["brave", "ddg_html"]


def test_unknown_provider_is_skipped(monkeypatch):
    monkeypatch.setenv("WILLOW_SEARCH_PROVIDER_ORDER", "nope, ddg_html")
    assert [p.name for p in web_search.build_providers()] == ["ddg_html"]


def test_explicit_order_overrides_env(monkeypatch):
    monkeypatch.setenv("WILLOW_SEARCH_PROVIDER_ORDER", "ddg_html")
    assert [p.name for p in web_search.build_providers(["brave"])] == ["brave"]


def test_ddg_provider_satisfies_protocol():
    assert isinstance(web_search.DDGHtmlProvider(), web_search.SearchProvider)


# --------------------------------------------------------------------------- #
# Brave stub — present but not yet active
# --------------------------------------------------------------------------- #


def test_brave_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    assert web_search.BraveSearchProvider().available() is False


def test_brave_unavailable_even_with_key(monkeypatch):
    # Key present but implementation flag off → still unavailable in Phase 1.
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    assert web_search.BraveSearchProvider().available() is False


def test_brave_search_returns_empty():
    assert web_search.BraveSearchProvider(api_key="k").search("q", 5) == []


# --------------------------------------------------------------------------- #
# Chain fallback semantics
# --------------------------------------------------------------------------- #


def test_chain_advances_on_empty():
    empty = _FakeProvider("a", results=[])
    full = _FakeProvider("b", results=[_hit("https://x.com")])
    out = web_search._search_providers("q", 8, providers=[empty, full])
    assert [h["url"] for h in out] == ["https://x.com"]
    assert empty.calls == 1 and full.calls == 1


def test_chain_advances_on_exception():
    boom = _FakeProvider("a", raises=True)
    full = _FakeProvider("b", results=[_hit("https://x.com")])
    out = web_search._search_providers("q", 8, providers=[boom, full])
    assert [h["url"] for h in out] == ["https://x.com"]
    assert full.calls == 1


def test_chain_skips_unavailable_without_calling():
    off = _FakeProvider("a", results=[_hit("https://x.com")], available=False)
    full = _FakeProvider("b", results=[_hit("https://y.com")])
    out = web_search._search_providers("q", 8, providers=[off, full])
    assert [h["url"] for h in out] == ["https://y.com"]
    assert off.calls == 0


def test_chain_returns_first_nonempty_and_stops():
    first = _FakeProvider("a", results=[_hit("https://x.com")])
    second = _FakeProvider("b", results=[_hit("https://y.com")])
    out = web_search._search_providers("q", 8, providers=[first, second])
    assert [h["url"] for h in out] == ["https://x.com"]
    assert second.calls == 0


def test_chain_exhausted_returns_empty():
    out = web_search._search_providers("q", 8, providers=[_FakeProvider("a")])
    assert out == []


# --------------------------------------------------------------------------- #
# search_web behavior preservation
# --------------------------------------------------------------------------- #


def test_search_web_uses_ddg_by_default(monkeypatch):
    captured = {}

    def fake_ddg(query, max_results=8):
        captured["query"] = query
        captured["max_results"] = max_results
        return [_hit("https://example.com")]

    monkeypatch.setattr(web_search, "ddg_html_search", fake_ddg)
    monkeypatch.delenv("WILLOW_SEARCH_PROVIDER_ORDER", raising=False)
    out = web_search.search_web("hello", max_results=5)
    assert [h["url"] for h in out] == ["https://example.com"]
    assert captured == {"query": "hello", "max_results": 5}


def test_search_web_trusted_only_filter():
    provider = _FakeProvider(
        "p",
        results=[_hit("https://nasa.gov/a"), _hit("https://spam.example/b")],
    )
    out = web_search.search_web("q", trusted_only=True, providers=[provider])
    assert [h["url"] for h in out] == ["https://nasa.gov/a"]


def test_search_web_include_handoffs_prepended():
    provider = _FakeProvider("p", results=[_hit("https://example.com")])
    out = web_search.search_web("coffee shops", include_handoffs=True, providers=[provider])
    assert out[0]["source_id"] == "maps_osm"
    assert any(h["url"] == "https://example.com" for h in out)


def test_search_web_dedups_by_url():
    provider = _FakeProvider(
        "p",
        results=[_hit("https://dup.com"), _hit("https://dup.com")],
    )
    out = web_search.search_web("q", providers=[provider])
    assert [h["url"] for h in out] == ["https://dup.com"]


def test_search_web_empty_chain_returns_empty():
    assert web_search.search_web("q", providers=[_FakeProvider("p")]) == []
