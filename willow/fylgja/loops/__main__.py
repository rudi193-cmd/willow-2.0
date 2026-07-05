from __future__ import annotations

import argparse
import json

from willow.fylgja.loops.registry import recount, sync_seed_to_soil, validate_registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Loop registry validator (ADR-20260705)")
    ap.add_argument("--validate", action="store_true", help="validate seed + SOIL overlay")
    ap.add_argument("--recount", action="store_true", help="registry vs systemd/hook reality")
    ap.add_argument("--sync-soil", action="store_true", help="mirror seed JSON into SOIL")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not (args.validate or args.recount or args.sync_soil):
        args.validate = True
        args.recount = True

    out: dict = {}
    exit_code = 0
    if args.sync_soil:
        out["synced"] = sync_seed_to_soil()
    if args.validate:
        problems = validate_registry()
        out["validation"] = {"ok": not problems, "problems": problems}
        if problems:
            exit_code = 1
    if args.recount:
        out["recount"] = recount()
        if not out["recount"].get("ok"):
            exit_code = 1

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps(out, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
