#!/usr/bin/env python3
"""
ratatosk-termux — phone endpoint for the Ratatosk local app suite.

Usage:
  python main.py                    # terminal UI, Ollama
  python main.py --gui              # Termux:GUI UI
  python main.py --listen           # Grove dispatch listener
  python main.py --doctor           # health check
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

# Parent package (apps/ratatosk)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ratatosk import ollama  # noqa: E402
from ratatosk.doctor import run_doctor  # noqa: E402
from ratatosk.protocol.envelope import Intent, build_envelope, parse_grove_message, validate_envelope  # noqa: E402
from ratatosk.session import Session  # noqa: E402
from ratatosk.traces import log_trace  # noqa: E402
from ratatosk.transport.grove_client import GroveClient  # noqa: E402
from ui.terminal import TerminalUI  # noqa: E402


def get_ui(args):
    if args.gui:
        from ui.tgui import TermuxGUI

        return TermuxGUI(node_name=args.node, model=args.model)
    return TerminalUI(node_name=args.node, model=args.model)


def run_repl(ui, sess, args):
    grove = GroveClient()
    ui.start()
    ui.status(f"ollama {'available' if ollama.is_available() else 'UNAVAILABLE'}")
    ui.status(f"transport {grove.config.mode} → {grove.config.grove_url or 'unset'}")

    while True:
        try:
            text = ui.prompt()
        except KeyboardInterrupt:
            break
        if not text:
            continue
        if text.lower() in ("exit", "quit", "/exit", "/quit"):
            break
        if text.startswith("/model "):
            args.model = text.split(None, 1)[1].strip()
            ui.status(f"model → {args.model}")
            continue
        if text == "/history":
            for m in sess.messages:
                ui.display(f"[{m['role']}] {m['content']}", role="system")
            continue
        if text == "/models":
            models = ollama.list_models()
            ui.display(", ".join(models) if models else "none found", role="system")
            continue
        if text in ("/status", "/doctor"):
            report = run_doctor()
            ui.display(json.dumps(report.to_dict(), indent=2), role="system")
            continue
        if text.startswith("/send "):
            prompt = text.split(None, 1)[1].strip()
            env = build_envelope(
                to="ratatosk",
                prompt=prompt,
                from_agent=args.node,
                intent=Intent.CHAT.value,
                reply_channel="general",
            )
            grove.post_envelope("dispatch", env, sender=args.node)
            ui.status(f"sent desktop trace={env.trace_id}")
            continue

        sess.user(text)
        try:
            if args.stream:
                ui.stream_start()
                tokens = []
                for token in ollama.generate_stream(text, model=args.model):
                    ui.stream_token(token)
                    tokens.append(token)
                ui.stream_end()
                response = "".join(tokens)
            else:
                response = ollama.generate(text, model=args.model, stream=False)
                ui.display(response)
            sess.assistant(response)
        except Exception as exc:
            ui.display(str(exc), role="error")

    sess.close()
    ui.stop()


def run_listener(ui, args):
    grove = GroveClient()
    ui.start()
    ui.status(f"listening on {args.grove_channel} as {args.node}")
    cursor = grove.tail_cursor(args.grove_channel)
    ui.status(f"cursor={cursor} — ready")

    def handle(msg):
        env = parse_grove_message(msg, default_node=args.node)
        if not env:
            return
        validation = validate_envelope(env, node=args.node)
        if not validation.ok:
            ui.display(f"rejected: {validation.errors}", role="error")
            return
        ui.status(f"← {env.sender or env.from_agent}: {env.prompt[:60]}")
        log_trace(env.trace_id, "phone_received", {"intent": env.intent})
        sess = Session(model=args.model, node=args.node)
        sess.user(env.prompt)
        try:
            if env.intent in {Intent.OPEN_STATUS.value}:
                ok, detail = grove.ping()
                response = f"status grove={'up' if ok else 'down'} {detail}"
            else:
                response = ollama.generate(env.prompt, model=args.model, stream=False)
            sess.assistant(response)
            grove.post(env.reply_channel, response, sender=args.node)
            log_trace(env.trace_id, "phone_replied", {"channel": env.reply_channel})
            ui.status(f"→ {env.reply_channel}: {response[:60]}")
        except Exception as exc:
            err = f"[{args.node}] error: {exc}"
            grove.post(env.reply_channel, err, sender=args.node)
            ui.display(err, role="error")
        finally:
            sess.close()

    while True:
        try:
            msgs = grove.get_history(args.grove_channel, since_id=cursor)
            for msg in msgs:
                cursor = max(cursor, msg.get("id", 0))
                threading.Thread(target=handle, args=(msg,), daemon=True).start()
        except Exception as exc:
            ui.display(f"poll error: {exc}", role="error")
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="ratatosk-termux")
    parser.add_argument("--gui", action="store_true", help="Use Termux:GUI")
    parser.add_argument("--listen", action="store_true", help="Grove listener mode")
    parser.add_argument("--doctor", action="store_true", help="Run health check and exit")
    parser.add_argument("--node", default=os.environ.get("WILLOW_AGENT_NAME", "ratatosk"))
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "llama3.2:1b"))
    parser.add_argument("--grove-channel", default="dispatch", dest="grove_channel")
    parser.add_argument("--no-stream", action="store_false", dest="stream")
    parser.set_defaults(stream=True)
    args = parser.parse_args()

    if args.doctor:
        print(json.dumps(run_doctor().to_dict(), indent=2))
        return

    ui = get_ui(args)
    sess = Session(model=args.model, node=args.node)

    if args.listen:
        run_listener(ui, args)
    else:
        run_repl(ui, sess, args)


if __name__ == "__main__":
    main()
