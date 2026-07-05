#!/usr/bin/env python3
"""Generic lane-4 harness runner — stdlib only.

Loads a harness directory (prompt.md, schema.json, fewshot.json,
fixtures.jsonl, harness.json), drives Ollama structured outputs, validates
the semantic checks a schema cannot express, and prints a per-fixture
receipt. Exit code is the verifier: nonzero when any required check fails.

Containment doctrine: harnesses declared verify_class=containment can never
"pass" — their best score is CONTAINED, meaning safe to queue for review.
The runner is the enforcement point, not the prompt.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
PASS, CONTAINED, FAIL = "PASS", "CONTAINED", "FAIL"


def load_harness(harness_dir: Path) -> dict:
    meta = json.loads((harness_dir / "harness.json").read_text())
    return {
        "meta": meta,
        "prompt": (harness_dir / "prompt.md").read_text(),
        "schema": json.loads((harness_dir / "schema.json").read_text()),
        "fewshot": json.loads((harness_dir / "fewshot.json").read_text()),
        "fixtures": [
            json.loads(line)
            for line in (harness_dir / "fixtures.jsonl").read_text().splitlines()
            if line.strip()
        ],
    }


def build_messages(harness: dict, user_input: str) -> list[dict]:
    messages = [{"role": "system", "content": harness["prompt"]}]
    for shot in harness["fewshot"]:
        messages.append({"role": "user", "content": shot["input"]})
        messages.append(
            {"role": "assistant", "content": json.dumps(shot["output"], ensure_ascii=False)}
        )
    messages.append({"role": "user", "content": user_input})
    return messages


def call_ollama(model: str, messages: list[dict], schema: dict, options: dict,
                timeout: float = 300.0) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "options": options,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return json.loads(body["message"]["content"])


# ── Checks: the semantic residue a schema can't express ──────────────────────
#
# Every check is a pure predicate over (output, check_arg, raw_input).
# Adding a harness never means adding runner code unless a genuinely new
# predicate shape appears.

def _get_path(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
    return cur


def check_contains(output, arg, _inp):
    """arg: {"path": "title", "any": [..]} — field must contain one substring."""
    val = str(_get_path(output, arg["path"]) or "")
    needles = arg.get("any") or [arg["value"]]
    return any(n.lower() in val.lower() for n in needles)


def check_not_contains(output, arg, _inp):
    val = json.dumps(output, ensure_ascii=False).lower()
    return not any(n.lower() in val for n in arg["values"])


def check_grounded(output, arg, inp):
    """Every value at path must appear verbatim in the input (anti-hallucination)."""
    vals = _get_path(output, arg["path"]) or []
    if not isinstance(vals, list):
        vals = [vals]
    return all(str(v) in inp for v in vals)


def check_max_len(output, arg, _inp):
    val = str(_get_path(output, arg["path"]) or "")
    return len(val) <= arg["chars"]


def check_regex(output, arg, _inp):
    val = str(_get_path(output, arg["path"]) or "")
    return re.search(arg["pattern"], val) is not None


def check_enum(output, arg, _inp):
    return _get_path(output, arg["path"]) in arg["values"]


CHECKS = {
    "contains": check_contains,
    "not_contains": check_not_contains,
    "grounded": check_grounded,
    "max_len": check_max_len,
    "regex": check_regex,
    "enum": check_enum,
}


def run_fixture(harness: dict, fixture: dict, model: str, options: dict) -> tuple[str, list[str]]:
    raw_input = fixture["input"] if isinstance(fixture["input"], str) else json.dumps(
        fixture["input"], ensure_ascii=False
    )
    try:
        output = call_ollama(
            model, build_messages(harness, raw_input), harness["schema"], options
        )
    except Exception as exc:  # noqa: BLE001 — a dead model is a FAIL, not a crash
        return FAIL, [f"generation error: {exc}"]

    failures = []
    for check in fixture.get("checks", []):
        fn = CHECKS.get(check["kind"])
        if fn is None:
            failures.append(f"unknown check kind {check['kind']!r}")
            continue
        try:
            ok = fn(output, check, raw_input)
        except Exception as exc:  # noqa: BLE001
            ok = False
            failures.append(f"{check['kind']}({check.get('path', '?')}) errored: {exc}")
            continue
        if not ok:
            failures.append(f"{check['kind']}({check.get('path', check.get('values', '?'))})")

    if failures:
        return FAIL, failures
    if harness["meta"]["verify_class"] == "containment":
        return CONTAINED, []
    return PASS, []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("harness_dir", type=Path)
    ap.add_argument("--model", default=None, help="override harness.json model")
    ap.add_argument("--repeat", type=int, default=1, help="runs per fixture (envelope mode)")
    ap.add_argument("--fixture", type=int, default=None, help="run only fixture N (0-based)")
    args = ap.parse_args()

    harness = load_harness(args.harness_dir)
    meta = harness["meta"]
    model = args.model or meta["model"]
    options = meta.get("options", {"temperature": 0})

    fixtures = harness["fixtures"]
    if args.fixture is not None:
        fixtures = [fixtures[args.fixture]]

    total = passed = contained = failed = 0
    for i, fixture in enumerate(fixtures):
        for rep in range(args.repeat):
            total += 1
            verdict, failures = run_fixture(harness, fixture, model, options)
            tag = f"[{meta['name']}#{i}" + (f" r{rep}" if args.repeat > 1 else "") + "]"
            if verdict == PASS:
                passed += 1
                print(f"{tag} PASS")
            elif verdict == CONTAINED:
                contained += 1
                print(f"{tag} CONTAINED (verify_class=containment → review queue)")
            else:
                failed += 1
                print(f"{tag} FAIL: {'; '.join(failures)}")

    print(
        f"\n{meta['name']} @ {model}: {passed} pass, {contained} contained, "
        f"{failed} fail / {total} runs"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
