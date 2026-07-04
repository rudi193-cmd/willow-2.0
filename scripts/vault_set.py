#!/usr/bin/env python3
"""Interactively write a secret into the credential vault that
sap/core/inference.load_credential actually reads (secrets/.willow_creds.db +
secrets/.willow_master.key — see tests/test_vault_path_sync.py). Does not
touch shell history, Kart logs, or a chat transcript. Run directly by a human:

    .venv-dev/bin/python3 scripts/vault_set.py GH_TOKEN
    .venv-dev/bin/python3 scripts/vault_set.py DISCORD_BOT_TOKEN
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import shoot  # noqa: E402
from sap.core import inference  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <SECRET_NAME>", file=sys.stderr)
        sys.exit(1)

    name = sys.argv[1]
    try:
        value = getpass.getpass(f"Value for {name} (input hidden): ").strip()
    except Exception:
        value = ""
    if not value:
        print("(hidden input failed or empty — falling back to visible paste)")
        value = input(f"Value for {name} (visible, paste ok): ").strip()
    if not value:
        print("empty value, aborting", file=sys.stderr)
        sys.exit(1)

    if not shoot._vault_init():
        print("vault init failed", file=sys.stderr)
        sys.exit(1)
    if not shoot._vault_write(name, name, value):
        print("vault write failed", file=sys.stderr)
        sys.exit(1)

    # Round-trip through the real reader to prove it actually works.
    readback = inference.load_credential(name)
    if readback == value:
        print(f"{name} written and verified via load_credential().")
    else:
        print(f"{name} written but load_credential() round-trip did NOT match — investigate.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
