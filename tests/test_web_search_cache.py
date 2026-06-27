"""Tests for the web_search in-process LRU/TTL query cache (Phase 4).

Covers the standalone `_TTLCache` (LRU eviction, lazy TTL expiry via an
injectable clock), the current-events TTL heuristic, the sha256 cache-key
sensitivity, and the `search_web` integration: hit/miss, `cache=False` and
`WILLOW_SEARCH_CACHE=0` bypass, the empty-result no-cache rule, and short-TTL
selection for current-events queries.
"""

from __future__ import annotations

from typing import Any

import pytest

from core import web_search


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Fresh cache + breaker state, deterministic single-provider chain."""
    web_search.reset_circuit_breakers()
    web_search.reset_search_cache()
    monkeypatch.setenv("WILLOW_SEARCH_MAX_ATTEMPTS", "1")
    monkeypatch.delenv("WILLOW_SEARCH_PROVIDER_ORDER", raising=False)
    monkeypatch.delenv("WILLOW_SEARCH_CACHE", raising=False)
    yield
    web_search.reset_circuit_breakers()
    web_search.reset_search_cache()


def _hit(url: str) -> dict[str, Any]:
    host = url.split("//")[-1].split("/")[0]
    return {"title": "t", "url": url, "snippet": "s", "source": host,
            "source_id": "web", "date": "", "hostname": host}


class _Provider:
    """Counts calls so we can prove the cache shortcut the provider chain."""

    def __init__(self, name="p", results=None, available=True):
        self.name = name
        self._results = results or []
        self._available = available
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def search(self, query: str, max_results: int):
        self.calls += 1
        return list(self._results)


class _Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


# --------------------------------------------------------------------------- #
# _TTLCache unit
# --------------------------------------------------------------------------- #


def test_ttlcache_hit_then_expiry():
    clock = _Clock()
    cache = web_search._TTLCache(maxsize=4, clock=clock)
    cache.set("k", [1, 2], ttl=10.0)
    assert cache.get("k") == [1, 2]
    clock.t = 9.9
    assert cache.get("k") == [1, 2]
    clock.t = 10.0  # expires_at is inclusive -> miss
    assert cache.get("k") is None
    assert len(cache) == 0  # expired entry dropped lazily on access


def test_ttlcache_lru_eviction():
    cache = web_search._TTLCache(maxsize=2)
    cache.set("a", 1, ttl=100)
    cache.set("b", 2, ttl=100)
    assert cache.get("a") == 1  # touch a -> b is now LRU
    cache.set("c", 3, ttl=100)  # evicts b
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_ttlcache_reset_rereads_size(monkeypatch):
    monkeypatch.setenv("WILLOW_SEARCH_CACHE_SIZE", "1")
    web_search.reset_search_cache()
    assert web_search._SEARCH_CACHE._maxsize == 1


# --------------------------------------------------------------------------- #
# current-events heuristic + key
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("query", ["latest iphone news", "BREAKING election",
                                   "what happened today", "live scores"])
def test_is_current_events_true(query):
    assert web_search._is_current_events(query) is True


@pytest.mark.parametrize("query", ["history of rome", "python decorators",
                                   "newton's laws"])
def test_is_current_events_false(query):
    assert web_search._is_current_events(query) is False


def test_cache_key_normalizes_and_differs():
    k1 = web_search._cache_key("  Hello   World ", 8, False, False, ["ddg_html"])
    k2 = web_search._cache_key("hello world", 8, False, False, ["ddg_html"])
    assert k1 == k2  # whitespace + case normalized
    # any param that changes the result set changes the key
    assert k1 != web_search._cache_key("hello world", 5, False, False, ["ddg_html"])
    assert k1 != web_search._cache_key("hello world", 8, True, False, ["ddg_html"])
    assert k1 != web_search._cache_key("hello world", 8, False, True, ["ddg_html"])
    assert k1 != web_search._cache_key("hello world", 8, False, False, ["brave"])


# --------------------------------------------------------------------------- #
# search_web integration
# --------------------------------------------------------------------------- #


def test_search_web_caches_and_shortcuts_provider():
    p = _Provider(results=[_hit("https://a.test")])
    first = web_search.search_web("rome aqueducts", providers=[p])
    second = web_search.search_web("rome aqueducts", providers=[p])
    assert first == second == [_hit("https://a.test")]
    assert p.calls == 1  # second call served from cache


def test_search_web_cache_false_bypasses():
    p = _Provider(results=[_hit("https://a.test")])
    web_search.search_web("rome aqueducts", providers=[p])
    web_search.search_web("rome aqueducts", providers=[p], cache=False)
    assert p.calls == 2  # bypass both serves and stores nothing new from #2


def test_search_web_cache_disabled_via_env(monkeypatch):
    monkeypatch.setenv("WILLOW_SEARCH_CACHE", "0")
    p = _Provider(results=[_hit("https://a.test")])
    web_search.search_web("rome aqueducts", providers=[p])
    web_search.search_web("rome aqueducts", providers=[p])
    assert p.calls == 2


def test_search_web_does_not_cache_empty():
    p = _Provider(results=[])
    web_search.search_web("rome aqueducts", providers=[p])
    web_search.search_web("rome aqueducts", providers=[p])
    assert p.calls == 2  # empty result never pinned


def test_search_web_returns_copy_not_cached_ref():
    p = _Provider(results=[_hit("https://a.test")])
    first = web_search.search_web("rome aqueducts", providers=[p])
    first.append("mutation")
    second = web_search.search_web("rome aqueducts", providers=[p])
    assert second == [_hit("https://a.test")]  # caller mutation didn't leak


def test_search_web_current_events_uses_short_ttl(monkeypatch):
    captured: dict[str, float] = {}
    real_set = web_search._SEARCH_CACHE.set

    def spy(key, value, ttl):
        captured["ttl"] = ttl
        return real_set(key, value, ttl)

    monkeypatch.setattr(web_search._SEARCH_CACHE, "set", spy)
    monkeypatch.setenv("WILLOW_SEARCH_CACHE_TTL", "300")
    monkeypatch.setenv("WILLOW_SEARCH_CACHE_TTL_NEWS", "60")
    p = _Provider(results=[_hit("https://a.test")])
    web_search.search_web("latest mars news", providers=[p])
    assert captured["ttl"] == 60.0
