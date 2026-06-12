"""Ratatosk suite CLI — doctor, listen, explain, panic."""
from __future__ import annotations

import argparse
import json
import sys

from ratatosk.doctor import clear_panic, explain, panic, run_doctor
from ratatosk.listener import DesktopListener


def _cmd_doctor(_args: argparse.Namespace) -> int:
    report = run_doctor()
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.ok else 1


def _cmd_listen(args: argparse.Namespace) -> int:
    listener = DesktopListener(channel=args.channel, node=args.node)
    if args.once:
        for result in listener.run_once():
            print(result)
        return 0

    def status(msg: str) -> None:
        print(f"· {msg}", flush=True)

    listener.run_forever(on_status=status)
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    print(json.dumps(explain(args.trace_id), indent=2))
    return 0


def _cmd_panic(args: argparse.Namespace) -> int:
    if args.clear:
        clear_panic()
        print(json.dumps({"panic": False, "cleared": True}))
        return 0
    print(json.dumps(panic(args.note), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ratatosk", description="Ratatosk local app suite")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Health checks for transport, grove, ollama, tailscale")
    p_doc.set_defaults(func=_cmd_doctor)

    p_listen = sub.add_parser("listen", help="Desktop Grove listener (capability-gated)")
    p_listen.add_argument("--channel", default="dispatch")
    p_listen.add_argument("--node", default=None)
    p_listen.add_argument("--once", action="store_true", help="Poll once and exit")
    p_listen.set_defaults(func=_cmd_listen)

    p_explain = sub.add_parser("explain", help="Explain a trace_id")
    p_explain.add_argument("trace_id")
    p_explain.set_defaults(func=_cmd_explain)

    p_panic = sub.add_parser("panic", help="Emergency stop — revoke exposure and halt listeners")
    p_panic.add_argument("--note", default="operator panic")
    p_panic.add_argument("--clear", action="store_true", help="Clear panic state")
    p_panic.set_defaults(func=_cmd_panic)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
