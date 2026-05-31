#!/usr/bin/env bash
# setup.sh — Willow 2.0 bootstrap
# Run once on a new machine, or re-run to sync config + deps.
#
# What it does:
#   1. Pull private willow-config → ~/github/.willow; link contract into willow-2.0 (symlinks in, not out)
#   2. Create .venv-dev if missing
#   3. Install/upgrade requirements.txt
#   4. Verify Postgres connection
#   5. Run migrations
#
# Usage:
#   bash setup.sh
#   bash setup.sh --no-migrate   # skip DB migration step

set -euo pipefail

WILLOW_CONFIG_REPO="https://github.com/rudi193-cmd/willow-config.git"
WILLOW_HOME="${HOME}/github/.willow"
GITHUB_ROOT="${HOME}/github"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${REPO_ROOT}/.venv-dev"
NO_MIGRATE="${1:-}"

hdr()  { echo ""; echo "─── $1 $(printf '─%.0s' $(seq 1 $((52 - ${#1}))))"; }
ok()   { echo "  ✓  $1"; }
warn() { echo "  ⚠  $1"; }
fail() { echo "  ✗  $1" >&2; exit 1; }

# ── 1. Python ─────────────────────────────────────────────────────────────────

hdr "Python"
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PY_MAJOR=$(echo "${PY_VER}" | cut -d. -f1)
PY_MINOR=$(echo "${PY_VER}" | cut -d. -f2)
[[ "${PY_MAJOR}" -ge 3 && "${PY_MINOR}" -ge 11 ]] || fail "Python 3.11+ required (found ${PY_VER})"
ok "Python ${PY_VER}"

# ── 2. ~/.willow runtime home (optional willow-config merge) ─────────────────

mkdir -p "${GITHUB_ROOT}/SAFE/Applications" "${GITHUB_ROOT}/SAFE/Agents"
# Legacy symlinks so old paths keep working
[[ -e "${HOME}/.willow" ]] || ln -sfn "${WILLOW_HOME}" "${HOME}/.willow"
[[ -e "${HOME}/SAFE" ]] || ln -sfn "${GITHUB_ROOT}/SAFE" "${HOME}/SAFE"
[[ -e "${HOME}/willow-2.0" ]] || ln -sfn "${REPO_ROOT}" "${HOME}/willow-2.0"
[[ -d "${GITHUB_ROOT}/safe-app-store" && ! -e "${HOME}/safe-app-store" ]] && ln -sfn "${GITHUB_ROOT}/safe-app-store" "${HOME}/safe-app-store"

hdr "~/github/.willow (willow-config)"
if [[ -d "${WILLOW_HOME}/.git" ]]; then
    REMOTE=$(git -C "${WILLOW_HOME}" remote get-url origin 2>/dev/null || echo "")
    if [[ "${REMOTE}" == *"willow-config"* ]]; then
        git -C "${WILLOW_HOME}" pull --ff-only origin master 2>&1 | tail -1
        ok "Pulled latest willow-config"
    else
        warn "~/.willow is a git repo but not willow-config (remote: ${REMOTE}). Skipping."
    fi
elif [[ -d "${WILLOW_HOME}" && ! -d "${WILLOW_HOME}/.git" ]]; then
    warn "~/.willow exists but is not a git repo. Cloning willow-config alongside..."
    WILLOW_HOME_TMP="${HOME}/.willow-config-tmp"
    git clone "${WILLOW_CONFIG_REPO}" "${WILLOW_HOME_TMP}"
    # Merge tracked files without clobbering existing runtime state
    rsync -a --ignore-existing "${WILLOW_HOME_TMP}/" "${WILLOW_HOME}/"
    rm -rf "${WILLOW_HOME_TMP}"
    ok "Merged willow-config into existing ~/.willow"
else
    git clone "${WILLOW_CONFIG_REPO}" "${WILLOW_HOME}"
    ok "Cloned willow-config → ~/.willow"
fi

# ── 3. Venv ───────────────────────────────────────────────────────────────────

hdr "Python venv (.venv-dev)"
if [[ ! -d "${VENV}" ]]; then
    python3 -m venv "${VENV}"
    ok "Created ${VENV}"
else
    ok "Venv exists"
fi
"${VENV}/bin/pip" install --quiet --upgrade pip
"${VENV}/bin/pip" install --quiet -r "${REPO_ROOT}/requirements.txt"
ok "Requirements installed"

# Private willow-config (~/github/.willow) is canonical; willow-2.0 symlinks in
PYTHONPATH="${REPO_ROOT}" "${VENV}/bin/python3" -m willow.fylgja.link_fleet_home
ok "Linked willow-2.0/willow.md + config → ~/.willow (willow-config)"

hdr "IDE + agent install"
ACTIVE_FILE="${REPO_ROOT}/.willow/active-agent"
if [[ -n "${WILLOW_AGENT_NAME:-}" ]]; then
    AGENT="${WILLOW_AGENT_NAME}"
elif [[ -f "${ACTIVE_FILE}" ]]; then
    AGENT="$(tr -d '[:space:]' < "${ACTIVE_FILE}")"
else
    fail "No active agent. Run: cd ${REPO_ROOT} && ./willow agents active <id> && ./willow agents install <id> --ide all"
fi
export WILLOW_AGENT_NAME="${AGENT}"
PYTHONPATH="${REPO_ROOT}" "${VENV}/bin/python3" -m willow.fylgja.install_project "${AGENT}" --ide all
ok "install_project ${AGENT} (active-agent=${ACTIVE_FILE})"

hdr "Systemd fleet units"
SYSTEMD_USER="${HOME}/.config/systemd/user"
mkdir -p "${SYSTEMD_USER}"
for unit in willow-metabolic.socket willow-metabolic.service grove-mcp.service \
            willow-grove-listen.service drop-server.service nest-watcher.service; do
    src="${REPO_ROOT}/systemd/${unit}"
    [[ -f "${src}" ]] && cp -f "${src}" "${SYSTEMD_USER}/${unit}"
done
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload
    systemctl --user enable --now willow-metabolic.socket grove-mcp.service \
        willow-grove-listen.service drop-server.service nest-watcher.service 2>/dev/null \
        && ok "Fleet units enabled" || warn "Some systemd units failed to enable"
else
    warn "systemctl not available"
fi

# ── 4. Postgres ───────────────────────────────────────────────────────────────

hdr "Postgres"
PG_DB="${WILLOW_PG_DB:-willow_20}"
if psql -d "${PG_DB}" -c "SELECT 1" >/dev/null 2>&1; then
    ok "Connected to ${PG_DB}"
else
    warn "Cannot reach Postgres DB '${PG_DB}'. Set WILLOW_PG_DB or start Postgres."
    warn "Skipping migration step."
    NO_MIGRATE="--no-migrate"
fi

# ── 5. Migrations ─────────────────────────────────────────────────────────────

if [[ "${NO_MIGRATE}" != "--no-migrate" ]]; then
    hdr "Migrations"
    "${VENV}/bin/python3" - << 'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
from core.pg_bridge import PgBridge, run_migrations
b = PgBridge()
run_migrations(b.conn)
b.conn.commit()
b.close()
print("  ✓  Migrations complete")
PYEOF
fi

# ── Done ──────────────────────────────────────────────────────────────────────

hdr "Done"
echo ""
echo "  Willow 2.0 is ready."
echo "  Activate venv:  source .venv-dev/bin/activate"
echo "  Run jukebox:    python3 tools/jukebox.py \"your mood here\""
echo ""
