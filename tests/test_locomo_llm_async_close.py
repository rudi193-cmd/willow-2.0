"""Async resource cleanup for LoCoMo LLM adapters."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

BENCH_DIR = Path(__file__).resolve().parent.parent / "willow" / "bench" / "locomo"
sys.path.insert(0, str(BENCH_DIR))

from locomo_llm import ClaudeAdapter, ClaudeJudge, MockAdapter, OllamaAdapter  # noqa: E402


def test_claude_adapter_aclose_closes_client():
    adapter = ClaudeAdapter.__new__(ClaudeAdapter)
    adapter.model = "claude-sonnet-4-6"
    client = MagicMock()
    client.is_closed = False
    client.close = AsyncMock()
    adapter._client = client

    asyncio.run(adapter.aclose())

    client.close.assert_awaited_once()
    assert adapter._client is None


def test_claude_adapter_aclose_skips_when_already_closed():
    adapter = ClaudeAdapter.__new__(ClaudeAdapter)
    client = MagicMock()
    client.is_closed = True
    client.close = AsyncMock()
    adapter._client = client

    asyncio.run(adapter.aclose())

    client.close.assert_not_awaited()


def test_claude_judge_aclose_closes_client():
    judge = ClaudeJudge.__new__(ClaudeJudge)
    judge.model = "claude-sonnet-4-6"
    client = MagicMock()
    client.is_closed = False
    client.close = AsyncMock()
    judge._client = client

    asyncio.run(judge.aclose())

    client.close.assert_awaited_once()
    assert judge._client is None


def test_ollama_adapter_aclose_closes_session():
    adapter = OllamaAdapter.__new__(OllamaAdapter)
    session = MagicMock()
    session.closed = False
    session.close = AsyncMock()
    adapter._session = session

    asyncio.run(adapter.aclose())

    session.close.assert_awaited_once()


def test_mock_adapter_aclose_is_noop():
    asyncio.run(MockAdapter().aclose())
