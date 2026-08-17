"""Grove MCP client — tailnet-first, envelope-aware.

The real Grove remote server (safe-app-willow-grove: `grove/mcp_local.py
--serve`) is an MCP streamable-HTTP server with OAuth, not a REST API. It
exposes MCP tools (`grove_send_message`, `grove_get_history`,
`grove_list_channels`, ...) at `{base_url}/mcp`. There is no
`GET/POST /channels/{channel}/messages` endpoint anywhere in the fleet.

This client speaks the MCP wire protocol directly over `requests` — a plain
JSON-RPC POST to the streamable-HTTP endpoint, handshake (`initialize` +
`notifications/initialized`) once per process, then `tools/call` per
operation — rather than depending on the `mcp` client SDK. `mcp` pulls in
httpx/anyio/pydantic/sse-starlette, which is a heavy ask for the Termux phone
install that shares this transport module; `requests` is already the app's
only runtime dependency (see pyproject.toml). The wire format is small
enough (three JSON-RPC shapes, one SSE fallback) that hand-rolling it keeps
the dependency-light shape of the rest of ratatosk.
"""
from __future__ import annotations

import itertools
import json
from typing import Any

import requests

from ratatosk.protocol.envelope import Envelope
from ratatosk.transport.config import TransportConfig, load_transport_config

TIMEOUT = 10
MCP_PROTOCOL_VERSION = "2025-06-18"


class GroveMCPError(RuntimeError):
    """Raised when the Grove MCP server returns a JSON-RPC or tool error."""


def _to_mcp_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/mcp"):
        return base
    return f"{base}/mcp"


def _extract_tool_result(result: dict[str, Any]) -> Any:
    """Pull the payload out of an MCP `tools/call` result.

    Grove's tools return plain Python data (list/dict); FastMCP serializes
    that as a JSON text content block (and often also `structuredContent`).
    Prefer the text block — it round-trips lists cleanly, whereas
    `structuredContent` is spec-required to be an object and callers here
    (get_history etc.) expect bare lists back.
    """
    for block in result.get("content") or []:
        if block.get("type") == "text":
            text = block.get("text", "")
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
    if "structuredContent" in result:
        return result["structuredContent"]
    return None


class GroveClient:
    """Talks MCP JSON-RPC over streamable-HTTP to a Grove server."""

    def __init__(self, config: TransportConfig | None = None):
        self.config = config or load_transport_config()
        self.mcp_url = _to_mcp_url(self.config.grove_url)
        self._session_id: str | None = None
        self._initialized = False
        self._ids = itertools.count(1)

    # -- wire plumbing --------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.config.grove_token:
            headers["Authorization"] = f"Bearer {self.config.grove_token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post_raw(self, payload: dict[str, Any]) -> requests.Response:
        r = requests.post(
            self.mcp_url,
            headers=self._headers(),
            json=payload,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        session_id = r.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id
        return r

    @staticmethod
    def _parse_sse(text: str) -> dict[str, Any] | None:
        """Streamable-HTTP may answer a POST with an SSE stream of one or
        more `data:` events. The JSON-RPC response we want is the last
        parseable event on the stream."""
        parsed: dict[str, Any] | None = None
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if not data:
                continue
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
        return parsed

    def _rpc(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        r = self._post_raw(payload)
        content_type = r.headers.get("Content-Type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(r.text)
        if not r.text:
            return None
        return r.json()

    def _notify(self, payload: dict[str, Any]) -> None:
        # Notifications carry no id and expect no body — the server may
        # answer 202 Accepted with an empty response.
        requests.post(
            self.mcp_url,
            headers=self._headers(),
            json=payload,
            timeout=TIMEOUT,
        ).raise_for_status()

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        resp = self._rpc(
            {
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "ratatosk", "version": "1"},
                },
            }
        )
        if resp is None or "error" in resp:
            raise GroveMCPError(f"grove mcp initialize failed: {resp}")
        self._notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self._ensure_initialized()
        resp = self._rpc(
            {
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if resp is None:
            raise GroveMCPError(f"grove mcp: empty response calling {name}")
        if "error" in resp:
            raise GroveMCPError(f"grove mcp: {name} failed: {resp['error']}")
        result = resp.get("result") or {}
        if result.get("isError"):
            raise GroveMCPError(f"grove mcp: {name} returned tool error: {result}")
        return _extract_tool_result(result)

    # -- Grove operations (method names kept stable for callers) --------

    def get_history(self, channel: str, since_id: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        result = self.call_tool(
            "grove_get_history",
            {"channel_name": channel, "limit": limit, "since_id": since_id},
        )
        return result if isinstance(result, list) else []

    def post(self, channel: str, content: str, sender: str | None = None) -> dict[str, Any]:
        result = self.call_tool(
            "grove_send_message",
            {
                "channel_name": channel,
                "content": content,
                "sender": sender or self.config.agent_name,
            },
        )
        return result if isinstance(result, dict) else {}

    def post_envelope(self, channel: str, envelope: Envelope, sender: str | None = None) -> dict[str, Any]:
        return self.post(channel, envelope.to_json(), sender=sender)

    def tail_cursor(self, channel: str) -> int:
        msgs = self.get_history(channel, since_id=0, limit=1)
        return msgs[-1]["id"] if msgs else 0

    def list_channels(self) -> list[dict[str, Any]]:
        result = self.call_tool("grove_list_channels", {})
        return result if isinstance(result, list) else []

    def ping(self) -> tuple[bool, str]:
        try:
            channels = self.list_channels()
            return True, f"grove mcp reachable ({len(channels)} channels)"
        except Exception as exc:
            return False, str(exc)
