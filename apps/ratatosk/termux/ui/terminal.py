"""Plain terminal UI — readline REPL with color."""

import readline  # noqa: F401

from .base import BaseUI

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GRAY = "\033[90m"


class TerminalUI(BaseUI):
    def __init__(self, node_name: str = "ratatosk", model: str | None = None):
        self.node_name = node_name
        self.model = model or "llama3.2:1b"

    def start(self):
        print(f"{BOLD}{CYAN}ratatosk-termux{RESET}  {DIM}node={self.node_name}  model={self.model}{RESET}")
        print(
            f"{DIM}exit | /model NAME | /history | /models | /status | /doctor{RESET}\n"
        )

    def prompt(self) -> str:
        try:
            return input(f"{GREEN}you{RESET} › ").strip()
        except EOFError:
            return "exit"

    def display(self, text: str, role: str = "assistant"):
        if role == "assistant":
            print(f"\n{CYAN}{self.node_name}{RESET} › {text}\n")
        elif role == "system":
            print(f"{YELLOW}[system]{RESET} {text}")
        elif role == "error":
            print(f"{RED}[error]{RESET} {text}")
        else:
            print(text)

    def stream_start(self):
        print(f"\n{CYAN}{self.node_name}{RESET} › ", end="", flush=True)

    def stream_token(self, token: str):
        print(token, end="", flush=True)

    def stream_end(self):
        print("\n", flush=True)

    def status(self, text: str):
        print(f"{GRAY}· {text}{RESET}")

    def stop(self):
        print(f"\n{DIM}session ended.{RESET}")
