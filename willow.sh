#!/usr/bin/env bash
# willow.sh — Willow 2.0 launcher
# b17: WLW20 · ΔΣ=42
#
# Usage:
#   ./willow.sh              — start SAP MCP server (stdio)
#   ./willow.sh status       — check Postgres + metabolic socket
#   ./willow.sh fleet_status — check full boot health without MCP
#   ./willow.sh handoff_latest [agent] — show latest handoff summary
#   ./willow.sh agents [list|active|install|check] — agent IDE wiring + MCP rails
#   ./willow.sh metabolic    — run Norn pass now
#   ./willow.sh update       — check for updates and apply if available
#   ./willow.sh export       — dump user data to $WILLOW_HOME/export.json
#   ./willow.sh purge <proj> — delete a project namespace entirely
#   ./willow.sh ledger [proj] — show FRANK's ledger (optional project filter)
#   ./willow.sh valhalla     — collect DPO training pairs to $WILLOW_HOME/valhalla/
#   ./willow.sh verify       — verify SAFE Applications + Agents manifests (.sig)

set -euo pipefail

WILLOW_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
export WILLOW_ROOT
SAP_MCP="${WILLOW_ROOT}/sap/sap_mcp.py"

# ── Canonical fleet home ($WILLOW_HOME) — resolved after Python is located ───────
WILLOW_HOME_FALLBACK="${HOME}/github/.willow"

# Python
if [[ -z "${WILLOW_PYTHON:-}" ]]; then
    if [[ -x "${WILLOW_ROOT}/.venv-dev/bin/python3" ]]; then
        WILLOW_PYTHON="${WILLOW_ROOT}/.venv-dev/bin/python3"
    elif [[ -x "${HOME}/github/willow-2.0/.venv-dev/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/github/willow-2.0/.venv-dev/bin/python3"
    elif [[ -n "${WILLOW_HOME:-}" && -x "${WILLOW_HOME}/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${WILLOW_HOME}/venv/bin/python3"
    elif [[ -x "${WILLOW_HOME_FALLBACK}/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${WILLOW_HOME_FALLBACK}/venv/bin/python3"
    elif [[ -x "${HOME}/.willow/venv/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/.willow/venv/bin/python3"
    elif [[ -x "${HOME}/.willow-venv/bin/python3" ]]; then
        WILLOW_PYTHON="${HOME}/.willow-venv/bin/python3"
    else
        WILLOW_PYTHON="$(command -v python3)"
    fi
fi
export WILLOW_PYTHON

if [[ -z "${WILLOW_HOME:-}" ]]; then
    WILLOW_HOME="$("${WILLOW_PYTHON}" -c "
import sys
from pathlib import Path
sys.path.insert(0, '${WILLOW_ROOT}')
from willow.fylgja.willow_home import fleet_home
print(fleet_home(Path('${WILLOW_ROOT}')))
" 2>/dev/null)" || WILLOW_HOME="${WILLOW_HOME_FALLBACK}"
fi
export WILLOW_HOME
export WILLOW_STORE_ROOT="${WILLOW_STORE_ROOT:-${WILLOW_HOME}/store}"
export WILLOW_VAULT="${WILLOW_VAULT:-${WILLOW_HOME}/secrets/.willow_creds.db}"
export WILLOW_SAFE_ROOT="${WILLOW_SAFE_ROOT:-${HOME}/github/SAFE/Applications}"
export WILLOW_AGENTS_ROOT="${WILLOW_AGENTS_ROOT:-${HOME}/github/SAFE/Agents}"
export WILLOW_PGP_FINGERPRINT="${WILLOW_PGP_FINGERPRINT:-9B6F87BEB4AE56E23D3D055724AED1D0216053F5}"

# Postgres — Unix socket, willow_20 DB (clean break from 1.7)
unset WILLOW_PG_HOST WILLOW_PG_PORT WILLOW_PG_PASS
export WILLOW_PG_DB="${WILLOW_PG_DB:-willow_20}"
export WILLOW_PG_USER="${WILLOW_PG_USER:-$(whoami)}"
ACTIVE_AGENT_FILE="${WILLOW_ROOT}/.willow/active-agent"
ACTIVE_AGENT=""
if [[ -f "${ACTIVE_AGENT_FILE}" ]]; then
    ACTIVE_AGENT="$(tr -d '[:space:]' < "${ACTIVE_AGENT_FILE}")"
fi
if [[ -n "${ACTIVE_AGENT}" ]]; then
    WILLOW_AGENT_NAME="${ACTIVE_AGENT}"
elif [[ -z "${WILLOW_AGENT_NAME:-}" ]]; then
    WILLOW_AGENT_NAME="hanuman"
fi
export WILLOW_AGENT_NAME
# Fleet launcher follows active agent — do not inherit stale human Grove handles from profile.
export GROVE_SENDER="${WILLOW_AGENT_NAME}"
export GROVE_NAME="${WILLOW_AGENT_NAME}"

# User-systemd services surfaced by start-all/stop-all/status-all. Keep this as
# the single inventory so restart hygiene does not drift between commands.
WILLOW_SYSTEMD_SERVICES=(
    grove-mcp
    grove-serve
    willow-grove-listen
    upstream-watcher
    journal-watcher
    journal-responder
    willow-dashboard
    willow-metabolic
    corpus-watcher
    willow-discord-responder
    kart-worker
    orin-worker
    willow-mcp
    nest-watcher
    drop-server
)

WILLOW_STOP_SERVICES=(
    willow-dashboard
    corpus-watcher
    journal-responder
    journal-watcher
    upstream-watcher
    willow-discord-responder
    willow-grove-listen
    grove-mcp
    grove-serve
    willow-metabolic
    kart-worker
    orin-worker
    willow-mcp
    nest-watcher
    drop-server
)

_willow_service_note() {
    case "$1" in
        journal-responder)
            echo "helper; spawned by journal-watcher per entry"
            ;;
        corpus-watcher)
            echo "missing local unit/script; human-start only when restored"
            ;;
        willow-metabolic)
            echo "timer/socket capable; service is oneshot"
            ;;
        *)
            echo ""
            ;;
    esac
}

_willow_unit_file_exists() {
    [[ -f "${WILLOW_ROOT}/systemd/${1}.service" ]]
}

_willow_user_unit_known() {
    systemctl --user list-unit-files "${1}.service" --no-legend 2>/dev/null | grep -q .
}

# ── LLM provider keys — uncomment whichever is active ────────────────────────
# export ANTHROPIC_API_KEY=""
# export GROQ_API_KEY=""  # set in local env, not committed

# Python path — willow-2.0 first, no legacy paths
export PYTHONPATH="${WILLOW_ROOT}:${PYTHONPATH:-}"

_willow_sync_version() {
    local repo_ver=""
    if [[ -f "${WILLOW_ROOT}/VERSION" ]]; then
        repo_ver="$(tr -d '[:space:]' < "${WILLOW_ROOT}/VERSION")"
    fi
    [[ -z "${repo_ver}" ]] && return
    mkdir -p "${WILLOW_HOME}"
    echo "${repo_ver}" > "${WILLOW_HOME}/version"
}

_willow_installed_version() {
    _willow_sync_version
    cat "${WILLOW_HOME}/version" 2>/dev/null || echo "not installed"
}

# Jeles trusted sources registry — 54 sources from Loki audit (atom 44A246FD)
export JELES_SOURCES_FILE="${HOME}/Desktop/sources.json"

cmd="${1:-start}"

case "$cmd" in
    start|"")
        exec "${WILLOW_PYTHON}" "${SAP_MCP}"
        ;;

    status)
        echo "Willow 2.0 — status"
        echo "  Store:    ${WILLOW_STORE_ROOT}"
        echo "  Vault:    ${WILLOW_VAULT}"
        echo "  Version:  $(_willow_installed_version)"
        "${WILLOW_PYTHON}" -c "
import sys, os
sys.path.insert(0, '${WILLOW_ROOT}')
os.environ['WILLOW_PG_DB'] = '${WILLOW_PG_DB}'
from core.pg_bridge import try_connect
pg = try_connect()
print('  Postgres:', 'connected' if pg else 'NOT CONNECTED')
if pg: pg.close()
"
        systemctl --user is-active willow-metabolic.socket 2>/dev/null \
            && echo "  Metabolic socket: active" \
            || echo "  Metabolic socket: inactive"
        systemctl --user is-active willow-metabolic.timer 2>/dev/null \
            && echo "  Metabolic timer:  active" \
            || echo "  Metabolic timer:  inactive"
        "${WILLOW_PYTHON}" -c "
import json, sys
sys.path.insert(0, '${WILLOW_ROOT}')
from core.metabolic_status import check_metabolic_status
m = check_metabolic_status()
print('  Last briefing:', m.get('last_briefing') or 'none')
print('  Consecrated:', m.get('consecrated'))
" 2>/dev/null || true
        ;;

    fleet_status)
        _willow_sync_version
        WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import json, os, sys
import urllib.request
from pathlib import Path
sys.path.insert(0, '${WILLOW_ROOT}')
from core.willow_store import WillowStore
from core.pg_bridge import PgBridge, try_connect
from sap.core.gate import SAFE_ROOT, PROFESSOR_ROOT, _verify_pgp

store = WillowStore(os.environ['WILLOW_STORE_ROOT'])
local_stats = store.stats() or {}
local_count = sum(s.get('count', 0) for s in local_stats.values())

conn = try_connect()
pg_stats = {}
if conn:
    conn.close()
    try:
        pg = PgBridge()
        if hasattr(pg, 'stats'):
            pg_stats = pg.stats() or {}
    except Exception:
        pg_stats = {}

try:
    url = os.environ.get('OLLAMA_URL', 'http://localhost:11434') + '/api/tags'
    with urllib.request.urlopen(url, timeout=2) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    ollama = {'running': True, 'models': [m.get('name') for m in payload.get('models', []) if m.get('name')]}
except Exception:
    ollama = {'running': False}

manifest_paths = list(SAFE_ROOT.glob('*/safe-app-manifest.json')) + list(PROFESSOR_ROOT.glob('*/safe-app-manifest.json'))
passed = 0
failed = []
for manifest_path in manifest_paths:
    ok, _reason = _verify_pgp(manifest_path)
    if ok:
        passed += 1
    else:
        failed.append(manifest_path.parent.name)

result = {
    'local_store': {'collections': len(local_stats), 'records': local_count},
    'postgres': pg_stats if pg_stats else ('not_connected' if conn is None else 'connected'),
    'ollama': ollama,
    'manifests': {'pass': passed, 'fail': len(failed), **({'failed': failed} if failed else {})},
    'mode': 'portless',
}
print(json.dumps(result, indent=2))
"
        ;;

    handoff_latest)
        shift
        exec "${WILLOW_PYTHON}" -m sap.handoff_cli "$@"
        ;;

    metabolic)
        echo "Willow 2.0 — running Norn pass"
        WILLOW_PG_DB="${WILLOW_PG_DB}" exec "${WILLOW_PYTHON}" "${WILLOW_ROOT}/core/metabolic.py"
        ;;

    w8-census)
        echo "Willow 2.0 — W8 canonical reconstruction census witness"
        WILLOW_PG_DB="${WILLOW_PG_DB}" exec "${WILLOW_PYTHON}" "${WILLOW_ROOT}/scripts/w8_census_witness.py"
        ;;

    wce)
        echo "Willow 2.0 — WCE weekly continuity eval witness"
        shift
        WILLOW_PG_DB="${WILLOW_PG_DB}" exec "${WILLOW_PYTHON}" "${WILLOW_ROOT}/scripts/wce_witness.py" --check-first "$@"
        ;;

    bridge-cross-runtime)
        echo "Willow 2.0 — rebuild cross-runtime handoff bridge"
        shift
        WILLOW_PG_DB="${WILLOW_PG_DB}" exec "${WILLOW_PYTHON}" "${WILLOW_ROOT}/scripts/bridge_cross_runtime.py" "$@"
        ;;

    kart-worker)
        echo "Willow 2.0 — starting Kart worker"
        exec "${WILLOW_PYTHON}" "${WILLOW_ROOT}/scripts/run_kart.py"
        ;;

    exec-python)
        shift
        [[ $# -gt 0 ]] || { echo "Usage: willow.sh exec-python <script-or--module> [args...]" >&2; exit 1; }
        exec "${WILLOW_PYTHON}" "$@"
        ;;

    update)
        echo "Willow 2.0 — checking for updates"
        CURRENT=$(cat "${WILLOW_HOME}/version" 2>/dev/null || echo "unknown")
        LATEST=$(curl -s --max-time 5 \
            "https://api.github.com/repos/rudi193-cmd/willow-2.0/releases/latest" \
            2>/dev/null | "${WILLOW_PYTHON}" -c \
            "import json,sys; d=json.load(sys.stdin); print(d.get('tag_name','unknown'))" \
            2>/dev/null || echo "unknown")
        echo "  Current: ${CURRENT}  Latest: ${LATEST}"
        if [[ "${CURRENT}" == "${LATEST}" || "${LATEST}" == "unknown" ]]; then
            echo "  Already up to date."
            exit 0
        fi
        echo "  Updating..."
        git -C "${WILLOW_ROOT}" pull origin master
        "${WILLOW_PYTHON}" "${WILLOW_ROOT}/root.py" --skip-gpg
        echo "  Update complete. Version: $(cat "${WILLOW_HOME}/version")"
        ;;

    export)
        echo "Willow 2.0 — exporting user data to ${WILLOW_HOME}/export.json"
        WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import sys, json, os
sys.path.insert(0, '${WILLOW_ROOT}')
os.environ['WILLOW_PG_DB'] = '${WILLOW_PG_DB}'
from core.willow_store import WillowStore
store = WillowStore()
data = {'store': {}}
for col in store.collections():
    data['store'][col] = store.list(col)
output = os.path.join(os.environ['WILLOW_HOME'], 'export.json')
with open(output, 'w') as f:
    json.dump(data, f, indent=2, default=str)
print(f'  Exported to {output}')
print(f'  Collections: {len(data[\"store\"])}')
"
        ;;

    purge)
        PROJECT="${2:-}"
        if [[ -z "${PROJECT}" ]]; then
            echo "Usage: willow.sh purge <project>"
            exit 1
        fi
        echo "  Purging project namespace: ${PROJECT}"
        echo "  This deletes all KB edges, atoms, and community nodes for ${PROJECT}."
        read -rp "  Type the project name to confirm: " CONFIRM
        if [[ "${CONFIRM}" != "${PROJECT}" ]]; then
            echo "  Cancelled."
            exit 0
        fi
        PURGE_PROJECT="${PROJECT}" WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import sys, os
sys.path.insert(0, '${WILLOW_ROOT}')
from core.pg_bridge import PgBridge
project = os.environ['PURGE_PROJECT']
bridge = PgBridge()
with bridge.conn.cursor() as cur:
    cur.execute('DELETE FROM knowledge WHERE project = %s', (project,))
    count = cur.rowcount
bridge.conn.commit()
print(f'  Deleted {count} KB edges for project: {project}')
"
        ;;

    ledger)
        echo "Willow 2.0 — FRANK's Ledger"
        LEDGER_PROJECT="${2:-}"
        LEDGER_PROJECT="${LEDGER_PROJECT}" WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import sys, os, json
sys.path.insert(0, '${WILLOW_ROOT}')
from core.pg_bridge import PgBridge
bridge = PgBridge()
project = os.environ.get('LEDGER_PROJECT') or None
entries = bridge.ledger_read(project=project, limit=20)
result = bridge.ledger_verify()
print(f'  Chain: {\"VALID\" if result[\"valid\"] else \"BROKEN\"}  Entries: {result[\"count\"]}')
print()
for e in entries:
    ts = e['created_at'].strftime('%Y-%m-%d %H:%M') if hasattr(e['created_at'], 'strftime') else str(e['created_at'])[:16]
    content = e.get('content') or {}
    note = content.get('note', json.dumps(content)[:60])
    print(f'  [{ts}] {e[\"project\"]:20s} {e[\"event_type\"]:15s} {note}')
"
        ;;

    backup)
        echo "Willow 2.0 — backup"
        WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import sys, os, json
sys.path.insert(0, '${WILLOW_ROOT}')
from core.backup import create_backup
backup_path = create_backup(pg_db='${WILLOW_PG_DB}')
manifest = json.loads((backup_path.parent / 'manifest.json').read_text())
print(f'  Backup:   {backup_path.parent}')
print(f'  Version:  {manifest[\"version\"]}')
print(f'  Postgres: {\"included\" if manifest[\"pg_included\"] else \"not included (pg_dump unavailable)\"}')
print()
print('  Snorri Sturluson would approve.')
"
        ;;

    restore)
        BACKUP_PATH="${2:-}"
        if [[ -z "${BACKUP_PATH}" ]]; then
            echo "Usage: willow.sh restore <path-to-backup-directory>"
            echo "Backups live at: ${WILLOW_HOME}/backups/"
            exit 1
        fi
        echo "  Restoring from: ${BACKUP_PATH}"
        read -rp "  This overwrites ${WILLOW_HOME}/. Type OVERWRITE MY DATA to proceed: " CONFIRM
        if [[ "${CONFIRM}" != "OVERWRITE MY DATA" ]]; then
            echo "  Cancelled."
            exit 0
        fi
        RESTORE_PATH="${BACKUP_PATH}" WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import sys, os
sys.path.insert(0, '${WILLOW_ROOT}')
from core.backup import restore_backup
from pathlib import Path
restore_backup(Path(os.environ['RESTORE_PATH']), pg_db='${WILLOW_PG_DB}')
print('  Restore complete.')
"
        ;;

    nuke)
        echo ""
        echo "  ╔══════════════════════════════════════════════════════════╗"
        echo "  ║                  W I L L O W   N U K E                  ║"
        echo "  ╠══════════════════════════════════════════════════════════╣"
        echo "  ║                                                          ║"
        echo "  ║  Deletes ${WILLOW_HOME}/ — your local Willow data folder. ║"
        echo "  ║                                                          ║"
        echo "  ║  What will be destroyed:                                 ║"
        echo "  ║    • Your API keys (vault)                               ║"
        echo "  ║    • Your GPG master key                                 ║"
        echo "  ║    • Local SOIL SQLite store (\$WILLOW_HOME/store/)       ║"
        echo "  ║    • All local backups (\$WILLOW_HOME/backups/)          ║"
        echo "  ║    • Your telemetry preferences                          ║"
        echo "  ║    • Version pin and session logs                        ║"
        echo "  ║                                                          ║"
        echo "  ║  What will NOT be touched:                               ║"
        echo "  ║    • The software (this repo stays)                      ║"
        echo "  ║    • ~/SAFE/Applications/ (your SAFE folder)             ║"
        echo "  ║    • The willow_20 Postgres database                     ║"
        echo "  ║      (knowledge, ledger, CMB atom live there)            ║"
        echo "  ║      To also wipe Postgres: dropdb willow_20             ║"
        echo "  ║                                                          ║"
        echo "  ║  There is no undo. There is no recovery.                ║"
        echo "  ║  Run 'willow backup' first if you want a copy.          ║"
        echo "  ║                                                          ║"
        echo "  ╚══════════════════════════════════════════════════════════╝"
        echo ""
        read -rp "  Type DELETE MY DATA to proceed (anything else cancels): " CONFIRM
        if [[ "${CONFIRM}" != "DELETE MY DATA" ]]; then
            echo ""
            echo "  Cancelled. Nothing was deleted."
            exit 0
        fi
        echo ""
        echo "  Deleting ${WILLOW_HOME}/ ..."
        rm -rf "${WILLOW_HOME}/"
        echo "  Done."
        echo ""
        echo "  Your data is gone. The software remains."
        echo "  Run python3 root.py to start fresh."
        echo ""
        ;;

    valhalla)
        echo "Willow 2.0 — Valhalla collection"
        echo "  Scanning KB for DPO pair candidates..."
        WILLOW_PG_DB="${WILLOW_PG_DB}" "${WILLOW_PYTHON}" -c "
import sys, os
sys.path.insert(0, '${WILLOW_ROOT}')
os.environ['WILLOW_PG_DB'] = '${WILLOW_PG_DB}'
from core.pg_bridge import PgBridge
from core.willow_store import WillowStore
from core.valhalla import collect_dpo_pairs
bridge = PgBridge()
store = WillowStore()
count = collect_dpo_pairs(bridge, store)
print(f'  Pairs collected: {count}')
print(f'  Output: {os.environ[\"WILLOW_HOME\"]}/valhalla/dpo_pairs.jsonl')
print()
print('  The Einherjar grow stronger.')
"
        ;;

    verify)
        echo "Willow 2.0 — manifest verification"
        pass=0; fail=0
        for SAFE_ROOT in "${WILLOW_SAFE_ROOT}" "${WILLOW_AGENTS_ROOT}"; do
            echo "  Root: ${SAFE_ROOT}"
            for manifest in "${SAFE_ROOT}"/*/safe-app-manifest.json; do
                [[ -f "$manifest" ]] || continue
                sig="${manifest}.sig"
                label="$(basename "$(dirname "$manifest")")"
                if [[ ! -f "$sig" ]]; then
                    echo "    MISSING SIG: ${label}"; fail=$((fail+1))
                elif gpg --verify "$sig" "$manifest" > /dev/null 2>&1; then
                    echo "    OK: ${label}"; pass=$((pass+1))
                else
                    echo "    BAD SIG: ${label}"; fail=$((fail+1))
                fi
            done
        done
        echo "  Passed: ${pass}  Failed: ${fail}"
        [[ $fail -eq 0 ]]
        ;;

    start-all)
        echo "Willow 2.0 — starting all services"
        for svc in "${WILLOW_SYSTEMD_SERVICES[@]}"; do
            note="$(_willow_service_note "${svc}")"
            if [[ -n "${note}" ]]; then
                if ! _willow_user_unit_known "${svc}" && ! _willow_unit_file_exists "${svc}"; then
                    echo "  [–] ${svc} skipped (${note})"
                    continue
                fi
            fi
            if systemctl --user is-active --quiet "${svc}.service" 2>/dev/null; then
                echo "  [✓] ${svc} already running"
            else
                systemctl --user start "${svc}.service" 2>/dev/null \
                    && echo "  [↑] ${svc} started" \
                    || echo "  [✗] ${svc} failed to start"
            fi
        done
        echo ""
        echo "  Note: sap_mcp.py is spawned by Claude Code only — not managed here."
        ;;

    stop-all)
        echo "Willow 2.0 — stopping all services"
        for svc in "${WILLOW_STOP_SERVICES[@]}"; do
            if ! _willow_user_unit_known "${svc}" && ! _willow_unit_file_exists "${svc}"; then
                note="$(_willow_service_note "${svc}")"
                if [[ -n "${note}" ]]; then
                    echo "  [–] ${svc} skipped (${note})"
                fi
                continue
            fi
            systemctl --user stop "${svc}.service" 2>/dev/null \
                && echo "  [↓] ${svc} stopped" \
                || echo "  [–] ${svc} was not running"
        done
        ;;

    status-all)
        echo "Willow 2.0 — system status"
        echo ""

        # Postgres
        "${WILLOW_PYTHON}" -c "
import sys, os
sys.path.insert(0, '${WILLOW_ROOT}')
os.environ['WILLOW_PG_DB'] = '${WILLOW_PG_DB}'
from core.pg_bridge import try_connect
pg = try_connect()
if pg:
    cur = pg.cursor()
    cur.execute('SELECT COUNT(*) FROM knowledge')
    count = cur.fetchone()[0]
    print(f'  [\033[32m✓\033[0m] postgres          up ({count} KB atoms)')
    pg.close()
else:
    print('  [\033[31m✗\033[0m] postgres          NOT CONNECTED')
" 2>/dev/null || echo "  [✗] postgres          error"

        # Ollama
        curl -sf http://localhost:11434/api/tags > /dev/null 2>&1 \
            && echo "  [✓] ollama            up" \
            || echo "  [✗] ollama            unreachable"

        # Systemd user services
        for svc in "${WILLOW_SYSTEMD_SERVICES[@]}"; do
            note="$(_willow_service_note "${svc}")"
            if systemctl --user is-active --quiet "${svc}.service" 2>/dev/null; then
                printf "  [\033[32m✓\033[0m] %-18s running\n" "${svc}"
            elif systemctl --user is-enabled --quiet "${svc}.service" 2>/dev/null; then
                printf "  [\033[31m✗\033[0m] %-18s dead (enabled)\n" "${svc}"
            elif _willow_user_unit_known "${svc}"; then
                printf "  [\033[33m–\033[0m] %-18s disabled\n" "${svc}"
            elif _willow_unit_file_exists "${svc}"; then
                printf "  [\033[33m–\033[0m] %-18s available (not installed)\n" "${svc}"
            elif [[ -n "${note}" ]]; then
                printf "  [\033[33m–\033[0m] %-18s %s\n" "${svc}" "${note}"
            else
                printf "  [\033[33m–\033[0m] %-18s missing unit\n" "${svc}"
            fi
        done

        # MCP server
        if pgrep -f "sap_mcp.py" > /dev/null 2>&1; then
            echo "  [✓] sap_mcp.py        running (Claude Code session)"
        else
            echo "  [–] sap_mcp.py        not running (start via Claude Code)"
        fi

        echo ""
        ;;

    restart)
        "${BASH_SOURCE[0]}" stop-all
        sleep 2
        "${BASH_SOURCE[0]}" start-all
        ;;

    check-updates)
        echo "Willow 2.0 — checking for updates"
        CURRENT=$(grep -r '' "${WILLOW_HOME}/version" 2>/dev/null || echo "unknown")
        LATEST=$(curl -sf --max-time 10 \
            "https://api.github.com/repos/rudi193-cmd/willow-2.0/releases/latest" \
            2>/dev/null | "${WILLOW_PYTHON}" -c \
            "import json,sys; d=json.load(sys.stdin); print(d.get('tag_name','unknown'))" \
            2>/dev/null || echo "unknown")

        if [[ "${LATEST}" == "unknown" ]]; then
            echo "  Could not reach GitHub — skipping"
            exit 0
        fi

        if [[ "${CURRENT}" == "${LATEST}" ]]; then
            echo "  Already up to date (${CURRENT})"
            exit 0
        fi

        echo "  Update available: ${CURRENT} → ${LATEST}"

        "${WILLOW_PYTHON}" -c "
import sys, json
sys.path.insert(0, '${WILLOW_ROOT}')
from core.willow_store import WillowStore
store = WillowStore()
nodes = store.list('grove/nodes')
count = len(nodes)
store.put('grove/pending_alerts', 'update_available', {
    'type': 'update_available',
    'current': '${CURRENT}',
    'latest': '${LATEST}',
    'created_at': __import__('datetime').datetime.now().isoformat(),
})
print(f'  Notification queued for {count} known node(s)')
" 2>/dev/null || echo "  (Grove notify skipped — store unavailable)"
        ;;

    logs)
        _n="${2:-50}"
        _log=$(ls -t "${WILLOW_HOME}/logs/"*.log 2>/dev/null | head -1)
        if [[ -z "${_log}" ]]; then
            echo "No logs found in ${WILLOW_HOME}/logs/"
        else
            echo "=== ${_log} (last ${_n} lines) ==="
            tail -n "${_n}" "${_log}"
        fi
        ;;

    serve)
        _port="${2:-7777}"
        echo "Willow Grove — command server on 0.0.0.0:${_port}"
        echo "  Token: ${WILLOW_HOME}/grove_token"
        echo "  Share the token with trusted nodes: willow grove pair"
        echo ""
        PYTHONPATH="${WILLOW_ROOT}:${PYTHONPATH:-}" WILLOW_ROOT="${WILLOW_ROOT}" "${WILLOW_PYTHON}" "${WILLOW_ROOT}/core/grove_serve.py" --port "${_port}"
        ;;

    grove)
        _grove_sub="${2:-}"
        case "${_grove_sub}" in
            pair)
                TOKEN_FILE="${WILLOW_HOME}/grove_token"
                if [[ ! -f "${TOKEN_FILE}" ]]; then
                    # Generate token by starting server briefly
                    "${WILLOW_PYTHON}" -c "
import os, sys, secrets
from pathlib import Path
tp = Path(os.environ['WILLOW_HOME']) / 'grove_token'
tp.parent.mkdir(parents=True, exist_ok=True)
token = secrets.token_hex(32)
tp.write_text(token + '\n')
tp.chmod(0o600)
print(token)
" 2>/dev/null
                fi
                echo ""
                echo "  Grove token (share with trusted nodes):"
                echo ""
                echo "  $(grep -v '^$' "${TOKEN_FILE}" | head -1)"
                echo ""
                echo "  On the other node, save it with:"
                echo "    echo <token> > ${WILLOW_HOME}/grove_token && chmod 600 ${WILLOW_HOME}/grove_token"
                echo ""
                ;;
            send)
                _host="${3:-}"
                _cmd="${4:-}"
                if [[ -z "${_host}" || -z "${_cmd}" ]]; then
                    echo "Usage: willow.sh grove send <host:port> <command>"
                    echo "  e.g. willow.sh grove send 192.168.1.5:7777 status-all"
                    exit 1
                fi
                "${WILLOW_PYTHON}" -m core.grove_client "${_host}" "${_cmd}"
                ;;
            add)
                _addr="${3:-}"
                _pubkey="${4:-}"
                if [[ -z "${_addr}" || -z "${_pubkey}" ]]; then
                    echo "Usage: willow.sh grove add <user@host:port> <public_key_hex>"
                    exit 1
                fi
                echo "Willow Grove — adding contact: ${_addr}"
                "${WILLOW_PYTHON}" -c "
import sys
sys.path.insert(0, '${WILLOW_ROOT}')
try:
    from pathlib import Path
    from u2u.contacts import ContactStore
    store = ContactStore(Path(os.environ['WILLOW_HOME']) / 'grove_contacts.json')
    name = '${_addr}'.split('@')[0]
    contact = store.add('${_addr}', '${_pubkey}', name=name)
    print(f'  Added: {contact.name} ({contact.addr})')
    print(f'  Public key: {contact.public_key_hex[:16]}...')
    print()
    print('  Next: ask them to run: willow.sh grove knock ${_addr}')
except ImportError:
    print('  Grove u2u module not yet available — arriving in Phase 3.')
    print(f'  Contact saved to pending list for import later.')
    import json, datetime
    from pathlib import Path
    pending = Path(os.environ['WILLOW_HOME']) / 'grove_contacts_pending.json'
    contacts = json.loads(pending.read_text()) if pending.exists() else []
    contacts.append({'addr': '${_addr}', 'pubkey': '${_pubkey}', 'added_at': datetime.datetime.now().isoformat()})
    pending.write_text(json.dumps(contacts, indent=2))
    print(f'  Saved to {pending}')
"
                ;;
            *)
                echo "Usage: willow.sh grove [add <addr> <pubkey>]"
                exit 1
                ;;
        esac
        ;;

    litellm-start)
        echo "Willow 2.0 — starting LiteLLM gateway"
        CONFIG_FILE="${WILLOW_HOME}/litellm_config.yaml"
        "${WILLOW_PYTHON}" -c "
import sys, yaml, json
sys.path.insert(0, '${WILLOW_ROOT}')
from core.willow_store import WillowStore
from core.providers import build_litellm_config
store = WillowStore()
config = build_litellm_config(store)
with open('${CONFIG_FILE}', 'w') as f:
    yaml.dump(config, f)
print('  Config written to ${CONFIG_FILE}')
"
        litellm --config "${CONFIG_FILE}" --port 4000 &
        echo "  LiteLLM gateway running at http://localhost:4000"
        echo "  PID: $!"
        echo $! > "${WILLOW_HOME}/litellm.pid"
        ;;

    litellm-stop)
        PID_FILE="${WILLOW_HOME}/litellm.pid"
        if [[ -f "${PID_FILE}" ]]; then
            kill "$(cat "${PID_FILE}")" 2>/dev/null && echo "  LiteLLM stopped" || echo "  Already stopped"
            rm -f "${PID_FILE}"
        else
            pkill -f "litellm --config" 2>/dev/null && echo "  LiteLLM stopped" || echo "  Not running"
        fi
        ;;

    providers)
        _sub="${2:-list}"
        case "${_sub}" in
            list)
                "${WILLOW_PYTHON}" -c "
import sys
sys.path.insert(0, '${WILLOW_ROOT}')
from core.willow_store import WillowStore
from core.providers import get_providers, _mask_key
store = WillowStore()
providers = get_providers(store)
print('  Providers:')
for p in providers:
    status = '✓ ON ' if p['enabled'] else '✗ OFF'
    local = ' (local)' if p.get('local') else ''
    key_info = ''
    if not p.get('local') and p.get('api_key'):
        key_info = f' key={_mask_key(p[\"api_key\"])}'
    print(f'    [{status}] {p[\"name\"]}{local}{key_info}')
"
                ;;
            enable)
                PROVIDER="${3:-}"
                API_KEY="${4:-}"
                [[ -z "${PROVIDER}" ]] && echo "Usage: willow.sh providers enable <name> [api_key]" && exit 1
                "${WILLOW_PYTHON}" -c "
import sys
sys.path.insert(0, '${WILLOW_ROOT}')
from core.willow_store import WillowStore
from core.providers import enable_provider
store = WillowStore()
enable_provider(store, '${PROVIDER}', api_key='${API_KEY}' or None)
print(f'  Enabled: ${PROVIDER}')
"
                ;;
            disable)
                PROVIDER="${3:-}"
                [[ -z "${PROVIDER}" ]] && echo "Usage: willow.sh providers disable <name>" && exit 1
                "${WILLOW_PYTHON}" -c "
import sys
sys.path.insert(0, '${WILLOW_ROOT}')
from core.willow_store import WillowStore
from core.providers import disable_provider
store = WillowStore()
disable_provider(store, '${PROVIDER}')
print(f'  Disabled: ${PROVIDER}')
"
                ;;
            *)
                echo "Usage: willow.sh providers [list|enable <name> [key]|disable <name>]"
                ;;
        esac
        ;;

    agents)
        shift
        exec "${WILLOW_PYTHON}" -m willow.fylgja.agents_cli "$@"
        ;;

    mcp)
        shift
        exec "${WILLOW_PYTHON}" -m willow.fylgja.mcp_cli "$@"
        ;;

    project)
        shift
        exec "${WILLOW_PYTHON}" -m willow.fylgja.project_cli "$@"
        ;;

    venv)
        shift
        exec "${WILLOW_PYTHON}" -m willow.fylgja.venv_cli "$@"
        ;;

    upstream)
        _WATCHER="${WILLOW_ROOT}/agents/hanuman/bin/upstream_watcher.py"
        _RESPONDER="${WILLOW_ROOT}/agents/hanuman/bin/upstream_responder.py"
        _SCOUT="${WILLOW_ROOT}/agents/hanuman/bin/upstream_scout.py"
        case "${2:-status}" in
            status|pending)
                "${WILLOW_PYTHON}" "${_RESPONDER}" list
                ;;
            show)
                [[ -z "${3:-}" ]] && echo "Usage: willow.sh upstream show <work_id>" && exit 1
                "${WILLOW_PYTHON}" "${_RESPONDER}" show "${3}"
                ;;
            approve)
                [[ -z "${3:-}" ]] && echo "Usage: willow.sh upstream approve <work_id>" && exit 1
                "${WILLOW_PYTHON}" "${_RESPONDER}" approve "${3}" "${@:4}"
                ;;
            edit)
                [[ -z "${3:-}" ]] && echo "Usage: willow.sh upstream edit <work_id> [--file <path>]" && exit 1
                "${WILLOW_PYTHON}" "${_RESPONDER}" edit "${3}" "${@:4}"
                ;;
            skip)
                [[ -z "${3:-}" ]] && echo "Usage: willow.sh upstream skip <work_id> [--reason <text>]" && exit 1
                "${WILLOW_PYTHON}" "${_RESPONDER}" skip "${3}" "${@:4}"
                ;;
            review)
                "${WILLOW_PYTHON}" "${_RESPONDER}" review "${@:3}"
                ;;
            scout)
                "${WILLOW_PYTHON}" "${_SCOUT}" run-once
                ;;
            scout-list)
                "${WILLOW_PYTHON}" "${_SCOUT}" list
                ;;
            scout-show)
                [[ -z "${3:-}" ]] && echo "Usage: willow.sh upstream scout-show <owner--repo>" && exit 1
                "${WILLOW_PYTHON}" "${_SCOUT}" show "${3}"
                ;;
            scout-dismiss)
                [[ -z "${3:-}" ]] && echo "Usage: willow.sh upstream scout-dismiss <owner--repo>" && exit 1
                "${WILLOW_PYTHON}" "${_SCOUT}" dismiss "${3}"
                ;;
            run-now)
                "${WILLOW_PYTHON}" "${_WATCHER}" run-once
                ;;
            digest)
                "${WILLOW_PYTHON}" -c "
import sys; sys.path.insert(0, '${WILLOW_ROOT}')
from core import soil
d = soil.get('upstream_steward/digest', 'latest')
if d:
    print(d.get('line', 'no digest'))
    print('  as of:', d.get('as_of', '?'))
else:
    print('no digest yet — run: willow.sh upstream run-now')
"
                ;;
            *)
                echo "Usage: willow.sh upstream [status|pending|review|scout|scout-list|scout-show|scout-dismiss|show <id>|approve <id>|edit <id>|skip <id>|run-now|digest]"
                ;;
        esac
        ;;

    openclaw-discord)
        _OC_BRIDGE="${WILLOW_ROOT}/scripts/openclaw_discord_bridge.py"
        case "${2:-run}" in
            init-config)
                "${WILLOW_PYTHON}" "${_OC_BRIDGE}" init-config
                ;;
            run)
                "${WILLOW_PYTHON}" "${_OC_BRIDGE}" run "${@:3}"
                ;;
            test-discord)
                "${WILLOW_PYTHON}" "${_OC_BRIDGE}" test-discord "${@:3}"
                ;;
            test-grove)
                "${WILLOW_PYTHON}" "${_OC_BRIDGE}" test-grove
                ;;
            *)
                echo "Usage: willow.sh openclaw-discord [init-config|run|run --once|test-discord|test-grove]"
                ;;
        esac
        ;;

    skills)
        _SKILL_STEWARD="${WILLOW_ROOT}/agents/hanuman/bin/skill_steward.py"
        _OPENCLAW_SETUP="${WILLOW_ROOT}/scripts/setup_openclaw_skills.py"
        case "${2:-}" in
            openclaw-setup)
                "${WILLOW_PYTHON}" "${_OPENCLAW_SETUP}" "${@:3}"
                ;;
            steward)
                case "${3:-status}" in
                    run-once)
                        "${WILLOW_PYTHON}" "${_SKILL_STEWARD}" run-once "${@:4}"
                        ;;
                    status)
                        "${WILLOW_PYTHON}" "${_SKILL_STEWARD}" status
                        ;;
                    list)
                        "${WILLOW_PYTHON}" "${_SKILL_STEWARD}" list
                        ;;
                    show)
                        [[ -z "${4:-}" ]] && echo "Usage: willow.sh skills steward show <skill_id>" && exit 1
                        "${WILLOW_PYTHON}" "${_SKILL_STEWARD}" show "${4}"
                        ;;
                    dismiss)
                        [[ -z "${4:-}" ]] && echo "Usage: willow.sh skills steward dismiss <skill_id> [--reason text]" && exit 1
                        "${WILLOW_PYTHON}" "${_SKILL_STEWARD}" dismiss "${4}" "${@:5}"
                        ;;
                    adopt)
                        [[ -z "${4:-}" ]] && echo "Usage: willow.sh skills steward adopt <skill_id> [--note text]" && exit 1
                        "${WILLOW_PYTHON}" "${_SKILL_STEWARD}" adopt "${4}" "${@:5}"
                        ;;
                    *)
                        echo "Usage: willow.sh skills steward [run-once|status|list|show <id>|dismiss <id>|adopt <id>]"
                        ;;
                esac
                ;;
            *)
                echo "Usage: willow.sh skills [openclaw-setup|steward run-once|steward status|…]"
                ;;
        esac
        ;;

    *)
        echo "Usage: willow.sh [start|status|fleet_status|handoff_latest [agent] [--project ID] [--workspace PATH]]|agents [list|active <id>|install <id>|check]|mcp [list|init|sync|check|audit]|project [list|sync|check]|venv [check|sync]|metabolic|update|export|purge <project>|backup|restore <path>|nuke|ledger [project]|valhalla|verify|w8-census|wce|bridge-cross-runtime|start-all|stop-all|status-all|restart|check-updates|grove add <addr> <pubkey>|litellm-start|litellm-stop|providers [list|enable <name> [key]|disable <name>]|upstream [status|pending|show|approve|run-now|digest]|openclaw-discord [init-config|run|test-discord|test-grove]|skills steward [run-once|status|list|show|dismiss|adopt]]"
        exit 1
        ;;
esac
