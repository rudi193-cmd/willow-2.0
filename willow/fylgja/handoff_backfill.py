"""Backfill project: frontmatter on session handoff markdown files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from willow.fylgja.handoff_project import DEFAULT_LEGACY_PROJECT

_PROJECT_RE = re.compile(r"^project:\s*(.+)$", re.MULTILINE)
_BRANCH_RE = re.compile(r"^branch:\s*(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)

ALMANAC_SLUGS = frozenset(
    {
        "climate-almanac",
        "health-almanac",
        "economy-almanac",
        "environment-almanac",
        "civic-almanac",
    }
)


def _normalize_project(raw: str) -> str:
    project = (raw or "").strip()
    if project == "willow":
        return DEFAULT_LEGACY_PROJECT
    return project


def infer_project_from_content(content: str) -> str | None:
    """Return inferred fleet project id, or None to use the desk default."""
    branch = _BRANCH_RE.search(content)
    if branch:
        slug = _normalize_project(branch.group(1))
        if slug in ALMANAC_SLUGS or slug.endswith("-almanac"):
            return slug

    snippet = content[:3000].lower()
    if "schmidt" in snippet and ("smapply" in snippet or "schmidt sciences" in snippet):
        return None

    for slug in sorted(ALMANAC_SLUGS, key=len, reverse=True):
        if slug in snippet or slug.replace("-", " ") in snippet:
            return slug

    title = ""
    title_match = re.search(r"^#\s*HANDOFF:\s*(.+)$", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).lower()
    if "climate almanac" in title or (
        "almanac-data" in snippet and "climate almanac" in snippet
    ):
        return "climate-almanac"
    return None


def resolve_target_project(content: str) -> tuple[str, str]:
    """Return (target_project, reason). reason is unchanged | normalize | infer | default."""
    existing = _PROJECT_RE.search(content)
    if existing:
        current = existing.group(1).strip()
        normalized = _normalize_project(current)
        if normalized == current:
            return current, "unchanged"
        return normalized, "normalize"

    inferred = infer_project_from_content(content)
    if inferred:
        return inferred, "infer"
    return DEFAULT_LEGACY_PROJECT, "default"


@dataclass(frozen=True)
class BackfillPlan:
    path: Path
    current: str
    target: str
    reason: str


def plan_file(path: Path) -> BackfillPlan | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not content.lstrip().startswith("---"):
        return None

    existing = _PROJECT_RE.search(content)
    current = existing.group(1).strip() if existing else ""
    target, reason = resolve_target_project(content)
    if reason == "unchanged" or current == target:
        return None
    return BackfillPlan(path, current, target, reason)


def apply_project_stamp(content: str, project: str) -> str:
    if _PROJECT_RE.search(content):
        return _PROJECT_RE.sub(f"project: {project}", content, count=1)

    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    inner = match.group(1)
    if re.search(r"^agent:\s*", inner, re.MULTILINE):
        inner_new = re.sub(
            r"^(agent:\s*.+)$",
            rf"\1\nproject: {project}",
            inner,
            count=1,
            flags=re.MULTILINE,
        )
    elif re.search(r"^date:\s*", inner, re.MULTILINE):
        inner_new = re.sub(
            r"^(date:\s*.+)$",
            rf"\1\nproject: {project}",
            inner,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        inner_new = f"project: {project}\n{inner}"
    return content[: match.start(1)] + inner_new + content[match.end(1) :]


def scan_agent_handoffs(agent_dir: Path, agent: str) -> list[BackfillPlan]:
    if not agent_dir.is_dir():
        return []
    suffix = f"_{agent.lower()}.md"
    plans: list[BackfillPlan] = []
    for path in sorted(agent_dir.glob("session_handoff-*.md")):
        if not path.name.lower().endswith(suffix):
            continue
        plan = plan_file(path)
        if plan is not None:
            plans.append(plan)
    return plans


def apply_plans(plans: list[BackfillPlan]) -> list[dict]:
    applied: list[dict] = []
    for plan in plans:
        text = plan.path.read_text(encoding="utf-8", errors="replace")
        updated = apply_project_stamp(text, plan.target)
        if updated != text:
            plan.path.write_text(
                updated if updated.endswith("\n") else updated + "\n",
                encoding="utf-8",
            )
            applied.append(
                {
                    "file": plan.path.name,
                    "from": plan.current or None,
                    "to": plan.target,
                    "reason": plan.reason,
                }
            )
    return applied
