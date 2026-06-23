"""Tests for sap/security_middleware.py — HTTP API key gate."""
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from sap import security_middleware as sm


async def _ok(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _app() -> Starlette:
    return Starlette(routes=[Route("/", _ok)])


def test_check_api_key_allows_when_unconfigured():
    assert sm.check_api_key(Request({"type": "http", "headers": []})) is True


def test_check_api_key_blocks_bad_header(monkeypatch):
    monkeypatch.setattr(sm, "WILLOW_MCP_API_KEY", "secret")
    scope = {
        "type": "http",
        "headers": [(b"x-willow-key", b"wrong")],
        "method": "GET",
        "path": "/",
    }
    assert sm.check_api_key(Request(scope)) is False


def test_check_api_key_accepts_good_header(monkeypatch):
    monkeypatch.setattr(sm, "WILLOW_MCP_API_KEY", "secret")
    scope = {
        "type": "http",
        "headers": [(b"x-willow-key", b"secret")],
        "method": "GET",
        "path": "/",
    }
    assert sm.check_api_key(Request(scope)) is True


def test_verify_transport_warns_public_http_without_key(monkeypatch, caplog):
    monkeypatch.setattr(sm, "WILLOW_MCP_API_KEY", "")
    with caplog.at_level("WARNING"):
        assert sm.verify_transport("http", host="0.0.0.0") is False
    assert "WILLOW_MCP_API_KEY" in caplog.text


def test_wrap_streamable_http_app_noop_without_key():
    app = _app()
    assert sm.wrap_streamable_http_app(app) is app


@pytest.mark.anyio
async def test_api_key_middleware_blocks(monkeypatch):
    monkeypatch.setattr(sm, "WILLOW_MCP_API_KEY", "secret")
    app = sm.wrap_streamable_http_app(_app())
    scope = {
        "type": "http",
        "headers": [],
        "method": "GET",
        "path": "/",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    started = False

    async def send(message):
        nonlocal started
        if message["type"] == "http.response.start":
            started = True
            assert message["status"] == 401

    await app(scope, receive, send)
    assert started
