#!/usr/bin/env python3
"""Loopback public demo server — chat UI + retrieval API (no Grove token required)."""

from __future__ import annotations

import http.server
import json
import os
import sys
import urllib.parse
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.public_demo import (  # noqa: E402
    apply_launcher_env,
    chat_retrieval,
    concierge_greeting,
    demo_banner,
    is_first_run,
)
from core.public_launcher_pg import host_port_open  # noqa: E402

# Grove defaults to 7777 — public chat uses 7788 to avoid colliding on dev machines.
DEFAULT_PUBLIC_PORT = 7788
PUBLIC_PORT_CANDIDATES = (7788, 7789, 7877, 8777, 8888)
DEFAULT_PORT = int(os.environ.get("WILLOW_PUBLIC_PORT", str(DEFAULT_PUBLIC_PORT)))
_MAX_BODY = 32_768

_PUBLIC_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Willow — local memory demo</title>
  <style>
    :root { font-family: system-ui, sans-serif; background: #0f1419; color: #e7ecf3; }
    body { max-width: 42rem; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.35rem; font-weight: 600; }
    .banner { background: #1a2a3a; border-left: 3px solid #5b9bd5; padding: 0.6rem 0.8rem;
              font-size: 0.85rem; margin: 1rem 0; color: #b8c5d6; }
    #log { min-height: 12rem; border: 1px solid #2a3544; border-radius: 8px;
           padding: 1rem; margin: 1rem 0; white-space: pre-wrap; line-height: 1.45; }
    form { display: flex; gap: 0.5rem; }
    input[type=text] { flex: 1; padding: 0.55rem 0.7rem; border-radius: 6px;
                        border: 1px solid #3a4556; background: #151b24; color: inherit; }
    button { padding: 0.55rem 1rem; border-radius: 6px; border: none;
             background: #3d7dd6; color: #fff; cursor: pointer; }
    button:disabled { opacity: 0.5; }
    .meta { font-size: 0.8rem; color: #8a97a8; margin-top: 1.5rem; }
  </style>
</head>
<body>
  <h1>Willow</h1>
  <p>Local-first memory — nothing leaves your machine.</p>
  <div class="banner" id="demo-banner"></div>
  <div id="log"></div>
  <form id="chat-form">
    <input type="text" id="q" placeholder="Ask Willow something…" autocomplete="off" />
    <button type="submit">Ask</button>
  </form>
  <p class="meta">Retrieval demo — no cloud. <a href="https://github.com/rudi193-cmd/willow-2.0/blob/master/TRUST.md" style="color:#7ab8ff">TRUST.md</a></p>
  <script>
    const log = document.getElementById('log');
    const banner = document.getElementById('demo-banner');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('q');
    banner.textContent = __BANNER__;
    log.textContent = __GREETING__;

    function append(role, text) {
      const prefix = role === 'you' ? '\\n\\nYou: ' : '\\n\\nWillow: ';
      log.textContent += prefix + text;
      log.scrollTop = log.scrollHeight;
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      input.value = '';
      append('you', q);
      const btn = form.querySelector('button');
      btn.disabled = true;
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q }),
        });
        const data = await res.json();
        append('willow', data.reply || data.error || '(no reply)');
      } catch (err) {
        append('willow', 'Could not reach Willow on this machine.');
      } finally {
        btn.disabled = false;
        input.focus();
      }
    });
    input.focus();
  </script>
</body>
</html>
"""


class PublicHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[public-serve] {self.address_string()} {fmt % args}", flush=True)

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            greeting = concierge_greeting(first_run=is_first_run())
            html = (
                _PUBLIC_HTML.replace("__BANNER__", json.dumps(demo_banner()))
                .replace("__GREETING__", json.dumps(greeting))
            )
            self._send_html(html)
            return
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok", "service": "public-serve"})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/chat":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > _MAX_BODY:
            self._send_json(413, {"error": "request too large"})
            return
        raw = self.rfile.read(min(length, _MAX_BODY))
        try:
            payload = json.loads(raw)
            query = (payload.get("query") or "").strip()
        except Exception:
            self._send_json(400, {"error": "invalid JSON"})
            return
        try:
            from core.pg_bridge import PgBridge

            bridge = PgBridge()
            try:
                result = chat_retrieval(bridge, query)
            finally:
                bridge.close()
            self._send_json(200, result)
        except Exception as exc:
            self._send_json(503, {
                "error": "database unavailable",
                "detail": str(exc),
                "reply": (
                    "I can't reach Postgres yet. Make sure Docker is running and "
                    "`docker compose up -d willow-db` succeeded."
                ),
            })


def pick_public_chat_port(
    *,
    preferred: int | None = None,
    explicit: bool = False,
) -> tuple[int, int | None]:
    """
    Choose a loopback port for the public chat server.

    Returns (port, skipped_busy_port). skipped is set when we fall back from preferred.
    """
    want = preferred if preferred is not None else DEFAULT_PUBLIC_PORT
    if not host_port_open("127.0.0.1", want):
        return want, None
    if explicit:
        raise OSError(f"Port {want} is already in use")
    for candidate in PUBLIC_PORT_CANDIDATES:
        if candidate == want:
            continue
        if not host_port_open("127.0.0.1", candidate):
            return candidate, want
    raise OSError("No free loopback port found for the public chat server")


def serve(host: str = "127.0.0.1", port: int | None = None) -> None:
    apply_launcher_env()
    os.environ.setdefault("WILLOW_CONFIG_MODE", "public-fallback")
    repo = _ROOT
    os.environ.setdefault("WILLOW_HOME", str(repo / ".willow" / "generated"))
    os.environ.setdefault("WILLOW_ROOT", str(repo))
    explicit = "WILLOW_PUBLIC_PORT" in os.environ and port is None
    if port is None:
        port, skipped = pick_public_chat_port(explicit=explicit)
        if skipped is not None:
            print(
                f"[public-serve] Port {skipped} is in use — listening on {port}",
                flush=True,
            )
    os.environ["WILLOW_PUBLIC_PORT"] = str(port)
    server = http.server.HTTPServer((host, port), PublicHandler)
    print(f"[public-serve] http://{host}:{port}/", flush=True)
    print(f"[public-serve] {demo_banner()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[public-serve] Stopped.", flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Willow public demo HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Loopback port (default: {DEFAULT_PUBLIC_PORT}, or next free)",
    )
    args = parser.parse_args()
    serve(args.host, args.port)
