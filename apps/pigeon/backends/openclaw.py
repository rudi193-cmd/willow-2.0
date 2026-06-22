"""
OpenClaw backend for Pigeon.
b17: 1284BC7D  ΔΣ=42

Lists active OpenClaw sessions as threads.
Send via openclaw_send MCP tool.

TODO: wire send path via MCP client subprocess.
"""
from __future__ import annotations
from apps.pigeon.backends.base import MailBackend


class OpenClawBackend(MailBackend):
    def list_threads(self) -> list[dict]:
        # TODO: call openclaw_sessions via MCP subprocess
        return [
            {
                "id":      "stub-oc-1",
                "from":    "openclaw (not yet wired)",
                "subject": "MCP client required",
                "date":    "",
                "snippet": "Wire MCP subprocess client to list live sessions.",
            }
        ]

    def get_thread(self, thread_id: str) -> str:
        return (
            "[bold]OpenClaw not yet wired.[/bold]\n\n"
            "Next session: add MCP subprocess client and replace this stub."
        )
