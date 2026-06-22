"""
Gmail backend for Pigeon.
b17: 1284BC7D  ΔΣ=42

Reads via Willow MCP Gmail tools (mcp__claude_ai_Gmail__*).
OAuth is handled by the MCP layer — no token management here.

TODO (next session): wire send via create_draft + label_thread SENT.
"""
from __future__ import annotations
from apps.pigeon.backends.base import MailBackend


class GmailBackend(MailBackend):
    def list_threads(self) -> list[dict]:
        # TODO: call willow MCP gmail search_threads via subprocess/MCP client
        # Stub returns placeholder until OAuth session is wired.
        return [
            {
                "id":      "stub-gmail-1",
                "from":    "gmail (not yet wired)",
                "subject": "OAuth session required",
                "date":    "",
                "snippet": "Wire CLOUDFLARE_API_TOKEN and Gmail OAuth to activate.",
            }
        ]

    def get_thread(self, thread_id: str) -> str:
        return (
            "[bold]Gmail OAuth not yet wired.[/bold]\n\n"
            "Next session: authenticate via MCP Gmail tools and replace this stub."
        )
