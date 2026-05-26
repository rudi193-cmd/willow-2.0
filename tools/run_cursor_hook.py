#!/usr/bin/env python3
"""Legacy shim — prefer willow.fylgja.hook_runner or fylgja-hook."""
from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: run_cursor_hook.py <python.module.to.run>", file=sys.stderr)
        sys.exit(2)
    sys.argv = [sys.argv[0], "--format", "cursor", sys.argv[1]]
    from willow.fylgja.hook_runner import main as hook_main

    hook_main()


if __name__ == "__main__":
    main()
