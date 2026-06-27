"""Tests for the web_search retry + circuit-breaker layer (Phase 3).

Covers the typed-error classification in `_ddg_fetch`, the `_with_retry`
backoff loop, the `CircuitBreaker` state machine, and their integration in
`_search_providers`. The public `ddg_html_search` back-compat contract
(never raises, returns [] on error) is also asserted.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests

from core import web_search
from core.web_search import (
    CircuitBreaker,
    HardBlockError,
    SearchError,
    TransientSearchError,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Reset breaker state and default to a single attempt (no real sleeps)."""
    web_search.reset_circuit_breakers()
    monkeypatch.setenv("WILLOW_SEARCH_MAX_ATTEMPTS", "1")
    monkeypatch.delenv("WILLOW_SEARCH_PROVIDER_ORDER", raising=False)
    yield
    web_search.reset_circuit_breakers()


class _FakeResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def _hit(url: str) -> dict[str, Any]:
    host = url.split("//")[-1].split("/")[0]
    return {"title": "t", "url": url, "snippet": "s", "source": host,
            "source_id": "web", "date": "", "hostname": host}


class _Provider:
    def __init__(self, name="p", results=None, exc=None, available=True):
        self.name = name
        self._results = results or []
        self._exc = exc
        self._available = available
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def search(self, query: str, max_results: int):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return list(self._results)


# --------------------------------------------------------------------------- #
# _ddg_fetch error classification
# --------------------------------------------------------------------------- #


def test_ddg_fetch_hard_block_raises(monkeypatch):
    monkeypatch.setattr(web_search.requests, "post", lambda *a, **k: _FakeResp(403))
    with pytest.raises(HardBlockError):
        web_search._ddg_fetch("q")


def test_ddg_fetch_retryable_status_raises_transient(monkeypatch):
    monkeypatch.setattr(web_search.requests, "post", lambda *a, **k: _FakeResp(429))
    with pytest.raises(TransientSearchError):
        web_search._ddg_fetch("q")


def test_ddg_fetch_timeout_is_transient(monkeypatch):
    def boom(*a, **k):
        raise requests.Timeout("slow")
    monkeypatch.setattr(web_search.requests, "post", boom)
    with pytest.raises(TransientSearchError):
        web_search._ddg_fetch("q")


def test_ddg_fetch_connection_error_is_transient(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(web_search.requests, "post", boom)
    with pytest.raises(TransientSearchError):
        web_search._ddg_fetch("q")


def test_ddg_fetch_other_4xx_is_search_error(monkeypatch):
    monkeypatch.setattr(web_search.requests, "post", lambda *a, **k: _FakeResp(418))
    with pytest.raises(SearchError):
        web_search._ddg_fetch("q")


def test_ddg_fetch_empty_query_returns_empty():
    assert web_search._ddg_fetch("   ") == []


def test_ddg_html_search_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise TransientSearchError("nope")
    monkeypatch.setattr(web_search, "_ddg_fetch", boom)
    assert web_search.ddg_html_search("q") == []


# --------------------------------------------------------------------------- #
# _with_retry
# --------------------------------------------------------------------------- #


def test_retry_returns_on_first_success():
    calls = []
    out = web_search._with_retry(lambda: calls.append(1) or "ok", sleep=lambda d: None)
    assert out == "ok" and len(calls) == 1


def test_retry_recovers_after_transient():
    state = {"n": 0}

    def fn():
        state["n"] += 1
        if state["n"] < 3:
            raise TransientSearchError("blip")
        return "ok"

    slept = []
    out = web_search._with_retry(
        fn, max_attempts=3, budget=999, base_backoff=0.01, sleep=slept.append
    )
    assert out == "ok"
    assert state["n"] == 3
    assert len(slept) == 2  # two backoffs before the third attempt


def test_retry_exhausts_and_raises():
    def fn():
        raise TransientSearchError("always")
    with pytest.raises(TransientSearchError):
        web_search._with_retry(fn, max_attempts=3, budget=999, base_backoff=0.01,
                               sleep=lambda d: None)


def test_retry_does_not_retry_hard_block():
    calls = []

    def fn():
        calls.append(1)
        raise HardBlockError("403")

    with pytest.raises(HardBlockError):
        web_search._with_retry(fn, max_attempts=3, sleep=lambda d: None)
    assert len(calls) == 1  # no retries on hard block


def test_retry_stops_when_budget_would_be_exceeded():
    calls = []
    # clock jumps 100s per check; any backoff would blow the 1s budget.
    ticks = iter([0, 100, 200, 300, 400])

    def fn():
        calls.append(1)
        raise TransientSearchError("slow")

    with pytest.raises(TransientSearchError):
        web_search._with_retry(
            fn, max_attempts=5, budget=1.0, base_backoff=1.0,
            sleep=lambda d: None, clock=lambda: next(ticks),
        )
    assert len(calls) == 1  # budget gate broke before a second attempt


# --------------------------------------------------------------------------- #
# CircuitBreaker
# --------------------------------------------------------------------------- #


def test_breaker_starts_closed_and_allows():
    cb = CircuitBreaker()
    assert cb.state == "CLOSED" and cb.allow() is True


def test_breaker_trips_after_threshold():
    cb = CircuitBreaker(fail_threshold=3, clock=lambda: 0.0)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.allow() is False


def test_breaker_success_resets_failures():
    cb = CircuitBreaker(fail_threshold=3, clock=lambda: 0.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert cb.state == "CLOSED"  # counter was reset, one failure isn't enough


def test_breaker_half_open_after_cooldown():
    now = {"t": 0.0}
    cb = CircuitBreaker(fail_threshold=1, base_cooldown=30.0, clock=lambda: now["t"])
    cb.record_failure()
    assert cb.allow() is False  # still within cooldown
    now["t"] = 31.0
    assert cb.allow() is True   # cooldown elapsed → half-open probe
    assert cb.state == "HALF_OPEN"


def test_breaker_half_open_failure_reopens_with_longer_cooldown():
    now = {"t": 0.0}
    cb = CircuitBreaker(fail_threshold=1, base_cooldown=30.0, max_cooldown=300.0,
                        clock=lambda: now["t"])
    cb.record_failure()       # OPEN, cooldown 30
    now["t"] = 31.0
    cb.allow()                # → HALF_OPEN
    cb.record_failure()       # probe fails → OPEN, cooldown 60
    now["t"] = 62.0
    assert cb.allow() is False  # 31s elapsed < 60s new cooldown
    now["t"] = 92.0
    assert cb.allow() is True


def test_breaker_half_open_success_closes():
    now = {"t": 0.0}
    cb = CircuitBreaker(fail_threshold=1, base_cooldown=30.0, clock=lambda: now["t"])
    cb.record_failure()
    now["t"] = 31.0
    cb.allow()                # HALF_OPEN
    cb.record_success()
    assert cb.state == "CLOSED" and cb.allow() is True


# --------------------------------------------------------------------------- #
# _search_providers integration
# --------------------------------------------------------------------------- #


def test_chain_advances_on_hard_block_and_records_failure():
    a = _Provider("a", exc=HardBlockError("403"))
    b = _Provider("b", results=[_hit("https://x.com")])
    out = web_search._search_providers("q", 8, providers=[a, b])
    assert [h["url"] for h in out] == ["https://x.com"]
    assert a.calls == 1
    assert web_search._get_breaker("a").state in ("CLOSED", "OPEN")


def test_chain_advances_on_transient_failure():
    a = _Provider("a", exc=TransientSearchError("429"))
    b = _Provider("b", results=[_hit("https://x.com")])
    out = web_search._search_providers("q", 8, providers=[a, b])
    assert [h["url"] for h in out] == ["https://x.com"]


def test_chain_trips_breaker_and_skips_open_provider():
    a = _Provider("a", exc=TransientSearchError("429"))
    # Drive 5 consecutive failures to trip the default threshold.
    for _ in range(5):
        web_search._search_providers("q", 8, providers=[a])
    assert web_search._get_breaker("a").state == "OPEN"
    calls_before = a.calls
    # Next call should skip the open provider without invoking search().
    web_search._search_providers("q", 8, providers=[a])
    assert a.calls == calls_before


def test_chain_records_success_and_resets_breaker():
    a = _Provider("a", results=[_hit("https://x.com")])
    web_search._get_breaker("a").record_failure()
    web_search._search_providers("q", 8, providers=[a])
    assert web_search._get_breaker("a").state == "CLOSED"
