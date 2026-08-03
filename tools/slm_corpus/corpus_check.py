#!/usr/bin/env python3
"""corpus_check.py — the corpus witness (redaction, path guard, data lint).

harvest.py transforms; this gate ratifies. The two never share a hand (§0.2):
harvest redacts on the way in, and corpus_check independently sweeps the
FINISHED corpus — so a redaction miss, a path leak, or a malformed record is
detected by a second pair of eyes, not assumed away because the builder ran.

Check families, over every record in the corpus dir:

  secrets — secret-shaped strings in any string field. The pattern set is a
            SUPERSET of harvest's _SECRET_PATTERNS (imported, then extended),
            so the witness can catch what the builder's own list misses.
            Findings are reported MASKED: the receipt must never itself
            become the leak.
  paths   — user-identifying filesystem paths in record content: the
            path_guard.sh discipline applied to data instead of tracked
            code. /home/<user>, /Users/<user>, C:\\Users\\<user> FAIL
            (username exposure in a training set); tilde-rooted personal
            dirs WARN. --allow-user exempts named benign users (e.g.
            "runner" from CI transcripts).
  lint    — structure: every line parses (a bad line is an ERROR here even
            though assemble.py silently skips it — witness, not builder),
            required fields per file kind, id uniqueness, known task_types,
            gold/SFT outputs pass templates.validate_output and are in
            canonical form, DPO chosen/rejected shape, and sft_train /
            sft_val disjointness.

The corpus is private operator data and never enters CI. The GATE is proven
in CI instead: tests/test_corpus_check.py builds synthetic corpora with
planted violations and asserts every family catches its class. The real run
happens where the corpus lives:

    python3 tools/slm_corpus/corpus_check.py --strict --receipt receipt.json

The receipt carries counts, verdicts, and a corpus fingerprint — no content.

Verdicts:
  ERROR — the corpus is lying to someone (leak, malformed, contract breach).
  WARN  — rough edge worth eyes (tilde path, empty file, thin task).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.slm_corpus.harvest import _SECRET_PATTERNS  # noqa: E402
from tools.slm_corpus.templates import (  # noqa: E402
    TASK_TYPES,
    canonicalize_output,
    validate_output,
)

# Witness-only additions — classes harvest's own list does not cover.
_EXTRA_SECRET_PATTERNS = [
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-secret-key", re.compile(
        r"(?i)aws.{0,20}(secret|sk).{0,20}['\"][A-Za-z0-9/+=]{40}['\"]")),
    ("slack-webhook", re.compile(
        r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+")),
    ("connection-string", re.compile(
        r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s/@]+:[^\s@]+@")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("bearer-header", re.compile(r"(?i)\bauthorization:\s*bearer\s+[A-Za-z0-9._\-]{16,}")),
]
_ALL_SECRET_PATTERNS = [
    (f"harvest-{i}", pat) for i, pat in enumerate(_SECRET_PATTERNS)
] + _EXTRA_SECRET_PATTERNS

_USER_PATH = re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\+Users\\+)([A-Za-z0-9._-]+)")
_TILDE_PATH = re.compile(r"~/(?:Desktop|Documents|Downloads|\.willow|\.ssh|\.gnupg)\b")


def _mask(value: str) -> str:
    """Show enough to locate the finding, never enough to re-leak it."""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}…{value[-2:]} ({len(value)} chars)"


def _string_leaves(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _string_leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _string_leaves(v, f"{path}[{i}]")


def _read_jsonl_strict(path: Path, errors: list[str]) -> list[tuple[int, dict]]:
    """Unlike assemble._read_jsonl, a bad line is an ERROR, not a silent skip."""
    out: list[tuple[int, dict]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{n}: unparseable JSONL line ({exc.msg})")
            continue
        if not isinstance(rec, dict):
            errors.append(f"{path.name}:{n}: record is not an object")
            continue
        out.append((n, rec))
    return out


class Witness:
    def __init__(self, corpus: Path, allow_users: set[str]):
        self.corpus = corpus
        self.allow_users = allow_users
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.counts: dict[str, int] = {"files": 0, "records": 0}
        self.visited: set[Path] = set()

    # ── families ──────────────────────────────────────────────────────────

    def sweep_secrets(self, where: str, rid: str, rec: dict) -> None:
        for field, text in _string_leaves(rec):
            for name, pat in _ALL_SECRET_PATTERNS:
                for m in pat.finditer(text):
                    if "[REDACTED]" in m.group(0):
                        continue
                    self.errors.append(
                        f"{where} id={rid} field={field}: secret-shaped "
                        f"[{name}] {_mask(m.group(0))}"
                    )

    def sweep_paths(self, where: str, rid: str, rec: dict) -> None:
        for field, text in _string_leaves(rec):
            for m in _USER_PATH.finditer(text):
                user = m.group(1)
                if user in self.allow_users:
                    continue
                self.errors.append(
                    f"{where} id={rid} field={field}: user-identifying path "
                    f"exposes username {user!r}"
                )
            if _TILDE_PATH.search(text):
                self.warnings.append(
                    f"{where} id={rid} field={field}: personal tilde path"
                )

    # ── file kinds ────────────────────────────────────────────────────────

    def _records(self, path: Path, required: tuple[str, ...]) -> list[tuple[int, dict]]:
        self.visited.add(path.resolve())
        self.counts["files"] += 1
        recs = _read_jsonl_strict(path, self.errors)
        seen: set[str] = set()
        for n, rec in recs:
            self.counts["records"] += 1
            for field in required:
                if field not in rec:
                    self.errors.append(f"{path.name}:{n}: missing field {field!r}")
            rid = rec.get("id") or rec.get("meta", {}).get("id") or f"line{n}"
            if rid in seen:
                self.errors.append(f"{path.name}:{n}: duplicate id {rid!r}")
            seen.add(rid)
            self.sweep_secrets(path.name, rid, rec)
            self.sweep_paths(path.name, rid, rec)
        if not recs:
            self.warnings.append(f"{path.name}: no records")
        return recs

    def check_inputs(self) -> dict[str, str]:
        """Returns id -> task_type for cross-file contract checks."""
        path = self.corpus / "inputs.jsonl"
        tasks: dict[str, str] = {}
        if not path.exists():
            self.warnings.append("inputs.jsonl: absent")
            return tasks
        for n, rec in self._records(path, ("id", "task_type", "payload")):
            tt = rec.get("task_type")
            if tt and tt not in TASK_TYPES:
                self.errors.append(f"inputs.jsonl:{n}: unknown task_type {tt!r}")
            if rec.get("id"):
                tasks[rec["id"]] = tt or ""
        return tasks

    def check_outputs_dir(self, name: str, tasks: dict[str, str]) -> None:
        d = self.corpus / name
        if not d.is_dir():
            self.warnings.append(f"{name}/: absent")
            return
        required = ("id", "output") if name == "gold" else ("id", "output", "model")
        for path in sorted(d.glob("*.jsonl")):
            for n, rec in self._records(path, required):
                rid, out = rec.get("id"), rec.get("output")
                if not (rid and isinstance(out, str)):
                    continue
                tt = tasks.get(rid)
                if tt is None:
                    self.errors.append(
                        f"{name}/{path.name}:{n}: id {rid!r} has no harvested input")
                elif name == "gold" and tt:
                    ok, why = validate_output(tt, {"categories": []}, out)
                    if not ok:
                        self.errors.append(
                            f"{name}/{path.name}:{n}: id {rid!r} fails the "
                            f"{tt} contract ({why})")

    def check_sft(self) -> None:
        seen: dict[str, str] = {}
        for name in ("sft_train.jsonl", "sft_val.jsonl"):
            path = self.corpus / name
            if not path.exists():
                self.warnings.append(f"{name}: absent")
                continue
            for n, rec in self._records(path, ("messages", "meta")):
                meta = rec.get("meta") or {}
                rid, tt = meta.get("id"), meta.get("task_type")
                msgs = rec.get("messages")
                if not (isinstance(msgs, list) and msgs
                        and msgs[-1].get("role") == "assistant"):
                    self.errors.append(
                        f"{name}:{n}: messages must end with an assistant turn")
                    continue
                if rid:
                    if rid in seen and seen[rid] != name:
                        self.errors.append(
                            f"{name}:{n}: id {rid!r} appears in both train and "
                            f"val — the split leaks")
                    seen[rid] = name
                gold = msgs[-1].get("content", "")
                if tt in TASK_TYPES and gold != canonicalize_output(tt, gold):
                    self.errors.append(
                        f"{name}:{n}: id {rid!r} assistant content is not in "
                        f"canonical form for {tt}")

    def check_dpo(self) -> None:
        path = self.corpus / "dpo.jsonl"
        if not path.exists():
            self.warnings.append("dpo.jsonl: absent")
            return
        for n, rec in self._records(path, ("messages", "chosen", "rejected", "meta")):
            if rec.get("chosen") == rec.get("rejected"):
                self.errors.append(
                    f"dpo.jsonl:{n}: chosen == rejected — the pair teaches nothing")

    # ── driver ────────────────────────────────────────────────────────────

    def check_unknown_files(self) -> None:
        """Data the layout doesn't name is still data: leak-sweep it anyway.

        The fingerprint hashes every *.jsonl recursively; witnessing fewer
        files than it fingerprints would be a blind spot (found in the field:
        a corpus dir whose only jsonl lived outside the canonical names
        fingerprinted as non-empty while the witness saw nothing).
        """
        for path in sorted(self.corpus.rglob("*.jsonl")):
            if path.resolve() in self.visited:
                continue
            self.warnings.append(
                f"{path.relative_to(self.corpus)}: unrecognized corpus file — "
                f"leak-swept only, no schema lint")
            self._records(path, ())

    def run(self) -> None:
        tasks = self.check_inputs()
        self.check_outputs_dir("gold", tasks)
        self.check_outputs_dir("baseline", tasks)
        self.check_sft()
        self.check_dpo()
        self.check_unknown_files()

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for path in sorted(self.corpus.rglob("*.jsonl")):
            h.update(path.name.encode())
            h.update(hashlib.sha256(path.read_bytes()).digest())
        return h.hexdigest()[:16]

    def receipt(self) -> dict:
        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "corpus_fingerprint": self.fingerprint(),
            "files": self.counts["files"],
            "records": self.counts["records"],
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "verdict": "FAIL" if self.errors else "PASS",
        }


def _resolve_dir(cli: str, env: str | None) -> Path:
    """--dir, else the env var, else harvest's own resolution.

    Field bug this replaces: Path("") stringifies to "." — the old falsy
    check never fired and the witness silently scanned the CURRENT
    DIRECTORY (the repo checkout, whose own jsonl files produced a stable,
    baffling fingerprint) instead of the corpus.
    """
    if cli:
        return Path(cli).expanduser()
    if env:
        return Path(env).expanduser()
    from tools.slm_corpus.harvest import corpus_dir
    return corpus_dir()


def main() -> int:
    ap = argparse.ArgumentParser(description="SLM corpus witness")
    ap.add_argument("--dir", default="", help="corpus dir (default: WILLOW_SLM_CORPUS_DIR)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any ERROR")
    ap.add_argument("--receipt", default="", help="write a content-free JSON receipt here")
    ap.add_argument("--allow-user", action="append", default=[],
                    help="benign path username to exempt (repeatable), e.g. runner")
    args = ap.parse_args()

    corpus = _resolve_dir(args.dir, os.environ.get("WILLOW_SLM_CORPUS_DIR"))
    if not corpus.is_dir():
        print(f"corpus dir not found: {corpus}", file=sys.stderr)
        return 2
    print(f"witnessing: {corpus}")

    w = Witness(corpus, set(args.allow_user))
    w.run()

    for e in w.errors:
        print(f"❌ ERROR {e}")
    for warning in w.warnings:
        print(f"⚠️  WARN  {warning}")
    r = w.receipt()
    print(f"\ncorpus witness: {r['records']} records in {r['files']} files · "
          f"{r['errors']} error(s) · {r['warnings']} warning(s) · "
          f"fingerprint {r['corpus_fingerprint']} · {r['verdict']}")

    if args.receipt:
        Path(args.receipt).write_text(json.dumps(r, indent=2) + "\n")

    return 1 if (args.strict and w.errors) else 0


if __name__ == "__main__":
    sys.exit(main())
