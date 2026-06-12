"""HTTP Grove client — tailnet-first, envelope-aware."""
from __future__ import annotations

from typing import Any

import requests

from ratatosk.protocol.envelope import Envelope
from ratatosk.transport.config import TransportConfig, load_transport_config

TIMEOUT = 10


class GroveClient:
    def __init__(self, config: TransportConfig | None = None):
        self.config = config or load_transport_config()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.grove_token}",
            "Content-Type": "application/json",
        }

    def get_history(self, channel: str, since_id: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        r = requests.get(
            f"{self.config.grove_url}/channels/{channel}/messages",
            headers=self._headers(),
            params={"since_id": since_id, "limit": limit},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json() if r.text else []
        return data if isinstance(data, list) else data.get("messages", [])

    def post(self, channel: str, content: str, sender: str | None = None) -> dict[str, Any]:
        r = requests.post(
            f"{self.config.grove_url}/channels/{channel}/messages",
            headers=self._headers(),
            json={"content": content, "sender": sender or self.config.agent_name},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json() if r.text else {}

    def post_envelope(self, channel: str, envelope: Envelope, sender: str | None = None) -> dict[str, Any]:
        return self.post(channel, envelope.to_json(), sender=sender)

    def tail_cursor(self, channel: str) -> int:
        msgs = self.get_history(channel, since_id=0, limit=1)
        return msgs[-1]["id"] if msgs else 0

    def ping(self) -> tuple[bool, str]:
        try:
            r = requests.get(
                f"{self.config.grove_url}/channels",
                headers=self._headers(),
                timeout=TIMEOUT,
            )
            if r.status_code < 500:
                return True, f"grove reachable ({r.status_code})"
            return False, f"grove error {r.status_code}"
        except Exception as exc:
            return False, str(exc)
