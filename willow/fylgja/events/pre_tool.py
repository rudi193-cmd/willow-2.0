"""
events/pre_tool.py — PreToolUse hook handler.
Safety gate → MCP guard (Bash + Agent + native web) → F5 canon guard (write tools).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.agent_identity import require_agent_name
from willow.fylgja._mcp import call
from willow.fylgja.safety.platform import check_all as _safety_check_all

try:
    from willow.context.ledger import log_block as _ledger_block
    _LEDGER_AVAILABLE = True
except Exception:
    _LEDGER_AVAILABLE = False
from willow.fylgja.safety.session import get_session_user_id, get_session_role, get_training_consent
from willow.fylgja.mcp_routing import BASH_TO_MCP as _MCP_BASH_TO_MCP
from willow.fylgja.safety.security_scan import (
    scan_bash as _scan_bash,
    scan_write as _scan_write,
    worst as _scan_worst,
    SEV_HIGH,
)

AGENT = require_agent_name()
MAX_DEPTH = int(os.environ.get("WILLOW_AGENT_MAX_DEPTH", "3"))
DEPTH_FILE = Path("/tmp/willow-agent-depth-stack.txt")
BOOT_DONE = Path(f"/tmp/willow-boot-done-{AGENT}.flag")

def _boot_done(session_id: str = ""):
    # Per-session sentinel: parallel windows all run as the same fleet
    # identity, so the agent-keyed flag alone lets one window's
    # SessionStart clear another's boot state mid-session (2026-07-04).
    # Falls back to the legacy shared path when no session_id is given.
    sid = "".join(c for c in (session_id or "") if c.isalnum() or c in "_-")[:16]
    if sid:
        return Path(f"/tmp/willow-boot-done-{AGENT}-{sid}.flag")
    return BOOT_DONE

_BOOT_MD_PATH = str(Path(__file__).parent.parent / "skills" / "boot.md")
_KART_PENDING_TTL = 1800  # seconds — backstop if kart_task_run is never called
_BLOCK_FLAG_THRESHOLD = int(os.environ.get("WILLOW_BLOCK_FLAG_THRESHOLD", "10"))
_BASH_SESSION_THRESHOLD = int(os.environ.get("WILLOW_BASH_SESSION_THRESHOLD", "5"))
_WARN_ESCALATE_STRIKES = int(os.environ.get("WILLOW_WARN_ESCALATE_STRIKES", "2"))
_SESSION_BAN_STRIKES = int(os.environ.get("WILLOW_SESSION_BAN_STRIKES", "3"))

# Native IDE web tools — warn until willow_web_fetch ships, then hard-block.
_NATIVE_WEB_SEARCH_BLOCK = True
_NATIVE_WEB_FETCH_BLOCK = True

_WEB_SEARCH_REDIRECT = (
    "Use MCP for open-web search — not native WebSearch. "
    "→ mcp__willow__willow_web_search({app_id, query}) "
    "· institutional sources → willow_external({app_id, mode='search', query})"
)
_WEB_FETCH_REDIRECT_WARN = (
    "Prefer MCP for URL fetch (external-guard + audit). "
    "→ willow_web_search for discovery · willow_external(mode=search) for archives."
)
_WEB_FETCH_REDIRECT_BLOCK = (
    "WebFetch is blocked — use guarded MCP fetch with external-guard. "
    "→ mcp__willow__willow_web_fetch({app_id, url}) "
    "or willow_external({app_id, mode='fetch', url})"
)

_REPO_ROOT = str(Path(__file__).parent.parent.parent.parent)

_MAI_HEADER = "@markdownai"
_MAI_WRITE_TOOLS = frozenset({"Write", "Edit", "StrReplace", "search_replace"})
_MAI_WRITE_MSG = (
    "Use mai_write_file (willow MCP) for @markdownai .md files. "
    "Use mai_read_file first when updating existing content."
)


def _markdownai_write_block(tool_name: str, tool_input: dict) -> str | None:
    """Block IDE Write/Edit on @markdownai files — use mai_write_file instead."""
    if tool_name not in _MAI_WRITE_TOOLS:
        return None
    file_path = str(
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("file")
        or ""
    )
    if not file_path.endswith(".md"):
        return None
    content = str(
        tool_input.get("content")
        or tool_input.get("new_string")
        or tool_input.get("new_str")
        or ""
    )
    p = Path(file_path).expanduser()
    if content.lstrip().startswith(_MAI_HEADER):
        return _MAI_WRITE_MSG
    if p.is_file():
        try:
            if p.read_text(encoding="utf-8", errors="replace").lstrip().startswith(_MAI_HEADER):
                return _MAI_WRITE_MSG
        except OSError:
            pass
    return None


def _rule_key(tool_name: str, reason: str) -> str:
    """Stable per-rule id. Block reasons are fixed redirect strings, so the
    tool + reason-prefix identifies the rule across repeated hits."""
    import hashlib
    digest = hashlib.sha1(f"{tool_name}|{reason[:80]}".encode("utf-8")).hexdigest()[:8]
    return f"block-{digest}"


def _corpus_log_block(tool_name: str, reason: str, session_id: str) -> None:
    """Phase 4(a/b): hook-enforcement blocks are *telemetry*, not human feedback.

    (a) Increment a per-rule counter in corpus/block_telemetry (one row per rule:
        hit_count, first/last_seen, runtimes) instead of writing a fresh correction
        atom every time.
    (b) When hit_count crosses a multiple of WILLOW_BLOCK_FLAG_THRESHOLD, open a
        SOIL flag in willow/flags so operators see repeated enforcement — agents
        keep attempting a blocked pattern despite redirects.
    """
    try:
        if _REPO_ROOT not in sys.path:
            sys.path.insert(0, _REPO_ROOT)
        from core.store_port import get_store_port
        _store = get_store_port()
        key = _rule_key(tool_name, reason)
        now = datetime.now(timezone.utc).isoformat()
        try:
            runtime = AGENT
        except Exception:
            runtime = "unknown"
        existing = _store.get("corpus/block_telemetry", key) or {}
        runtimes = set(existing.get("runtimes") or [])
        runtimes.add(runtime)
        new_count = int(existing.get("hit_count") or 0) + 1
        _store.put("corpus/block_telemetry", {
            "id": key,
            "type": "block_telemetry",
            "tool": tool_name,
            "sample_reason": reason[:200],
            "hit_count": new_count,
            "first_seen": existing.get("first_seen") or now,
            "last_seen": now,
            "last_session_id": session_id,
            "runtimes": sorted(runtimes),
            "b17": "BTEL0",
        }, record_id=key)
        # Phase 4(b): repetition trigger — open a flag at each threshold crossing.
        if new_count % _BLOCK_FLAG_THRESHOLD == 0:
            flag_id = f"flag-{key}"
            existing_flag = _store.get("willow/flags", flag_id) or {}
            if existing_flag.get("flag_state") != "open":
                _store.put("willow/flags", {
                    "id": flag_id,
                    "type": "flag",
                    "flag_state": "open",
                    "title": (
                        f"Repeated enforcement: '{tool_name}' blocked {new_count}× fleet-wide"
                    ),
                    "source": "block_telemetry",
                    "rule_key": key,
                    "hit_count": new_count,
                    "sample_reason": reason[:200],
                    "fix_path": (
                        "Agents still attempting this pattern — check boot tool_denial "
                        "injection and pre_tool warn escalation; review BASH_BLOCKS / "
                        "_MCP_BASH_TO_MCP redirects"
                    ),
                    "opened_at": now,
                    "b17": "BFLAG0",
                }, record_id=flag_id)
        # Signal taxonomy: also write a tool_denial preference signal.
        from willow.fylgja.tool_denials import upsert_tool_denial
        upsert_tool_denial(_store, tool_name=tool_name, reason=reason, session_id=session_id)
    except Exception:
        pass

# Legitimate shell Python — checked before BASH_BLOCKS.
_BASH_ALLOW_PATTERNS = [
    r"(?i)python3?\s+-m\s+pytest\b",
    r"(?i)python3?\s+-m\s+willow\.fylgja\.(install|install_project|hook_runner)\b",
    r"(?i)python3?\s+seed\.py\b",
    r"(?i)python3?\s+-m\s+(ruff|mypy)\b",
    r"(?i)\./willow(\.sh)?\b",
    r"(?i)\./willow\s+agents\b",
]

# Each entry: (pattern, decision, redirect_message)
# decision: "block" = hard stop | "warn" = let through but redirect
BASH_BLOCKS = [
    (r"\bsqlite3\b", "block",
     "Direct SQLite access is not allowed. "
     "→ Use MCP: soil_get / soil_list / soil_search, or Read for schema inspection."),
    (r"^\s*psql\s", "block",
     "Direct psql access is not allowed. "
     "→ Use MCP: pg_bridge via Python, or Read pg_bridge.py for schema inspection."),
    (r"^\s*(cat|head|tail)\s", "block",
     "Use the Read tool instead of cat/head/tail — it provides line numbers and better context. "
     "→ Read({file_path: '<path>'})"),
    (r"^\s*ls(\s|$)", "block",
     "Do not run ls in agent Bash — Kart is the execution plane. "
     "→ agent_task_submit(app_id, task='ls <path>') then kart_task_run(app_id). "
     "Willow atom listings → soil_list / app_list / fleet_agents (MCP data lane)."),
    (r"(?i)(?:^|\s)(?:env\s+)?PYTHONPATH=", "block",
     "Do not bypass Willow with PYTHONPATH= shell. "
     "→ MCP tools (kb_search, soil_get, fleet_status, handoff_latest, …). "
     "Shell-only work → agent_task_submit + kart_task_run (see /kart)."),
    (r"(?i)python3?\s+-m\s+(willow|sap|core)\.", "block",
     "Do not invoke Willow modules via python -m in Bash. "
     "→ Matching MCP tool — registry: sap/mcp_registry.json."),
    (r"(?i)python3?\s+(-c|--command)\s+.*\b(from\s+(core|willow|sap)|import\s+(core|willow|sap))\b", "block",
     "Inline Python importing Willow core is blocked. "
     "→ MCP tools, or Kart with a script in /tmp/ for true shell-only work."),
    (r"(?i)python3?\s+.*\b(pg_bridge|sqlite_bridge|willow_store|promote_intake|sap_mcp)\b", "warn",
     "Willow Python entrypoint in Bash — prefer MCP if a tool exists. "
     "→ agent_task_submit(app_id, task='python3 /tmp/job.py') + kart_task_run."),
    # grep/find entries removed 2026-07-06: dead code. check_bash_block() checks
    # _MCP_BASH_TO_MCP (mcp_routing.BASH_TO_MCP) first, which already matches
    # \bgrep\b and \bfind\s and returns before this list is ever reached.
    (r"^\s*bash\s+", "warn",
     "bash <script> detected. Prefer Kart for script execution. "
     "→ agent_task_submit(app_id, task='bash scripts/foo.sh') + kart_task_run(app_id)"),
]

# Loki runs disk audits. These read-only patterns bypass the builder guards above.
_AUDIT_AGENTS = {"loki"}
_AUDIT_ALLOW_PATTERNS = [
    r"^\s*psql\s+-[lL]",   # list databases only — no writes
    r"(?i)^\s*psql\s+.*-c\s+['\"]?\s*(select|show|\\[a-z\\])",  # read-only: SELECT/SHOW/meta-commands only
    r"^\s*ls(\s|$)",        # file listing for disk audit
]

# User-owned SQLite databases that are not protected stores.
# Access to these bypasses the \bsqlite3\b block.
# Protected stores (vault.db, .willow/store) are NOT listed here and remain blocked.
_SQLITE_USER_PATHS = [
    r"/SAFE/",          # principal personal data (sean.db, etc.)
    r"\bai_news\.db\b", # AI news knowledge graph
]


def _sqlite_access_allowed(command: str) -> bool:
    return any(re.search(p, command) for p in _SQLITE_USER_PATHS)


# Worktree-cleanup exception (S18). Git worktree husks are bind-mounted into every
# Kart sandbox, so their removal returns EBUSY inside bwrap — it MUST run host-side
# via agent Bash. This is the one shell operation the MCP/Kart lane structurally
# cannot perform. The exception is deliberately narrow: a SINGLE bare rm/rmdir/
# git-worktree command whose every target lives under a `/worktrees/` directory, with
# NO command chaining or substitution (`;`, `&&`, `||`, `|`, backtick, `$(`). That
# strictness is what lets it also bypass the destructive security scan safely — a
# chained or substituted command never matches, so nothing can be smuggled through.
_WORKTREE_CLEANUP_RE = re.compile(
    r"^(?:"
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(?:[^\s]*/worktrees/[^\s]+\s*)+"
    r"|rmdir\s+(?:-[a-zA-Z]+\s+)?(?:[^\s]*/worktrees/[^\s]+\s*)+"
    r"|git\s+(?:-C\s+[^\s]+\s+)?worktree\s+"
    r"(?:remove(?:\s+--force|\s+-f)?\s+[^\s]*/worktrees/[^\s]+|prune)\s*"
    r")$"
)
_WORKTREE_CLEANUP_FORBIDDEN = (";", "&&", "||", "|", "`", "$(", "\n", ">", "<")


def _is_worktree_cleanup(command: str) -> bool:
    """True only for a single, unchained rm/rmdir/git-worktree on a /worktrees/ path."""
    c = command.strip()
    if any(tok in c for tok in _WORKTREE_CLEANUP_FORBIDDEN):
        return False
    return bool(_WORKTREE_CLEANUP_RE.match(c))

F5_PROSE_TOOLS = {
    "mcp__willow__soil_put": "record",
    "mcp__willow__soil_update": "record",
    "mcp__willow__kb_ingest": "content",
}

FLEET_CHANNEL_MAX_CHARS = 400


def check_channel_enforce(tool_name: str, tool_input: dict) -> str | None:
    """Warn if grove_send_message exceeds #fleet char limit."""
    if tool_name not in ("mcp__grove__grove_send_message", "mcp__claude_ai_Grove__grove_send_message"):
        return None

    channel_name = tool_input.get("channel_name", "")
    content = tool_input.get("content", "")

    if channel_name == "fleet" and len(content) > FLEET_CHANNEL_MAX_CHARS:
        return json.dumps({
            "decision": "warn",
            "reason": (
                f"#fleet is short-form (max {FLEET_CHANNEL_MAX_CHARS} chars). "
                f"Your message is {len(content)} chars. Consider: (1) move to #general or topic channel, "
                f"or (2) write to file and post path."
            ),
        })
    return None


def check_bash_block(command: str) -> tuple[str, str] | None:
    """Returns (decision, reason) or None. decision is 'block' or 'warn'."""
    # S18 exception: worktree husk cleanup is host-only (bind-mount EBUSY in Kart).
    if _is_worktree_cleanup(command):
        return None
    if AGENT in _AUDIT_AGENTS:
        for pattern in _AUDIT_ALLOW_PATTERNS:
            if re.search(pattern, command, re.MULTILINE):
                return None
    for pattern in _BASH_ALLOW_PATTERNS:
        if re.search(pattern, command, re.MULTILINE):
            return None
    for pattern, decision, mcp_hint in _MCP_BASH_TO_MCP:
        if re.search(pattern, command, re.MULTILINE):
            return decision, f"Use MCP instead of shell. → {mcp_hint}"
    for pattern, decision, reason in BASH_BLOCKS:
        if re.search(pattern, command, re.MULTILINE):
            if pattern == r"\bsqlite3\b" and _sqlite_access_allowed(command):
                continue
            return decision, reason
    return None


def check_boot_gate(tool_name: str, tool_input: dict,
                    session_id: str = "") -> str | None:
    """Block every tool call until the boot sentinel exists, except reading boot.md
    itself and writing the sentinel file. Real enforcement (decision:block) —
    replaces the old advisory-only print in prompt_submit.py's _boot_guard."""
    # Integration tests exercise pre_tool.main() without a live boot ritual;
    # PYTEST_CURRENT_TEST is set automatically under pytest (see tests/vcr.py).
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    flag = _boot_done(session_id)
    if flag.exists():
        return None
    target = str(
        tool_input.get("file_path") or tool_input.get("path") or ""
    )
    if tool_name == "Read" and target == _BOOT_MD_PATH:
        return None
    if tool_name == "Write" and target == str(flag):
        return None
    return (
        f"Boot sentinel absent for this session. Read {_BOOT_MD_PATH}, complete the "
        f"steps there, then write {flag} to clear this gate."
    )


def _kart_pending_path(session_id: str) -> Path:
    """Must match post_tool.py's _kart_pending_path exactly — same file, written
    there on agent_task_submit, read/cleared here on the next tool call."""
    safe = (session_id or "unknown")[:16].replace("/", "_")
    return Path(f"/tmp/willow-kart-pending-{safe}.json")


def check_kart_reuse(tool_name: str, tool_input: dict, session_id: str) -> str | None:
    """Real enforcement for the old PostToolUse-only Kart nudge: PostToolUse
    writes the submitted command to a pending file; this blocks a Bash
    re-run of that exact command until kart_task_run is called for it (which
    clears the pending file). This is the post-tool-writes /
    pre-tool-enforces pattern — the same shape as the existing bash-count /
    rule-strike state files, just keyed to a specific prior action instead of
    a rolling counter."""
    p = _kart_pending_path(session_id)
    if tool_name == "mcp__willow__kart_task_run":
        p.unlink(missing_ok=True)
        return None
    if tool_name != "Bash":
        return None
    if not p.exists():
        return None
    try:
        pending = json.loads(p.read_text())
    except Exception:
        p.unlink(missing_ok=True)
        return None
    if time.time() - pending.get("ts", 0) > _KART_PENDING_TTL:
        p.unlink(missing_ok=True)
        return None
    command = (tool_input.get("command") or "").strip()
    if command and command == str(pending.get("command", "")).strip():
        tid = pending.get("task_id", "")
        return (
            f"Already submitted to Kart (task_id={tid}). "
            "Call kart_task_run(app_id) for its output instead of re-running in Bash."
        )
    return None


def check_agent_block(subagent_type: str) -> str | None:
    """Block subagents that replicate grep/find/shell lanes outside PreToolUse."""
    raw = (subagent_type or "").strip()
    norm = raw.replace("_", "-").lower()
    if norm == "explore":
        return (
            "Explore subagent is blocked. Use MCP: willow_find, code_graph_search, "
            "cbm_search, kb_search, soil_search — or willow_run(script_body=...) via Kart."
        )
    if norm in ("generalpurpose", "general-purpose"):
        return (
            "generalPurpose Task subagent is blocked for code/search work. "
            "Use Willow MCP directly (willow_find, code_graph_search, cbm_search) "
            "or willow_run / Kart — delegated subagents bypass hook enforcement."
        )
    if norm == "shell":
        return (
            "shell subagent is blocked. Use willow_run / agent_task_submit + kart_task_run."
        )
    return None


_HOOK_GUARD_FRAGMENTS = (
    "willow/fylgja/events/",
    "willow/fylgja/hook_runner.py",
    "willow/fylgja/bin/fylgja-hook",
    "willow/fylgja/config/cursor-hooks.json",
    ".cursor/hooks.json",
    ".claude/settings.json",
)


def _normalize_path(path: str) -> str:
    return str(Path(path).expanduser()).replace("\\", "/")


def check_hook_tamper_guard(tool_name: str, tool_input: dict) -> str | None:
    """Block agents from reading/editing Fylgja hook sources (Sonnet gremlin path)."""
    if os.environ.get("WILLOW_HOOK_MAINTENANCE"):
        return None
    file_path = str(
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("file")
        or ""
    )
    if not file_path:
        return None
    norm = _normalize_path(file_path)
    if not any(frag in norm for frag in _HOOK_GUARD_FRAGMENTS):
        return None
    if tool_name == "Read":
        return (
            "Fylgja hook source is not readable by agents (prevents bypass discovery). "
            "Use docs/CONTRACT.md and willow/fylgja/skills/boot.md. "
            "Maintainers: set WILLOW_HOOK_MAINTENANCE=1 for hook edits."
        )
    if tool_name in ("Write", "Edit", "StrReplace"):
        return (
            "Fylgja hook files cannot be edited via IDE tools. "
            "Change hooks in a maintainer session (WILLOW_HOOK_MAINTENANCE=1) "
            "or queue Kart work on the host."
        )
    return None


def check_native_web_block(tool_name: str) -> tuple[str, str] | None:
    """Route native WebSearch/WebFetch to Willow MCP web tools."""
    if tool_name == "WebSearch":
        decision = "block" if _NATIVE_WEB_SEARCH_BLOCK else "warn"
        return decision, _WEB_SEARCH_REDIRECT
    if tool_name == "WebFetch":
        if _NATIVE_WEB_FETCH_BLOCK:
            return "block", _WEB_FETCH_REDIRECT_BLOCK
        return "warn", _WEB_FETCH_REDIRECT_WARN
    return None


def _apply_native_web_escalation(
    session_id: str,
    tool_name: str,
    decision: str,
    reason: str,
) -> tuple[str, str]:
    """Escalate warn→block on repeat (same strike model as Bash)."""
    rule_key = _rule_key(tool_name, reason)
    current = _read_session_rule_strikes(session_id).get(rule_key, 0)
    ban_msg = (
        f"[SESSION-BAN] {tool_name} is blocked for the rest of this session "
        f"(rule {rule_key}, {_SESSION_BAN_STRIKES}+ attempts). "
        f"Use willow_web_search / willow_web_fetch / willow_external.\n\n"
    )
    if current >= _SESSION_BAN_STRIKES:
        return "block", ban_msg + reason
    strike = _increment_session_rule_strike(session_id, rule_key)
    if strike >= _SESSION_BAN_STRIKES:
        return "block", ban_msg + reason
    if decision == "warn" and strike >= _WARN_ESCALATE_STRIKES:
        return (
            "block",
            (
                f"[ESCALATED] Repeated {tool_name} attempt ({strike}× this session) — "
                f"now blocked. Use Willow MCP web tools.\n\n{reason}"
            ),
        )
    if decision == "block" and strike >= 2:
        return "block", f"[REPEAT {strike}×] {reason}"
    return decision, reason


def _mcp_store_search(query: str) -> list:
    try:
        result = call("store_search", {
            "app_id": AGENT,
            "collection": f"{AGENT}/file-index",
            "query": query,
        }, timeout=3)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def check_kb_first(path: str) -> str | None:
    """
    Check if a file path is indexed in the KB file-index.
    Returns a KB-FIRST advisory if found (suggesting reading from KB instead of disk),
    or None if not indexed.
    """
    filename = Path(path).name
    results = _mcp_store_search(filename)
    if not results:
        return None
    hit = results[0]
    return (
        f"[KB-FIRST] '{filename}' is indexed (collection: {hit.get('collection', f'{AGENT}/file-index')}, "
        f"id: {hit.get('id', '?')}). Consider reading from KB before disk."
    )


def _read_depth() -> int:
    try:
        return int(DEPTH_FILE.read_text().strip()) if DEPTH_FILE.exists() else 0
    except Exception:
        return 0


def _write_depth(n: int) -> None:
    try:
        if n <= 0:
            DEPTH_FILE.unlink(missing_ok=True)
        else:
            DEPTH_FILE.write_text(str(n))
    except Exception:
        pass


def _bash_counter_path(session_id: str) -> Path:
    safe = (session_id or "unknown")[:16].replace("/", "_")
    return Path(f"/tmp/willow-bash-count-{safe}.txt")


def _session_rule_strikes_path(session_id: str) -> Path:
    safe = (session_id or "unknown")[:16].replace("/", "_")
    return Path(f"/tmp/willow-rule-strikes-{safe}.json")


def _read_session_rule_strikes(session_id: str) -> dict[str, int]:
    p = _session_rule_strikes_path(session_id)
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): int(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _increment_session_rule_strike(session_id: str, rule_key: str) -> int:
    """Per-session strikes for a rule_key (warn/block attempts). Returns new count."""
    strikes = _read_session_rule_strikes(session_id)
    count = int(strikes.get(rule_key, 0)) + 1
    strikes[rule_key] = count
    try:
        _session_rule_strikes_path(session_id).write_text(
            json.dumps(strikes), encoding="utf-8"
        )
    except Exception:
        pass
    return count


def _apply_bash_escalation(
    session_id: str,
    decision: str,
    reason: str,
) -> tuple[str, str]:
    """Escalate warn→block on repeat; session-ban after N strikes on same rule."""
    rule_key = _rule_key("Bash", reason)
    current = _read_session_rule_strikes(session_id).get(rule_key, 0)
    ban_msg = (
        f"[SESSION-BAN] This Bash pattern is blocked for the rest of this session "
        f"(rule {rule_key}, {_SESSION_BAN_STRIKES}+ attempts). "
        f"Use willow_run / Kart or the MCP redirect.\n\n"
    )
    if current >= _SESSION_BAN_STRIKES:
        return "block", ban_msg + reason
    strike = _increment_session_rule_strike(session_id, rule_key)
    if strike >= _SESSION_BAN_STRIKES:
        return "block", ban_msg + reason
    if decision == "warn" and strike >= _WARN_ESCALATE_STRIKES:
        return (
            "block",
            (
                f"[ESCALATED] Repeated Bash attempt ({strike}× this session) — "
                f"now blocked. Use willow_run / Kart or MCP.\n\n{reason}"
            ),
        )
    if decision == "block" and strike >= 2:
        return "block", f"[REPEAT {strike}×] {reason}"
    return decision, reason


def _increment_bash_count(session_id: str) -> int:
    """Increment per-session direct Bash call counter. Returns new count."""
    p = _bash_counter_path(session_id)
    try:
        count = int(p.read_text().strip()) if p.exists() else 0
        count += 1
        p.write_text(str(count))
        return count
    except Exception:
        return 0


_F5_DOC_FIELDS = {"content", "body", "raw_content"}


def _is_prose(s: str) -> bool:
    """True if s looks like a prose document rather than a file path or short value."""
    c = s.strip()
    if c.startswith("/") and len(c) < 300 and "\n" not in c:
        return False
    return len(c) > 150 or c.count("\n") > 2 or c.count(". ") > 1


def check_f5_canon(tool_name: str, tool_input: dict) -> str | None:
    field = F5_PROSE_TOOLS.get(tool_name)
    if not field:
        return None
    content = tool_input.get(field, "")

    # Dict record: only flag if a doc-content field (content/body/raw_content) is prose.
    # Structured metadata fields (description, summary, resolution, etc.) are always allowed.
    if isinstance(content, dict):
        for doc_field in _F5_DOC_FIELDS:
            val = content.get(doc_field, "")
            if isinstance(val, str) and _is_prose(val):
                preview = val[:80].replace("\n", " ")
                return (
                    f"\n[WWSDN/F5] ⚠  CANON DRIFT — record.{doc_field} is prose, not a file path\n"
                    f"[WWSDN/F5]    tool: {tool_name}  field: {field}.{doc_field}\n"
                    f"[WWSDN/F5]    content ({len(val)} chars): \"{preview}...\"\n"
                    f"[WWSDN/F5]    fix: write content to a file, store the path instead\n"
                )
        return None

    # String record (model serialised the dict as JSON): parse and apply same check.
    if not isinstance(content, str) or not content.strip():
        return None
    c = content.strip()
    if c.startswith("{"):
        try:
            import json as _json
            parsed = _json.loads(c)
            if isinstance(parsed, dict):
                return check_f5_canon(tool_name, {field: parsed})
        except Exception:
            pass

    if _is_prose(c):
        preview = c[:80].replace("\n", " ")
        return (
            f"\n[WWSDN/F5] ⚠  CANON DRIFT — content is prose, not a file path\n"
            f"[WWSDN/F5]    tool: {tool_name}  field: {field}\n"
            f"[WWSDN/F5]    content ({len(c)} chars): \"{preview}...\"\n"
            f"[WWSDN/F5]    fix: write content to a file, store the path instead\n"
        )
    return None


def _run_safety_gate(tool_name: str, tool_input: dict, session_id: str) -> str | None:
    """Run platform hard stops. Returns block JSON string or None."""
    try:
        user_id = get_session_user_id()
        user_role = get_session_role(user_id)
        training_consented = get_training_consent()
        result = _safety_check_all(
            tool_name=tool_name,
            tool_input=tool_input,
            user_role=user_role,
            training_consented=training_consented,
        )
        if result:
            try:
                call("store_put", {
                    "app_id": AGENT,
                    "collection": "willow/safety_log",
                    "record": {
                        "id": f"hs-{session_id[:8]}-{abs(hash(tool_name + str(tool_input))) % 99999:05d}",
                        "user_id": user_id,
                        "tool_name": tool_name,
                        "hard_stop_id": result["hard_stop_id"],
                        "reason": result["reason"],
                        "session_id": session_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }, timeout=3)
            except Exception:
                pass
            return json.dumps({"decision": "block", "reason": result["reason"]})
    except Exception:
        pass
    return None


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    session_id = payload.get("session_id", "")

    mai_block = _markdownai_write_block(tool_name, tool_input)
    if mai_block:
        _corpus_log_block(tool_name, mai_block, session_id)
        print(json.dumps({"decision": "block", "reason": mai_block}))
        sys.exit(0)

    boot_block = check_boot_gate(tool_name, tool_input, session_id)
    if boot_block:
        print(json.dumps({"decision": "block", "reason": boot_block}))
        sys.exit(0)

    kart_block = check_kart_reuse(tool_name, tool_input, session_id)
    if kart_block:
        _corpus_log_block(tool_name, kart_block, session_id)
        print(json.dumps({"decision": "block", "reason": kart_block}))
        sys.exit(0)

    hook_guard = check_hook_tamper_guard(tool_name, tool_input)
    if hook_guard:
        _corpus_log_block(tool_name, hook_guard, session_id)
        print(json.dumps({"decision": "block", "reason": hook_guard}))
        sys.exit(0)

    # Safety gate — runs before all other checks
    block = _run_safety_gate(tool_name, tool_input, session_id)
    if block:
        try:
            reason = json.loads(block).get("reason", block)[:300]
        except Exception:
            reason = block[:300]
        if _LEDGER_AVAILABLE:
            try:
                _ledger_block(tool_name, reason, session_id=session_id)
            except Exception:
                pass
        _corpus_log_block(tool_name, reason, session_id)
        print(block)
        sys.exit(0)

    # Agent / Task subagent tools
    subagent_type = tool_input.get("subagent_type", "") or tool_input.get("agent_type", "")
    if subagent_type or tool_name in ("Agent", "Task"):
        reason = check_agent_block(subagent_type) if subagent_type else None
        if reason:
            print(json.dumps({"decision": "block", "reason": reason}))
            sys.exit(0)
        depth = _read_depth()
        if depth >= MAX_DEPTH:
            print(json.dumps({
                "decision": "block",
                "reason": (f"Agent depth limit reached ({depth}/{MAX_DEPTH}). "
                           f"Complete the work directly or surface to parent session."),
            }))
            sys.exit(0)
        _write_depth(depth + 1)
        sys.exit(0)

    # Bash tool
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # Willow workflow guard first
        block_result = check_bash_block(command) if command else None
        escalated: tuple[str, str] | None = None
        if block_result:
            escalated = _apply_bash_escalation(
                session_id, block_result[0], block_result[1]
            )
            decision, reason = escalated
            if decision == "block":
                if _LEDGER_AVAILABLE:
                    try:
                        _ledger_block("Bash", reason[:300], session_id=session_id)
                    except Exception:
                        pass
                _corpus_log_block("Bash", reason, session_id)
                print(json.dumps({"decision": "block", "reason": reason}))
                sys.exit(0)

        # Increment per-session counter for all non-blocked Bash calls.
        bash_count = _increment_bash_count(session_id) if command else 0
        count_warn: str | None = None
        if _BASH_SESSION_THRESHOLD > 0 and bash_count % _BASH_SESSION_THRESHOLD == 0:
            count_warn = (
                f"[BASH-COUNT] {bash_count} direct Bash calls this session. "
                "Prefer Kart for shell work: "
                "agent_task_submit(app_id, task=...) → kart_task_run(app_id)."
            )

        # Emit a single warn combining tool-redirect and count milestone if both apply.
        if escalated:
            _, reason = escalated
            full_reason = f"{reason}\n\n{count_warn}" if count_warn else reason
            print(json.dumps({"decision": "warn", "reason": full_reason}))
        elif count_warn:
            print(json.dumps({"decision": "warn", "reason": count_warn}))

        # Security scan — exfiltration, credential theft, destructive, obfuscation.
        # Skip for user-owned SQLite databases (DROP TABLE etc. on personal data is fine)
        # and for worktree-cleanup (a /worktrees/ path matches the destructive-path
        # rule; the strict single-command check above means nothing else can ride along).
        _scan_skip = (
            (re.search(r"\bsqlite3\b", command) and _sqlite_access_allowed(command))
            or _is_worktree_cleanup(command)
        )
        if command and not _scan_skip:
            issues = _scan_bash(command)
            bad = _scan_worst(issues)
            if bad and bad.severity >= SEV_HIGH:
                print(json.dumps({
                    "decision": "block",
                    "reason": (
                        f"[SECURITY] {bad.message} "
                        f"(category: {bad.category}, severity: {bad.severity})"
                    ),
                }))
                sys.exit(0)
        sys.exit(0)

    # Native IDE web tools — route to Willow MCP (external-guard path)
    if tool_name in ("WebFetch", "WebSearch"):
        block_result = check_native_web_block(tool_name)
        if block_result:
            decision, reason = _apply_native_web_escalation(
                session_id, tool_name, block_result[0], block_result[1]
            )
            if decision == "block":
                if _LEDGER_AVAILABLE:
                    try:
                        _ledger_block(tool_name, reason[:300], session_id=session_id)
                    except Exception:
                        pass
                _corpus_log_block(tool_name, reason, session_id)
                print(json.dumps({"decision": "block", "reason": reason}))
                sys.exit(0)
            print(json.dumps({"decision": "warn", "reason": reason}))
        sys.exit(0)

    # Write/Edit tools — MarkdownAI routing, security path check, F5 canon guard
    if tool_name in ("Write", "Edit") or tool_name in F5_PROSE_TOOLS:
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", tool_input.get("new_string", ""))
        # Security scan — protected paths + code injection
        if file_path or content:
            issues = _scan_write(file_path, content or "")
            bad = _scan_worst(issues)
            if bad and bad.severity >= SEV_HIGH:
                print(json.dumps({
                    "decision": "block",
                    "reason": (
                        f"[SECURITY] {bad.message} "
                        f"(category: {bad.category}, path: {file_path[:80]})"
                    ),
                }))
                sys.exit(0)
        # F5 canon guard (MCP write tools only)
        if tool_name in F5_PROSE_TOOLS:
            f5 = check_f5_canon(tool_name, tool_input)
            if f5:
                _corpus_log_block(tool_name, f5, session_id)
                print(json.dumps({"decision": "block", "reason": f5}))
        sys.exit(0)

    # Channel enforcement — warn on #fleet exceeding char limit
    warn = check_channel_enforce(tool_name, tool_input)
    if warn:
        print(warn)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
