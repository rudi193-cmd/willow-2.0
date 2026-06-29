"""willow_external facade — fetch mode."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch


def test_willow_external_fetch_delegates():
    from sap import sap_mcp

    async def _run():
        with patch.object(sap_mcp, "willow_web_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"ok": True, "url": "https://example.com", "content": "hi"}
            out = await sap_mcp.willow_external(
                app_id="willow",
                mode="fetch",
                url="https://example.com",
            )
        mock_fetch.assert_awaited_once()
        assert out["facade"] == "willow_external"
        assert out["backend"] == "willow_web_fetch"
        assert out["result"]["ok"] is True

    asyncio.run(_run())
