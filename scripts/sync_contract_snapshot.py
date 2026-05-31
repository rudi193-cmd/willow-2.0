#!/usr/bin/env python3
"""Generate docs/CONTRACT.md from private willow.md (willow-config).

Run from repo root after editing the fleet contract:

    python3 scripts/sync_contract_snapshot.py

Source resolution order:
  1. WILLOW_HOME/willow.md
  2. ~/github/.willow/willow.md
  3. repo willow.md (symlink OK)
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "docs" / "CONTRACT.md"

# Headings copied verbatim from willow.md (public-safe sections only).
SECTION_HEADINGS = (
    "## Glossary",
    "## Constraints",
    "## Boot sequence",
    "## Knowledge architecture",
    "## Tool groups (SAP MCP)",
    "## Agent model",
    "## Git workflow",
    "## Execution discipline — no dogfooding",
    "## Fleet path truth (ThinkPad)",
    "## Canonical principle",
)


def _resolve_willow_md() -> Path | None:
    env_home = os.environ.get("WILLOW_HOME", "").strip()
    candidates = [
        Path(env_home) / "willow.md" if env_home else None,
        Path.home() / "github" / ".willow" / "willow.md",
        REPO_ROOT / "willow.md",
    ]
    for path in candidates:
        if path and path.is_file():
            return path.resolve()
    return None


def _extract_sections(text: str, headings: tuple[str, ...]) -> str:
    positions: list[tuple[int, str]] = []
    for heading in headings:
        idx = text.find(heading)
        if idx >= 0:
            positions.append((idx, heading))
    if not positions:
        return ""
    positions.sort(key=lambda x: x[0])
    chunks: list[str] = []
    for i, (start, heading) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        chunks.append(text[start:end].rstrip())
    return "\n\n".join(chunks).strip()


def _fix_repo_root_links(text: str) -> str:
    """CONTRACT.md lives in docs/ — rewrite repo-root relative links to ../ paths."""
    import re

    def repl(m: re.Match[str]) -> str:
        target = m.group(1)
        if target.startswith(("../", "http", "mailto", "#", "/")):
            return m.group(0)
        return f"](../{target})"

    return re.sub(r"\]\(([^)#]+)\)", repl, text)


# Stale names in private willow.md — map to files that exist in the public repo.
_LINK_ALIASES = {
    "../willow/fylgja/skills/willow-worktree.md": "../willow/fylgja/skills/worktree.md",
}


def _apply_link_aliases(text: str) -> str:
    for old, new in _LINK_ALIASES.items():
        text = text.replace(f"]({old})", f"]({new})")
    return text


def _banner(source: Path) -> str:
    today = date.today().isoformat()
    home = Path.home()
    if str(source).startswith(str(home)):
        display = "~/" + str(source.relative_to(home))
    else:
        try:
            display = str(source.relative_to(REPO_ROOT))
        except ValueError:
            display = str(source)
    return f"""# Willow fleet contract (public snapshot)

b17: PUBCNT · ΔΣ=42

> **Auto-generated** from `{display}` on {today}.
> Run `python3 scripts/sync_contract_snapshot.py` after editing the private contract.
>
> This file is a **redacted snapshot** for GitHub-only clones. Machine-specific paths,
> persona tables, and operator secrets stay in **willow-config** — see [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md).

---


"""


def main() -> int:
    source = _resolve_willow_md()
    if source is None:
        print(
            "sync_contract_snapshot: willow.md not found "
            "(clone willow-config to ~/github/.willow or set WILLOW_HOME)",
            file=sys.stderr,
        )
        return 1

    body = _extract_sections(source.read_text(encoding="utf-8"), SECTION_HEADINGS)
    if not body:
        print("sync_contract_snapshot: no sections extracted — check heading names", file=sys.stderr)
        return 1

    footer = """

---

*Public snapshot · canonical contract lives in willow-config · ΔΣ=42*
"""
    OUT_PATH.write_text(
        _banner(source) + _apply_link_aliases(_fix_repo_root_links(body)) + footer,
        encoding="utf-8",
    )
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes) from {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
