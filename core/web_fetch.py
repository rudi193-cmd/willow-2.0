"""Guarded HTTP fetch for agents — external-guard scan + sandwich wrap."""

from __future__ import annotations

import html
import ipaddress
import logging
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

log = logging.getLogger("willow.web_fetch")

_USER_AGENT = "Mozilla/5.0 (compatible; Willow/2.0; +https://github.com/rudi193-cmd/willow-2.0)"
_DEFAULT_MAX_BYTES = 512_000
_DEFAULT_MAX_CHARS = 80_000
_TAG_RE = re.compile(r"<[^>]+>")

_GUARD_SCRIPTS = (
    Path(__file__).resolve().parent.parent / "willow" / "fylgja" / "skills" / "scripts"
)


def _guard_modules():
    scripts = str(_GUARD_SCRIPTS)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from guard import SANDWICH_TEMPLATE, scan, verdict  # type: ignore import-not-found

    return scan, verdict, SANDWICH_TEMPLATE


def _strip_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or ""))


def _is_blocked_host(hostname: str) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return True
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return bool(
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        )
    except ValueError:
        pass
    if host.endswith(".local") or host.endswith(".internal"):
        return True
    return False


def validate_fetch_url(url: str) -> str | None:
    """Return error string if URL is not allowed, else None."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return f"unsupported scheme: {parsed.scheme!r} (http/https only)"
    if not parsed.netloc:
        return "missing hostname"
    if _is_blocked_host(parsed.hostname or ""):
        return f"blocked host: {parsed.hostname}"
    return None


def fetch_url(
    url: str,
    *,
    wrap: bool = True,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    max_chars: int = _DEFAULT_MAX_CHARS,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Fetch URL body with size limits, guard scan, optional sandwich wrap."""
    err = validate_fetch_url(url)
    if err:
        return {"ok": False, "url": url, "error": err}

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        log.warning("fetch failed %s: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc)}

    raw = resp.content[:max_bytes]
    charset = resp.encoding or "utf-8"
    try:
        text = raw.decode(charset, errors="replace")
    except Exception:
        text = raw.decode("utf-8", errors="replace")

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "html" in content_type or text.lstrip().startswith("<"):
        text = _strip_html(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "…"

    scan, guard_verdict, sandwich = _guard_modules()
    hits = scan(text)
    guard = guard_verdict(hits)
    if guard == "BLOCKED":
        label = hits[0]["label"] if hits else "injection pattern"
        return {
            "ok": False,
            "url": url,
            "status_code": resp.status_code,
            "guard": guard,
            "guard_hits": hits,
            "error": f"external-guard BLOCKED: {label}",
        }

    body = sandwich.format(content=text) if wrap else text
    return {
        "ok": True,
        "url": url,
        "final_url": str(resp.url),
        "status_code": resp.status_code,
        "content_type": content_type,
        "guard": guard,
        "guard_hits": hits,
        "chars": len(text),
        "content": body,
        "wrapped": wrap,
    }
