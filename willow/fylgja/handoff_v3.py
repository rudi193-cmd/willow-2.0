"""
Handoff v3 — claims record carrying narrative.

ADR: docs/adrs/ADR-20260703-handoff-v3-claims-record.md
Schema: docs/adrs/handoff-v3.schema.json

A v3 handoff is one markdown file with three layers:
  1. machine skeleton — code-written facts (crash-safe)
  2. typed claims     — open threads + next_bite, verified at READ time
  3. narrative        — model-written, tier-scaled, optional

Models never author the JSON machine block; fields arrive via tool call and
this module serializes them. Verification verdicts are boot-digest output and
are never written back into the file.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from willow.fylgja.handoff_project import resolve_handoff_project
from willow.fylgja.handoff_write import handoff_dir, next_session_filename

CLAIM_KINDS = (
    "branch_pushed",
    "pr_state",
    "file_exists",
    "flag_open",
    "sha_current",
    "prose",
)

_MACHINE_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
_CLAIM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def extract_machine_block(content: str) -> dict | None:
    """Return the parsed v3 machine block from markdown, or None.

    Scans fenced ```json blocks from the end of the document — the machine
    block is conventionally last, and earlier blocks may be examples.
    """
    for match in reversed(list(_MACHINE_BLOCK_RE.finditer(content or ""))):
        try:
            data = json.loads(match.group(1))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("format") == "v3":
            return data
    return None


def is_v3_handoff(content: str) -> bool:
    head = (content or "").lstrip()[:400]
    if re.search(r"^format:\s*v3\s*$", head, re.MULTILINE):
        return True
    return extract_machine_block(content) is not None


def validate_machine_block(block: dict) -> list[str]:
    """Structural validation. Returns a list of problems (empty = valid).

    Uses jsonschema against docs/adrs/handoff-v3.schema.json when available;
    always runs the cheap structural checks so validation works without the
    optional dependency.
    """
    problems: list[str] = []
    if not isinstance(block, dict):
        return ["machine block is not an object"]
    if block.get("format") != "v3":
        problems.append("format must be 'v3'")
    for key in ("session", "agent", "project", "runtime", "written_at", "written_by"):
        if not str(block.get(key) or "").strip():
            problems.append(f"missing required field: {key}")
    if not isinstance(block.get("skeleton"), dict):
        problems.append("skeleton must be an object")
    claims = block.get("claims")
    if not isinstance(claims, list):
        problems.append("claims must be a list")
        claims = []
    next_bite = block.get("next_bite")
    all_claims = list(claims) + ([next_bite] if isinstance(next_bite, dict) else [])
    if not isinstance(next_bite, dict):
        problems.append("next_bite must be a claim object")
    for claim in all_claims:
        problems.extend(_validate_claim(claim))

    schema_path = _schema_path()
    if schema_path is not None:
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            problems.extend(
                f"schema: {err.message}" for err in validator.iter_errors(block)
            )
        except ImportError:
            pass
        except Exception as exc:
            problems.append(f"schema load failed: {exc}")
    return problems


def _validate_claim(claim: object) -> list[str]:
    if not isinstance(claim, dict):
        return ["claim is not an object"]
    problems: list[str] = []
    cid = str(claim.get("id") or "")
    if not _CLAIM_ID_RE.match(cid):
        problems.append(f"claim id invalid: {cid!r}")
    if not str(claim.get("text") or "").strip():
        problems.append(f"claim {cid}: missing text")
    kind = claim.get("kind")
    if kind not in CLAIM_KINDS:
        problems.append(f"claim {cid}: unknown kind {kind!r}")
    if kind != "prose":
        verify = claim.get("verify")
        if not isinstance(verify, dict) or not str(verify.get("subject") or "").strip():
            problems.append(f"claim {cid}: non-prose claim needs verify.subject")
    if not str(claim.get("opened") or "").strip():
        problems.append(f"claim {cid}: missing opened date")
    return problems


def _schema_path() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    candidate = root / "docs" / "adrs" / "handoff-v3.schema.json"
    return candidate if candidate.is_file() else None


# ---------------------------------------------------------------------------
# Skeleton collection — code-observed facts, every probe fail-soft
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 8) -> str:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def collect_machine_skeleton(repo_root: str | Path = "") -> dict:
    """Best-effort code-observed session facts. Never raises."""
    root = Path(repo_root) if repo_root else Path.cwd()
    skeleton: dict = {}

    branch = _run(["git", "branch", "--show-current"], cwd=root)
    if branch:
        skeleton["branches"] = [branch]

    log = _run(
        ["git", "log", "--since=12 hours ago", "--format=%h\t%s", "-20"], cwd=root
    )
    if log:
        commits = []
        for line in log.splitlines():
            sha, _, subject = line.partition("\t")
            commits.append({"sha": sha, "branch": branch or "", "subject": subject[:120]})
        skeleton["commits"] = commits

    changed = _run(["git", "status", "--porcelain"], cwd=root)
    if changed:
        skeleton["files_changed"] = [
            line[3:].strip() for line in changed.splitlines()[:40]
        ]
    return skeleton


def _handoff_paths_for_agent(agent: str) -> list[Path]:
    dest = handoff_dir(agent)
    if not dest.is_dir():
        return []
    return sorted(dest.glob(f"session_handoff-*_{agent}.md"))


def _block_for_session(agent: str, session_id: str, *, written_by: str) -> dict | None:
    if not session_id:
        return None
    for path in reversed(_handoff_paths_for_agent(agent)):
        try:
            block = extract_machine_block(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            block
            and block.get("written_by") == written_by
            and str(block.get("session_id") or "") == session_id
        ):
            return block
    return None


# A model handoff written within this window of session stop is treated as
# belonging to the current working session. Matches collect_machine_skeleton's
# `--since=12 hours ago` window — the codebase's notion of one session's span.
_SESSION_RECENCY_HOURS = 12.0


def _parse_iso(ts: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _recent_block(agent: str, *, written_by: str, within_hours: float) -> dict | None:
    """Newest handoff block from `written_by` written within `within_hours` of now."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    for path in reversed(_handoff_paths_for_agent(agent)):
        try:
            block = extract_machine_block(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not block or block.get("written_by") != written_by:
            continue
        written_at = _parse_iso(block.get("written_at"))
        if written_at is not None and written_at >= cutoff:
            return block
    return None


def should_write_stop_hook_handoff(
    agent: str,
    session_id: str = "",
    *,
    recency_hours: float = _SESSION_RECENCY_HOURS,
) -> bool:
    """True when session_stop should emit a crash-safe skeleton handoff.

    Skip when this session already produced a handoff:
      * exact session_id match on a prior stop_hook or model handoff (precise), or
      * a model_tool_call handoff written within the recent-session window.

    The recency fallback is load-bearing: the model handoff path
    (handoff_write_v3) usually cannot stamp its own session_id, so the precise
    session_id match never fires for it. Without the fallback, the stop hook
    writes a skeleton on top of a rich model handoff and — sorting to a later
    session letter — that empty skeleton shadows the model's handoff at next
    boot (the "Session ended without model handoff" placeholder wins).
    """
    if session_id and _block_for_session(agent, session_id, written_by="stop_hook"):
        return False
    if session_id and _block_for_session(agent, session_id, written_by="model_tool_call"):
        return False
    if _recent_block(agent, written_by="model_tool_call", within_hours=recency_hours):
        return False
    return True


def skeleton_from_stack(stack: dict, repo_root: str | Path = "") -> dict:
    """Merge session_stop stack snapshot into the machine skeleton."""
    sk = collect_machine_skeleton(repo_root)
    tasks = stack.get("open_tasks") or []
    if tasks:
        sk["kart_tasks"] = [
            {
                "id": str(t.get("id") or t.get("task_id") or ""),
                "status": str(t.get("status") or ""),
                "summary": str(t.get("task") or "")[:120],
            }
            for t in tasks
            if isinstance(t, dict)
        ]
    flags = stack.get("open_flags") or []
    if flags:
        sk["flags_delta"] = {
            "opened": [
                str(f.get("title") or "")[:80]
                for f in flags
                if isinstance(f, dict)
            ][:10],
            "closed": [],
        }
    return sk


def claims_from_stack(stack: dict) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    claims: list[dict] = []
    for i, flag in enumerate(stack.get("open_flags") or []):
        if not isinstance(flag, dict):
            continue
        claims.append({
            "id": f"stack-flag-{i}",
            "text": str(flag.get("title") or "open flag")[:140],
            "kind": "prose",
            "opened": today,
        })
    for i, task in enumerate(stack.get("open_tasks") or []):
        if not isinstance(task, dict):
            continue
        claims.append({
            "id": f"stack-task-{i}",
            "text": f"Kart {task.get('status', 'pending')}: {str(task.get('task') or '')[:100]}",
            "kind": "prose",
            "opened": today,
        })
    return claims[:8]


def next_bite_from_stack(stack: dict) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tasks = stack.get("open_tasks") or []
    flags = stack.get("open_flags") or []
    text = "Session ended without model handoff — resume from stack snapshot and skeleton claims."
    if tasks and isinstance(tasks[0], dict) and tasks[0].get("task"):
        text = str(tasks[0]["task"])[:160]
    elif flags and isinstance(flags[0], dict):
        fix = str(flags[0].get("fix_path") or "")
        if fix:
            text = fix[:160]
        elif flags[0].get("title"):
            text = str(flags[0]["title"])[:160]
    return {"id": "next-bite", "text": text, "kind": "prose", "opened": today}


def write_stop_hook_skeleton_handoff(
    agent: str,
    stack: dict,
    *,
    session_id: str = "",
    repo_root: str | Path = "",
    workspace: str | Path = "",
    runtime: str = "unknown",
    project: str = "",
) -> Path | None:
    """Crash-safe v3 handoff from session_stop — skeleton + stack-derived claims. Never raises."""
    if not should_write_stop_hook_handoff(agent, session_id):
        return None
    try:
        root = repo_root or workspace or Path.cwd()
        return write_session_handoff_v3(
            agent,
            summary="Session stop skeleton handoff (crash-safe checkpoint)",
            claims=claims_from_stack(stack),
            next_bite=next_bite_from_stack(stack),
            open_questions=[],
            agreements=[],
            agent_notes=[
                f"stop_hook session_id={session_id or 'unknown'}",
                "Narrative empty — model did not run handoff_write_v3 or /shutdown this session.",
            ],
            understanding="",
            project=project,
            runtime=runtime,
            session_id=session_id,
            skeleton=skeleton_from_stack(stack, root),
            repo_root=root,
            workspace=workspace,
            written_by="stop_hook",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Writer — code serializes; models pass fields via tool call
# ---------------------------------------------------------------------------

def write_session_handoff_v3(
    agent: str,
    *,
    summary: str = "",
    claims: list[dict] | None = None,
    next_bite: dict | None = None,
    open_questions: list[str] | None = None,
    agreements: list[str] | None = None,
    agent_notes: list[str] | None = None,
    understanding: str = "",
    project: str = "",
    runtime: str = "claude-code",
    session_id: str = "",
    skeleton: dict | None = None,
    repo_root: str | Path = "",
    workspace: str | Path = "",
    written_by: str = "model_tool_call",
    suffix: str = "",
) -> Path:
    """Write a v3 handoff file. Raises ValueError when the block is invalid."""
    claims = list(claims or [])
    project_id = (
        project or resolve_handoff_project(workspace=workspace) or "willow-2.0"
    ).strip()
    dest_dir = handoff_dir(agent)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = next_session_filename(agent, suffix)
    match = re.search(r"session_handoff-(\d{4}-\d{2}-\d{2}[a-z]?)_", filename)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session = match.group(1) if match else today
    if session and not session[-1].isalpha():
        session += "a"

    if next_bite is None:
        next_bite = {
            "id": "next-bite",
            "text": "No next action recorded.",
            "kind": "prose",
            "opened": today,
        }

    block: dict = {
        "format": "v3",
        "session": session,
        "agent": agent,
        "project": project_id,
        "runtime": runtime,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "written_by": written_by,
        "skeleton": skeleton if skeleton is not None else collect_machine_skeleton(repo_root),
        "claims": claims,
        "next_bite": next_bite,
        "open_questions": list(open_questions or []),
        "agreements": list(agreements or []),
        "summary": summary or "",
    }
    if session_id:
        block["session_id"] = session_id

    problems = validate_machine_block(block)
    if problems:
        raise ValueError("invalid v3 machine block: " + "; ".join(problems[:8]))

    body = _render_markdown(block, agent_notes or [], understanding)
    path = dest_dir / filename
    path.write_text(body, encoding="utf-8")
    return path


def _render_markdown(block: dict, agent_notes: list[str], understanding: str) -> str:
    """Render the v3 file: frontmatter, narrative sections, machine block."""
    claims: list[dict] = block.get("claims") or []
    next_bite: dict = block.get("next_bite") or {}
    lines: list[str] = [
        "---",
        f"agent: {block['agent']}",
        f"date: {block['written_at'][:10]}",
        f"session: {block['session']}",
        f"runtime: {block['runtime']}",
        "format: v3",
        f"project: {block['project']}",
        "---",
        "",
        f"# HANDOFF: {block.get('summary', '')[:80] or block['session']}",
        "",
        "## What I Now Understand",
        "",
        understanding or block.get("summary") or "",
        "",
        "## Open Threads",
        "",
    ]
    for claim in claims:
        carried = f" (carried from {claim['carried_from']})" if claim.get("carried_from") else ""
        lines.append(f"- **[{claim.get('id')}]** {claim.get('text')}{carried}")
    if not claims:
        lines.append("- none")
    lines += ["", "## What We Agreed On", ""]
    for item in block.get("agreements") or []:
        lines.append(f"- {item}")
    if not block.get("agreements"):
        lines.append("- none recorded")
    lines += ["", "## Open Questions", ""]
    for q in block.get("open_questions") or []:
        lines.append(f"- {q}")
    if not block.get("open_questions"):
        lines.append("- none")
    lines += [
        "",
        "## Next Single Bite",
        "",
        str(next_bite.get("text") or ""),
        "",
        "## Agent Notes for Human",
        "",
    ]
    for note in agent_notes:
        lines.append(f"- {note}")
    if not agent_notes:
        lines.append("-")
    lines += [
        "",
        "## Human Notes to Agent",
        "",
        "-",
        "",
        "## Machine block",
        "",
        "```json",
        json.dumps(block, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser — v3 file -> handoff-index candidate shape (v2-compatible keys)
# ---------------------------------------------------------------------------

def parse_v3_handoff(content: str, filename: str = "") -> dict:
    """Parse a v3 handoff into the parse_session_handoff result shape.

    List fields are JSON-encoded strings to match the v2 parser contract
    (build_handoff_db stores them as TEXT; handoff_index re-parses them).
    """
    block = extract_machine_block(content) or {}
    claims: list[dict] = [c for c in (block.get("claims") or []) if isinstance(c, dict)]
    next_bite = block.get("next_bite") if isinstance(block.get("next_bite"), dict) else {}

    open_threads = [str(c.get("text") or "") for c in claims if c.get("text")]
    questions = [str(q) for q in (block.get("open_questions") or [])]
    bite_text = str(next_bite.get("text") or "").strip()
    if bite_text:
        # Last question slot, stored prefix-stripped exactly like the v2
        # parser does, so extract_next_bite() works unchanged.
        questions.append(f"What is the next single bite? {bite_text}")

    result: dict = {
        "format": "v3",
        "project": str(block.get("project") or ""),
        "handoff_date": str(block.get("written_at") or "")[:10]
        or (filename[16:26] if filename.startswith("session_handoff-") else ""),
        "summary": str(block.get("summary") or "")[:500],
        "claims": json.dumps(claims + ([next_bite] if next_bite else [])),
    }
    if block.get("session_id"):
        result["session_id"] = str(block["session_id"])
    if open_threads:
        result["open_threads"] = json.dumps(open_threads)
    if questions:
        result["questions"] = json.dumps(questions)
    if block.get("agreements"):
        result["agreements"] = json.dumps([str(a) for a in block["agreements"]])
    return result
