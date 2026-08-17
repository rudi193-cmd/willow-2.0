"""Tests for the Grove MCP client — mocks the HTTP/JSON-RPC layer, no live server."""
from __future__ import annotations

import json

import pytest

from ratatosk.transport.config import TransportConfig
from ratatosk.transport.grove_client import GroveClient, GroveMCPError


def make_config(url: str = "http://100.64.0.5:8787", token: str = "test-token") -> TransportConfig:
    return TransportConfig(
        mode="tailnet",
        grove_url=url,
        grove_token=token,
        agent_name="ratatosk",
        public_exposure=False,
        tailnet_url=url,
        ngrok_url="",
        cloudflare_url="",
        pangolin_url="",
        funnel_url="",
    )


class FakeResponse:
    def __init__(self, payload=None, *, headers=None, status_code=200, text_override=None, content_type="application/json"):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": content_type, **(headers or {})}
        if text_override is not None:
            self.text = text_override
        elif payload is None:
            self.text = ""
        else:
            self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.text)


class FakeTransport:
    """Records every POST and answers initialize / notifications / tools/call."""

    def __init__(self, tool_results: dict[str, object] | None = None, session_id: str = "sess-1"):
        self.calls: list[dict] = []
        self.tool_results = tool_results or {}
        self.session_id = session_id

    def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002 - matches requests.post signature
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        method = json.get("method")
        if method == "initialize":
            return FakeResponse(
                {"jsonrpc": "2.0", "id": json["id"], "result": {"protocolVersion": "2025-06-18"}},
                headers={"Mcp-Session-Id": self.session_id},
            )
        if method == "notifications/initialized":
            return FakeResponse(None, status_code=202)
        if method == "tools/call":
            name = json["params"]["name"]
            arguments = json["params"]["arguments"]
            if name not in self.tool_results:
                raise AssertionError(f"unexpected tool call: {name}")
            result = self.tool_results[name](arguments)
            return FakeResponse({"jsonrpc": "2.0", "id": json["id"], "result": result})
        raise AssertionError(f"unexpected method: {method}")


def _text_result(payload) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": False}


@pytest.fixture
def transport(monkeypatch):
    fake = FakeTransport()
    monkeypatch.setattr("ratatosk.transport.grove_client.requests.post", fake.post)
    return fake


def test_get_history_calls_grove_get_history_tool(transport):
    transport.tool_results["grove_get_history"] = lambda args: _text_result(
        [{"id": 3, "sender": "phone", "content": "hi"}]
    )
    client = GroveClient(config=make_config())
    msgs = client.get_history("dispatch", since_id=1, limit=25)

    assert msgs == [{"id": 3, "sender": "phone", "content": "hi"}]
    call = next(c for c in transport.calls if c["json"].get("method") == "tools/call")
    assert call["json"]["params"]["name"] == "grove_get_history"
    assert call["json"]["params"]["arguments"] == {
        "channel_name": "dispatch",
        "limit": 25,
        "since_id": 1,
    }


def test_handshake_happens_once_before_first_tool_call(transport):
    transport.tool_results["grove_get_history"] = lambda args: _text_result([])
    client = GroveClient(config=make_config())
    client.get_history("dispatch")
    client.get_history("dispatch")

    methods = [c["json"].get("method") for c in transport.calls]
    assert methods.count("initialize") == 1
    assert methods.count("notifications/initialized") == 1
    assert methods.count("tools/call") == 2


def test_session_id_threaded_into_later_requests(transport):
    transport.tool_results["grove_get_history"] = lambda args: _text_result([])
    client = GroveClient(config=make_config())
    client.get_history("dispatch")

    tool_call = next(c for c in transport.calls if c["json"].get("method") == "tools/call")
    assert tool_call["headers"]["Mcp-Session-Id"] == "sess-1"


def test_bearer_token_sent_on_every_request(transport):
    transport.tool_results["grove_get_history"] = lambda args: _text_result([])
    client = GroveClient(config=make_config(token="secret-tok"))
    client.get_history("dispatch")

    for call in transport.calls:
        assert call["headers"]["Authorization"] == "Bearer secret-tok"


def test_post_calls_grove_send_message_tool(transport):
    transport.tool_results["grove_send_message"] = lambda args: _text_result(
        {"id": 9, "channel": args["channel_name"], "sent": True}
    )
    client = GroveClient(config=make_config())
    result = client.post("general", "hello world", sender="ratatosk")

    assert result == {"id": 9, "channel": "general", "sent": True}
    call = next(c for c in transport.calls if c["json"].get("method") == "tools/call")
    assert call["json"]["params"]["name"] == "grove_send_message"
    assert call["json"]["params"]["arguments"] == {
        "channel_name": "general",
        "content": "hello world",
        "sender": "ratatosk",
    }


def test_post_defaults_sender_to_agent_name(transport):
    transport.tool_results["grove_send_message"] = lambda args: _text_result({"sent": True})
    client = GroveClient(config=make_config())
    client.post("general", "hi")

    call = next(c for c in transport.calls if c["json"].get("method") == "tools/call")
    assert call["json"]["params"]["arguments"]["sender"] == "ratatosk"


def test_tail_cursor_uses_last_message_id(transport):
    transport.tool_results["grove_get_history"] = lambda args: _text_result(
        [{"id": 41, "sender": "x", "content": "y"}]
    )
    client = GroveClient(config=make_config())
    assert client.tail_cursor("dispatch") == 41


def test_tail_cursor_zero_when_empty(transport):
    transport.tool_results["grove_get_history"] = lambda args: _text_result([])
    client = GroveClient(config=make_config())
    assert client.tail_cursor("dispatch") == 0


def test_ping_true_on_reachable_server(transport):
    transport.tool_results["grove_list_channels"] = lambda args: _text_result(
        [{"id": 1, "name": "general", "type": "group", "description": None}]
    )
    client = GroveClient(config=make_config())
    ok, detail = client.ping()
    assert ok is True
    assert "1 channels" in detail


def test_ping_false_on_transport_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("ratatosk.transport.grove_client.requests.post", boom)
    client = GroveClient(config=make_config())
    ok, detail = client.ping()
    assert ok is False
    assert "connection refused" in detail


def test_jsonrpc_error_raises_grove_mcp_error(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        if json.get("method") == "initialize":
            return FakeResponse({"jsonrpc": "2.0", "id": json["id"], "result": {}})
        if json.get("method") == "notifications/initialized":
            return FakeResponse(None, status_code=202)
        return FakeResponse(
            {"jsonrpc": "2.0", "id": json["id"], "error": {"code": -32601, "message": "no such tool"}}
        )

    monkeypatch.setattr("ratatosk.transport.grove_client.requests.post", fake_post)
    client = GroveClient(config=make_config())
    with pytest.raises(GroveMCPError):
        client.get_history("dispatch")


def test_tool_is_error_raises_grove_mcp_error(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        if json.get("method") == "initialize":
            return FakeResponse({"jsonrpc": "2.0", "id": json["id"], "result": {}})
        if json.get("method") == "notifications/initialized":
            return FakeResponse(None, status_code=202)
        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": json["id"],
                "result": {"content": [{"type": "text", "text": "boom"}], "isError": True},
            }
        )

    monkeypatch.setattr("ratatosk.transport.grove_client.requests.post", fake_post)
    client = GroveClient(config=make_config())
    with pytest.raises(GroveMCPError):
        client.post("general", "hi")


def test_sse_response_is_parsed(monkeypatch):
    """Streamable-HTTP servers may answer a POST with an SSE stream."""

    def fake_post(url, headers=None, json=None, timeout=None):
        if json.get("method") == "initialize":
            body = (
                "event: message\n"
                f"data: {json_dumps({'jsonrpc': '2.0', 'id': json['id'], 'result': {}})}\n\n"
            )
            return FakeResponse(text_override=body, content_type="text/event-stream")
        if json.get("method") == "notifications/initialized":
            return FakeResponse(None, status_code=202)
        result = {"content": [{"type": "text", "text": json_dumps([{"id": 5}])}], "isError": False}
        body = f"data: {json_dumps({'jsonrpc': '2.0', 'id': json['id'], 'result': result})}\n\n"
        return FakeResponse(text_override=body, content_type="text/event-stream")

    def json_dumps(obj):
        return json.dumps(obj)

    monkeypatch.setattr("ratatosk.transport.grove_client.requests.post", fake_post)
    client = GroveClient(config=make_config())
    msgs = client.get_history("dispatch")
    assert msgs == [{"id": 5}]


def test_mcp_url_appends_mcp_suffix():
    client = GroveClient(config=make_config(url="http://100.64.0.5:8787"))
    assert client.mcp_url == "http://100.64.0.5:8787/mcp"


def test_mcp_url_not_doubled_when_already_present():
    client = GroveClient(config=make_config(url="http://100.64.0.5:8787/mcp"))
    assert client.mcp_url == "http://100.64.0.5:8787/mcp"
