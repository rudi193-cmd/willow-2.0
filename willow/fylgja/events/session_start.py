"""
events/session_start.py — SessionStart hook handler.
Hardware state, willow_status, JELES registration.
Outputs additionalContext JSON.
"""
import concurrent.futures as _cf
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.agent_identity import require_agent_name
from willow.fylgja._mcp import call
from willow.fylgja._grove import call as _grove_call
from willow.fylgja._state import reset_turn_count
from willow.fylgja.anchor_state import reset_prompt_count
from willow.fylgja.events._stack_snapshot import normalize_stack_record
from willow.fylgja.project_env import repo_root
from willow.fylgja.session_inject import (
    CONFIRMATION_EXCERPT_CHARS,
    CORRECTION_EXCERPT_CHARS,
    DENIAL_EXCERPT_CHARS,
    MAX_CORRECTIONS,
    MAX_CROSS_RUNTIME_OPEN,
    MAX_HUMAN_CONFIRMATIONS,
    MAX_PREFERENCES,
    MAX_TOOL_DENIALS,
    PREFERENCE_EXCERPT_CHARS,
    dedup_fingerprint,
    excerpt_corpus,
    is_continuation_source,
    is_fresh_source,
    minimal_continuation_block,
    record_injection,
    should_skip_duplicate,
)
from willow.fylgja.willow_home import willow_home

try:
    from willow.context.dedup import reset_session as _dedup_reset
    from willow.context.ledger import build_resume_context as _ledger_resume_context
    _CONTEXT_AVAILABLE = True
except Exception:
    _CONTEXT_AVAILABLE = False

AGENT = require_agent_name()
# Expected layout per startup.md step 3: ~/agents/{AGENT}/index/haumana_handoffs/
INDEX_DIR = Path.home() / "agents" / AGENT / "index"
THREAD_FILE = Path("/tmp/willow-context-thread.json")
BOOT_DONE = Path(f"/tmp/willow-boot-done-{AGENT}.flag")


# ---------------------------------------------------------------------------
# Atom query helpers (used by tests and context-building paths)
# ---------------------------------------------------------------------------

_PREFERENCE_SOURCES = {"insight", "user_statement", "reflection"}
_WORLD_STATE_TYPES = {"insight", "chunk"}
_EXCLUDED_SOURCES = {"trace", "observation"}


def _query_preference_atoms(atoms: list[dict], limit: int = 10) -> list[dict]:
    """Return preference-relevant atoms: insight + user_statement sources, no invalid, capped."""
    result = [
        a for a in atoms
        if a.get("source") in _PREFERENCE_SOURCES
        and a.get("source") not in _EXCLUDED_SOURCES
        and not a.get("invalid_at")
    ]
    result.sort(key=lambda a: a.get("importance", 0), reverse=True)
    return result[:limit]


def _query_world_state_atoms(atoms: list[dict], limit: int = 10) -> list[dict]:
    """Return world-state atoms: insight + chunk types, no invalid, no traces."""
    result = [
        a for a in atoms
        if a.get("type") in _WORLD_STATE_TYPES
        and a.get("source") not in _EXCLUDED_SOURCES
        and not a.get("invalid_at")
    ]
    result.sort(key=lambda a: a.get("importance", 0), reverse=True)
    return result[:limit]


def _position_order(atoms: list[dict]) -> list[dict]:
    """Sort atoms worst-first, best-last (ascending importance × weight × stability score)."""
    def _score(a: dict) -> float:
        return a.get("importance", 0) * a.get("weight", 1.0) * a.get("stability", 1.0)

    return sorted(atoms, key=_score)


# ---------------------------------------------------------------------------

def _clear_stale_thread():
    try:
        if THREAD_FILE.exists():
            THREAD_FILE.unlink()
    except Exception:
        pass


def _scan_hardware() -> tuple[list[str], list[str]]:
    summary, alerts = [], []
    try:
        r = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,FSTYPE,SIZE,MOUNTPOINT,LABEL,TYPE"],
            capture_output=True, text=True, timeout=5
        )
        hw = json.loads(r.stdout) if r.returncode == 0 else {}
        ntfs_unmounted = []

        def _gb(s):
            s = (s or "").upper()
            if s.endswith("G"):
                return float(s[:-1])
            if s.endswith("T"):
                return float(s[:-1]) * 1024
            return 0

        def _walk(devices):
            for d in devices:
                if d.get("fstype") == "ntfs" and not d.get("mountpoint"):
                    if _gb(d.get("size", "0")) >= 10:
                        ntfs_unmounted.append(d["name"])
                if d.get("children"):
                    _walk(d["children"])

        _walk(hw.get("blockdevices", []))
        if ntfs_unmounted:
            alerts.append(f"NTFS unmounted: {', '.join(ntfs_unmounted)}")
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        (INDEX_DIR / "hardware.json").write_text(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "lsblk": hw, "ntfs_unmounted": ntfs_unmounted,
        }, indent=2))
        summary.append("drives")
    except Exception as e:
        alerts.append(f"hardware: {e}")

    try:
        zones = []
        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            try:
                temp = int((zone / "temp").read_text().strip()) / 1000
                type_ = (zone / "type").read_text().strip()
                zones.append({"zone": zone.name, "type": type_, "temp_c": round(temp, 1)})
                if temp > 85:
                    alerts.append(f"HIGH TEMP: {type_} {temp}°C")
            except Exception:
                pass
        if zones:
            peak = max(z["temp_c"] for z in zones)
            summary.append(f"{peak}°C")
            (INDEX_DIR / "thermals.json").write_text(json.dumps({
                "timestamp": datetime.now().isoformat(), "zones": zones
            }, indent=2))
    except Exception as e:
        alerts.append(f"thermals: {e}")

    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            if k.strip() in ("MemTotal", "MemAvailable"):
                mem[k.strip()] = v.strip()
        if "MemAvailable" in mem and "MemTotal" in mem:
            avail = int(mem["MemAvailable"].split()[0])
            total = int(mem["MemTotal"].split()[0])
            summary.append(f"{round(avail/total*100)}% RAM free")
        (INDEX_DIR / "memory.json").write_text(json.dumps({
            "timestamp": datetime.now().isoformat(), **mem
        }, indent=2))
    except Exception as e:
        alerts.append(f"memory: {e}")

    return summary, alerts


def _check_willow_status() -> str:
    # Try MCP subprocess first; fall back to willow.sh shell call.
    try:
        result = call("fleet_status", {"app_id": AGENT}, timeout=5)
        pg = result.get("postgres", "unknown")
        if isinstance(pg, dict):
            return "postgres=up"
    except Exception:
        pass
    try:
        repo_root = Path(__file__).parent.parent.parent.parent
        willow_sh = repo_root / "willow.sh"
        if willow_sh.exists():
            r = subprocess.run(
                ["bash", str(willow_sh), "fleet_status"],
                capture_output=True, text=True, timeout=8,
            )
            if r.returncode == 0:
                import json as _json
                data = _json.loads(r.stdout)
                if isinstance(data.get("postgres"), dict):
                    return "postgres=up"
    except Exception:
        pass
    return "postgres=unknown"


def _register_jeles(session_id: str) -> None:
    try:
        projects_dir = Path.home() / ".claude" / "projects"
        jsonl_files = list(projects_dir.rglob(f"{session_id}.jsonl"))
        if jsonl_files:
            call("willow_jeles_register", {
                "app_id": AGENT,
                "agent": AGENT,
                "jsonl_path": str(jsonl_files[0]),
                "session_id": session_id,
            }, timeout=10)
    except Exception:
        pass


DISPATCH_INBOX = Path(f"/tmp/willow-dispatch-inbox-{AGENT}.json")


def _subscribe_dispatch() -> int:
    """
    Pull #dispatch messages addressed to this agent since last cursor.
    Writes unread messages to DISPATCH_INBOX. Returns count of new messages.
    """
    cursor_file = Path(f"/tmp/willow-dispatch-cursor-{AGENT}.json")
    cursors: dict = {}
    if cursor_file.exists():
        try:
            cursors = json.loads(cursor_file.read_text())
        except Exception:
            pass
    since_id = cursors.get("dispatch", 0)
    try:
        result = _grove_call("grove_get_history", {
            "channel": "dispatch",
            "since_id": since_id,
            "limit": 50,
        }, timeout=8)
    except Exception:
        return 0

    if not isinstance(result, dict):
        return 0
    messages = result.get("messages", [])
    addressed = [
        m for m in messages
        if AGENT.lower() in m.get("content", "").lower()
        or m.get("to", "").lower() == AGENT.lower()
    ]
    last_id = max((m.get("id", 0) for m in messages), default=since_id)
    if last_id > since_id:
        cursors["dispatch"] = last_id
        try:
            cursor_file.write_text(json.dumps(cursors))
        except Exception:
            pass
    if addressed:
        try:
            DISPATCH_INBOX.write_text(json.dumps(addressed))
        except Exception:
            pass
    return len(addressed)


def _send_heartbeat() -> None:
    try:
        _grove_call("grove_heartbeat", {"sender": AGENT}, timeout=5)
    except Exception:
        pass


def _run_boot_projects_check() -> str:
    """Run boot_projects_check.py in dry-run mode. Returns compact summary string."""
    try:
        script = Path.home() / "agents" / AGENT / "bin" / "boot_projects_check.py"
        if not script.exists():
            return ""
        import subprocess as _sp
        r = _sp.run(
            [sys.executable, str(script), "--dry-run"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip()[:600] if r.returncode == 0 else ""
    except Exception:
        return ""


def _ensure_grove_mcp() -> str:
    """Check grove monitor is running via PID file. Returns status string."""
    pid_file = Path("/tmp/grove-monitor.pid")
    if not pid_file.exists():
        return "grove=down"
    try:
        pid = int(pid_file.read_text().strip())
        Path(f"/proc/{pid}").stat()
        return "grove=up"
    except Exception:
        return "grove=down"



def _open_attention_items(agent: str) -> tuple[int, list[str]]:
    """Merge open human gaps ({agent}/gaps) and open SOIL flags ({agent}/flags).

    Previously only {agent}/gaps was queried; block-telemetry flags live in
    {agent}/flags, so startup reported open_flags=0 while flat handoff showed 10+.
    """
    ranked: list[tuple[int, str]] = []

    try:
        gaps = call("store_list", {"app_id": agent, "collection": f"{agent}/gaps"}, timeout=5)
        for gap in gaps or []:
            if gap.get("status") != "open":
                continue
            title = str(gap.get("title") or gap.get("id") or "?")[:60]
            ranked.append((int(gap.get("severity") or 0), title))
    except Exception:
        pass

    try:
        flags = call("store_list", {"app_id": agent, "collection": f"{agent}/flags"}, timeout=5)
        for flag in flags or []:
            if flag.get("flag_state") != "open":
                continue
            title = str(flag.get("title") or flag.get("id") or "?")[:60]
            ranked.append((int(flag.get("severity") or flag.get("hit_count") or 0), title))
    except Exception:
        pass

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    titles = [title for _, title in ranked[:3]]
    return len(ranked), titles


def _run_silent_startup(session_id: str = "") -> dict:
    """
    Silent startup — 5 targeted MCP calls, writes session_anchor.json.
    Removed: fork_create, skill_load, knowledge_search, atoms/store, skills/store.
    """
    anchor_dir = willow_home()
    anchor_file = anchor_dir / f"session_anchor_{AGENT}.json"

    result = {
        "handoff_title": "", "handoff_summary": "",
        "handoff_threads": [], "handoff_next_bite": "",
        "open_flags": 0, "top_flags": [],
        "postgres": "unknown",
        "recent_traces": [], "next_bite": "",
        "mcp_errors": [],
    }

    # 1. Latest handoff — filename, summary, open threads, next bite
    handoff_date = ""
    try:
        h = call("handoff_latest", {"app_id": AGENT}, timeout=8)
        if isinstance(h, dict) and not h.get("error"):
            result["handoff_title"] = h.get("filename", "")
            result["handoff_summary"] = (h.get("summary") or "")[:500]
            result["handoff_threads"] = h.get("open_threads") or []
            result["handoff_next_bite"] = h.get("next_bite") or ""
            handoff_date = h.get("date", h.get("session_date", h.get("created", "")))
            if result["handoff_next_bite"] and not result["next_bite"]:
                result["next_bite"] = result["handoff_next_bite"]
    except Exception as e:
        result["mcp_errors"].append({"step": "handoff", "error": str(e)[:80]})

    # 2. Postgres health — MCP first, shell fallback
    try:
        s = call("fleet_status", {"app_id": AGENT}, timeout=5)
        if isinstance(s.get("postgres"), dict):
            result["postgres"] = "up"
    except Exception as e:
        result["mcp_errors"].append({"step": "status", "error": str(e)[:80]})
    if result["postgres"] == "unknown":
        try:
            import json as _json
            repo_root = Path(__file__).parent.parent.parent.parent
            willow_sh = repo_root / "willow.sh"
            if willow_sh.exists():
                r = subprocess.run(
                    ["bash", str(willow_sh), "fleet_status"],
                    capture_output=True, text=True, timeout=8,
                )
                if r.returncode == 0:
                    data = _json.loads(r.stdout)
                    if isinstance(data.get("postgres"), dict):
                        result["postgres"] = "up"
        except Exception:
            pass

    # 3. Next bite from session composite (same key stop.py writes)
    try:
        from willow.fylgja.events._session_store import session_composite_lookup_ids

        session = None
        for store_id in session_composite_lookup_ids(session_id):
            try:
                row = call("store_get", {
                    "app_id": AGENT,
                    "collection": f"{AGENT}/sessions",
                    "id": store_id,
                }, timeout=5)
                if isinstance(row, dict) and row and not row.get("error"):
                    session = row
                    break
            except Exception:
                continue
        if session:
            result["next_bite"] = session.get("next_bite", "")
    except Exception as e:
        result["mcp_errors"].append({"step": "session", "error": str(e)[:80]})

    # 4. Open gaps + flags (both collections — see _open_attention_items)
    try:
        count, titles = _open_attention_items(AGENT)
        result["open_flags"] = count
        result["top_flags"] = titles
    except Exception as e:
        result["mcp_errors"].append({"step": "flags", "error": str(e)[:80]})

    # 5. Recent traces since last handoff
    try:
        params: dict = {"app_id": AGENT, "collection": f"{AGENT}/turns", "query": ""}
        if handoff_date:
            params["after"] = handoff_date
        traces = call("store_search", params, timeout=5)
        result["recent_traces"] = (traces or [])[:10]
    except Exception as e:
        result["mcp_errors"].append({"step": "traces", "error": str(e)[:80]})

    # 5b. Stack snapshot — read authoritative open-state written by stop.py
    try:
        raw = call("soil_get", {
            "app_id": AGENT,
            "collection": f"{AGENT}/stack",
            "record_id": "current",
        }, timeout=5)
        snap = normalize_stack_record(raw)
        result["stack_snapshot"] = snap
        if snap:
            if not result["handoff_title"] and snap.get("handoff_title"):
                result["handoff_title"] = snap["handoff_title"]
            if snap.get("open_threads") and not result["handoff_threads"]:
                result["handoff_threads"] = snap.get("open_threads") or []
            if snap.get("open_decisions"):
                result.setdefault("stack_open_decisions", snap.get("open_decisions"))
    except Exception as e:
        result["stack_snapshot"] = {}
        result["mcp_errors"].append({"step": "stack", "error": str(e)[:80]})

    if result.get("recent_traces") and not result.get("stack_snapshot"):
        result["mcp_errors"].append({
            "step": "stack_missing",
            "error": (
                f"{len(result['recent_traces'])} recent trace(s) but no "
                f"{AGENT}/stack/current snapshot"
            )[:120],
        })

    if result["next_bite"]:
        result["handoff_summary"] = result["next_bite"][:200]
    elif result["handoff_summary"]:
        pass
    elif result["handoff_threads"]:
        result["handoff_summary"] = "Open: " + "; ".join(str(t) for t in result["handoff_threads"][:3])
    elif result["top_flags"]:
        result["handoff_summary"] = "Open: " + "; ".join(result["top_flags"])

    # 6. Corpus identity — seed + corrections + preferences (direct SOIL read)
    try:
        from core.store_port import get_store_port
        _store = get_store_port()
        _seed_rec = _store.get("corpus/seed", "seed") or {}
        _corrs = _store.all("corpus/corrections") or []
        _prefs = _store.all("corpus/preferences") or []
        _confs = _store.all("corpus/confirmations") or []
        _corrs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        _prefs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        _confs.sort(key=lambda r: r.get("last_seen", r.get("created_at", "")), reverse=True)
        human_confs = [
            r.get("content", "")
            for r in _confs
            if r.get("content")
            and str(r.get("source", "")).startswith("prompt_submit")
        ]
        from willow.fylgja.tool_denials import top_denial_lessons
        result["corpus"] = {
            "seed": _seed_rec.get("content", ""),
            "corrections": [
                excerpt_corpus(r.get("content", ""), CORRECTION_EXCERPT_CHARS)
                for r in _corrs[:MAX_CORRECTIONS]
                if r.get("content")
            ],
            "correction_total": len(_corrs),
            "preferences": [
                excerpt_corpus(r.get("content", ""), PREFERENCE_EXCERPT_CHARS)
                for r in _prefs[:MAX_PREFERENCES]
                if r.get("content")
            ],
            "preference_total": len(_prefs),
            "confirmations": [
                excerpt_corpus(c, CONFIRMATION_EXCERPT_CHARS)
                for c in human_confs[:MAX_HUMAN_CONFIRMATIONS]
            ],
            "confirmation_total": len(human_confs),
            "tool_denials": [
                excerpt_corpus(lesson, DENIAL_EXCERPT_CHARS)
                for lesson in top_denial_lessons(_store, limit=MAX_TOOL_DENIALS)
            ],
        }
    except Exception:
        result["corpus"] = {
            "seed": "",
            "preferences": [],
            "corrections": [],
            "confirmations": [],
            "tool_denials": [],
        }

    # Flat handoff — read most recent file and verify anchor against JSONL
    flat: dict = {}
    try:
        from willow.fylgja.handoff_flat import read_flat_handoff, verify_anchor
        flat = read_flat_handoff(AGENT)
        if flat.get("anchor") and flat.get("jsonl_path"):
            flat["verified"] = verify_anchor(flat["anchor"], flat["jsonl_path"])
        else:
            flat["verified"] = False
    except Exception:
        flat = {}
    result["flat_handoff"] = flat

    # Open Run Ledger row — enables PMEM1 trace writes for this session.
    run_id = _open_run()

    # Write anchor cache
    try:
        anchor_dir.mkdir(parents=True, exist_ok=True)
        anchor_file.write_text(json.dumps({
            "written_at": datetime.now().isoformat(),
            "agent": AGENT,
            "postgres": result["postgres"],
            "handoff_title": result["handoff_title"],
            "handoff_summary": result["handoff_summary"],
            "handoff_threads": result["handoff_threads"],
            "handoff_next_bite": result["handoff_next_bite"],
            "open_flags": result["open_flags"],
            "top_flags": result["top_flags"],
            "next_bite": result["next_bite"],
            "trace_count": len(result["recent_traces"]),
            "mcp_degraded": len(result["mcp_errors"]) > 0,
            "mcp_last_error": result["mcp_errors"][-1] if result["mcp_errors"] else None,
            "run_id": run_id,
            "flat_handoff_verified": flat.get("verified", False),
        }, indent=2))
    except Exception:
        pass

    return result


def _open_run() -> str | None:
    """Open a Run Ledger row for this session. Returns run_id or None on failure."""
    try:
        import psycopg2
        db = os.environ.get("WILLOW_PG_DB", "willow_20")
        user = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
        conn = psycopg2.connect(dbname=db, user=user)
        conn.autocommit = True
        with conn.cursor() as cur:
            # Close any stale running rows for this agent first (crash recovery)
            cur.execute(
                "UPDATE willow.runs SET status='abandoned', ended_at=now()"
                " WHERE initiator=%s AND status='running'",
                (AGENT,),
            )
            cur.execute(
                "INSERT INTO willow.runs (initiator, purpose, status)"
                " VALUES (%s, %s, 'running') RETURNING id",
                (AGENT, f"{AGENT} session"),
            )
            run_id = str(cur.fetchone()[0])
        conn.close()
        return run_id
    except Exception:
        return None


def _claude_memory_dir() -> Path | None:
    """Resolve Claude Code project memory dir for the open repo (runtime-specific)."""
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        return None
    repo_name = repo_root().name.lower()
    for entry in sorted(projects.iterdir()):
        if not entry.is_dir():
            continue
        slug = entry.name.lower().lstrip("-")
        if repo_name.replace("-", "") in slug.replace("-", ""):
            memory = entry / "memory"
            if memory.is_dir():
                return memory
    return None


def _seed_corpus_corrections() -> None:
    """Populate corpus/corrections from memory feedback_*.md files (idempotent).

    The feedback files are the canonical source of behavioral corrections but
    corpus/corrections (read by session_start at boot) was never populated.
    This runs once per session; soil_put is idempotent by key so re-runs are safe.
    """
    memory_dir = _claude_memory_dir()
    if memory_dir is None:
        return

    try:
        from core.store_port import get_store_port
        store = get_store_port()
    except Exception:
        return

    for fpath in sorted(memory_dir.glob("feedback_*.md")):
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
            # Extract rule: first non-blank line after frontmatter (after second ---)
            body = text.split("---", 2)[-1].strip() if "---" in text else text.strip()
            # First substantive line is the rule
            rule = ""
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("@"):
                    rule = line[:200]
                    break
            if not rule:
                continue
            record_id = fpath.stem  # e.g. "feedback_no_direct_db"
            # Check if already seeded
            existing = store.get("corpus/corrections", record_id)
            if existing:
                continue
            store.put("corpus/corrections", {
                "id": record_id,
                "content": rule,
                "source": str(fpath.name),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sandbox": False,
            }, record_id=record_id)
        except Exception:
            continue


def _is_isolated_directory() -> bool:
    """Return True if CWD lacks the willow MCP server — skip all fleet hooks."""
    mcp = Path.cwd() / ".mcp.json"
    try:
        data = json.loads(mcp.read_text())
        return "willow" not in data.get("mcpServers", {})
    except Exception:
        return False


def main():
    if _is_isolated_directory():
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    session_id = data.get("session_id", "")
    session_source = data.get("source", "startup")  # startup | resume | clear | compact
    lite_inject = is_continuation_source(session_source)

    if is_fresh_source(session_source):
        reset_prompt_count(AGENT)

    # Reset dedup tracker for the new session
    if _CONTEXT_AVAILABLE:
        try:
            _dedup_reset()
        except Exception:
            pass

    _clear_stale_thread()
    if is_fresh_source(session_source):
        reset_turn_count()  # fresh session — boot guard must fire exactly once
        BOOT_DONE.unlink(missing_ok=True)
    grove_status = _ensure_grove_mcp()  # instant local file check
    if session_id:
        _register_jeles(session_id)

    # Seed corpus/corrections from memory feedback files (idempotent)
    try:
        _seed_corpus_corrections()
    except Exception:
        pass

    # Ensure hook_registry has built-in hooks (edge_linking, stop_slow, shutdown, …)
    try:
        from willow.hooks.registry import seed_builtin_hooks
        seed_builtin_hooks()
    except Exception:
        pass

    # Ensure fleet agent intake dirs exist for norn-pass promotion parity
    try:
        from core.intake import ensure_fleet_intake_dirs
        ensure_fleet_intake_dirs()
    except Exception:
        pass

    with _cf.ThreadPoolExecutor(max_workers=5) as ex:
        hw_future = ex.submit(_scan_hardware)
        startup_future = ex.submit(_run_silent_startup, session_id)
        ex.submit(_send_heartbeat)
        dispatch_future = ex.submit(_subscribe_dispatch)
        projects_future = ex.submit(_run_boot_projects_check)

    summary, alerts = hw_future.result()
    summary.append(grove_status)
    dispatch_count = dispatch_future.result()
    if dispatch_count:
        summary.append(f"dispatch={dispatch_count}")

    startup = startup_future.result()
    projects_summary = projects_future.result()
    summary.append(f"postgres={startup['postgres']}")

    lines = ["[INDEX] " + " · ".join(summary)]
    for a in alerts:
        lines.append(f"  ⚠ {a}")

    # Anchor context — always injected
    lines.append("[ANCHOR]")
    lines.append(f"agent={AGENT}  postgres={startup['postgres']}")
    lines.append(
        "[MCP-FIRST] Use Willow MCP tools — not PYTHONPATH= python, not psql/sqlite3 Bash. "
        "Shell work → agent_task_submit + kart_task_run. Registry: sap/mcp_registry.json."
    )
    lines.append(
        f"[IDENTITY] You are {AGENT}. The IDE/CLI model is transport only — not your name. "
        "Do not route all fleet work to hanuman; use agent_route then agent_dispatch(to=…). "
        f"Postgres dispatch_tasks.from_agent must be {AGENT}."
    )

    try:
        from willow.fylgja.persona import anchor_lines as _persona_lines

        if not lite_inject:
            lines.append(_persona_lines())
    except Exception:
        pass

    if not lite_inject:
        try:
            from willow.fylgja.cross_runtime import anchor_lines as _cross_runtime_lines

            lines.extend(_cross_runtime_lines(max_open=MAX_CROSS_RUNTIME_OPEN))
        except Exception:
            pass

    # Flat handoff — verified ground truth takes priority over MCP handoff prose
    flat = startup.get("flat_handoff", {})
    if flat.get("written_at"):
        verified = flat.get("verified", False)
        status = "verified" if verified else "UNVERIFIED"
        lines.append(f"flat handoff: {flat['written_at'][:10]} [{status}]")
        if not verified and flat.get("anchor"):
            lines.append("  ⚠ anchor not found in JSONL — handoff may be stale or fabricated")
        if flat.get("open_gates"):
            lines.append(f"open gates: {len(flat['open_gates'])}")
            for g in flat["open_gates"][:3]:
                lines.append(f"  · {g}")
    elif startup["handoff_title"]:
        lines.append(f"last handoff: {startup['handoff_title']}")

    if startup.get("handoff_threads") or startup.get("handoff_summary"):
        lines.append("[HANDOFF]")
        if startup.get("handoff_summary"):
            lines.append(f"  {startup['handoff_summary'][:200]}")
        for th in startup.get("handoff_threads", [])[:5]:
            lines.append(f"  · {str(th)[:100]}")
        if startup.get("handoff_next_bite"):
            lines.append(f"  NEXT: {startup['handoff_next_bite'][:160]}")

    traces = startup.get("recent_traces", [])
    if traces:
        trace_summaries = [t.get("summary", t.get("tool", "?"))[:40] for t in traces[:3]]
        lines.append(f"recent traces ({len(traces)}): " + " · ".join(trace_summaries))
    if startup["open_flags"]:
        lines.append(f"open gaps: {startup['open_flags']}")
        for flag in startup["top_flags"][:2]:
            lines.append(f"  · {flag}")
    corpus = startup.get("corpus", {})
    if corpus.get("seed"):
        lines.append(f"why: {corpus['seed'][:120]}")
    if corpus.get("corrections"):
        cap = MAX_CORRECTIONS if not lite_inject else min(2, MAX_CORRECTIONS)
        shown = corpus["corrections"][:cap]
        if shown:
            total = int(corpus.get("correction_total") or len(corpus["corrections"]))
            head = f"corrections — operator ({len(shown)}"
            if total > len(shown):
                head += f"/{total}"
            head += "):"
            lines.append(head)
            for c in shown:
                lines.append(f"  · {c}")
    if corpus.get("preferences"):
        cap = MAX_PREFERENCES if not lite_inject else min(2, MAX_PREFERENCES)
        shown = corpus["preferences"][:cap]
        if shown:
            total = int(corpus.get("preference_total") or len(corpus["preferences"]))
            head = f"preferences — operator ({len(shown)}"
            if total > len(shown):
                head += f"/{total}"
            head += "):"
            lines.append(head)
            for p in shown:
                lines.append(f"  · {p}")
    if corpus.get("confirmations"):
        cap = MAX_HUMAN_CONFIRMATIONS if not lite_inject else 1
        shown = corpus["confirmations"][:cap]
        if shown:
            total = int(corpus.get("confirmation_total") or len(corpus["confirmations"]))
            head = f"confirmations — operator ({len(shown)}"
            if total > len(shown):
                head += f"/{total}"
            head += "):"
            lines.append(head)
            for c in shown:
                lines.append(f"  · {c}")
    if corpus.get("tool_denials"):
        # Automated lane — fewer slots; never crowd out human corrections above.
        cap = MAX_TOOL_DENIALS if not lite_inject else 0
        shown = corpus["tool_denials"][:cap]
        if shown:
            lines.append(
                f"learned denials — automated ({len(corpus['tool_denials'])}); "
                "defer to operator corrections when they conflict:"
            )
            for lesson in shown:
                lines.append(f"  · {lesson}")

    # Stack snapshot — inject open tasks + open decisions from last stop hook write
    snap = startup.get("stack_snapshot", {})
    if snap:
        snap_tasks = snap.get("open_tasks", [])
        snap_threads = snap.get("open_threads", [])
        snap_decisions = snap.get("open_decisions", [])
        snap_ts = snap.get("written_at", "")[:16]
        if snap_tasks or snap_threads or snap_decisions:
            lines.append(f"[STACK] as of {snap_ts}:")
            for t in snap_tasks[:5]:
                lines.append(f"  task: {t.get('title', t.get('id', '?'))[:80]}")
            for th in snap_threads[:3]:
                lines.append(f"  thread: {str(th)[:80]}")
            for d in snap_decisions[:3]:
                lines.append(f"  decision pending: {str(d)[:80]}")

    if startup.get("next_bite"):
        lines.append(f"NEXT: {startup['next_bite']}")
    elif startup["handoff_summary"]:
        lines.append(startup["handoff_summary"])

    if not lite_inject and projects_summary:
        lines.append("")
        lines.append("[PROJECTS]")
        lines.append(projects_summary)
    if not lite_inject:
        grove_pid_file = Path("/tmp/grove-monitor.pid")
        grove_log_file = Path("/tmp/grove-monitor.log")
        # The LISTEN/NOTIFY monitor is considered active when its pidfile exists.
        # Logs are expected at /tmp/grove-monitor.log (typically via systemd redirect),
        # but we key off pid to avoid a chicken/egg with file creation timing.
        if grove_pid_file.exists() and grove_log_file.exists():
            lines.append(
                "GROVE MONITOR: active — "
                "Monitor(description='Grove mentions', persistent=True, "
                "command='tail -n +1 -f /tmp/grove-monitor.log | grep --line-buffered \"\\[MENTION\\]\"')"
            )
        elif grove_pid_file.exists():
            lines.append(
                "GROVE MONITOR: pid active but log missing at /tmp/grove-monitor.log "
                "(check systemd unit StandardOutput= path)"
            )
    if startup["postgres"] == "unknown":
        lines.append("BOOT DEGRADED — invoke /startup before responding to anything.")

    # Ledger resume context — inject on compact/resume so decisions survive compaction
    if _CONTEXT_AVAILABLE and session_source in ("compact", "resume", "clear"):
        try:
            ledger_ctx = _ledger_resume_context()
            if ledger_ctx:
                lines.append("")
                lines.append(ledger_ctx)
        except Exception:
            pass

    if lite_inject:
        lines.append("[SESSION] compact/resume — trimmed boot injection.")

    fingerprint = dedup_fingerprint(session_id, lines)
    if should_skip_duplicate(session_id, fingerprint):
        lines = minimal_continuation_block(
            AGENT,
            startup["postgres"],
            startup.get("next_bite") or startup.get("handoff_next_bite", ""),
        )
        record_injection(session_id, fingerprint, lite=True)
    else:
        record_injection(session_id, fingerprint, lite=lite_inject)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
