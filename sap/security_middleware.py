"""HTTP transport guards for SAP MCP — stdio remains keyless by default."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = logging.getLogger(__name__)

WILLOW_MCP_API_KEY = os.environ.get("WILLOW_MCP_API_KEY", "").strip()
API_KEY_HEADER = "x-willow-key"


def api_key_configured() -> bool:
    return bool(WILLOW_MCP_API_KEY)


def check_api_key(request: Request) -> bool:
    """Return True when the request may proceed (stdio / unset key / valid header)."""
    if not api_key_configured():
        return True
    headers = getattr(request, "headers", None)
    if headers is None:
        return False
    return headers.get(API_KEY_HEADER, "") == WILLOW_MCP_API_KEY


def verify_transport(transport_type: str, *, host: str = "127.0.0.1") -> bool:
    """Warn when HTTP is exposed beyond loopback without an API key."""
    if transport_type != "http":
        return True
    if api_key_configured():
        return True
    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    if host in loopback_hosts:
        logger.warning(
            "MCP HTTP on %s without WILLOW_MCP_API_KEY — loopback only; "
            "set WILLOW_MCP_API_KEY before binding a public interface.",
            host,
        )
        return True
    logger.warning(
        "SECURITY WARNING: MCP Server running in HTTP mode on %s without "
        "WILLOW_MCP_API_KEY. Set the env var or bind to loopback only.",
        host,
    )
    return False


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not check_api_key(request):
            logger.warning("Security: blocked HTTP request with invalid API key")
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def wrap_streamable_http_app(app: Starlette) -> Starlette:
    """Insert API-key middleware when WILLOW_MCP_API_KEY is set."""
    if not api_key_configured():
        return app
    from starlette.applications import Starlette
    from starlette.middleware import Middleware

    middleware = [Middleware(ApiKeyMiddleware), *list(app.user_middleware)]
    return Starlette(
        debug=app.debug,
        routes=app.routes,
        middleware=middleware,
        exception_handlers=app.exception_handlers,
        lifespan=app.router.lifespan_context,
    )
