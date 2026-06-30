#!/usr/bin/env bash
# setup.sh — Willow 2.0 bootstrap
# Run once on a new machine, or re-run to sync config + deps.
#
# What it does:
#   1. Pull private willow-config → ~/github/.willow; link runtime config into willow-2.0
#   2. Create .venv-dev if missing
#   3. Install requirements.txt, editable willow (--no-deps), dev tools
#   4. Verify Postgres connection
#   5. Run migrations
#
# Usage:
#   bash setup.sh
#   bash setup.sh --public     # GitHub-only clone — skip private willow-config
#   bash setup.sh --no-migrate   # skip DB migration step

set -euo pipefail

WILLOW_CONFIG_REPO="https://github.com/rudi193-cmd/willow-config.git"
WILLOW_HOME="${HOME}/github/.willow"
GITHUB_ROOT="${HOME}/github"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${REPO_ROOT}/.venv-dev"
PUBLIC_MODE=0
NO_MIGRATE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --public) PUBLIC_MODE=1; shift ;;
        --no-migrate) NO_MIGRATE="--no-migrate"; shift ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

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
if [[ "${PY_MINOR}" -ge 14 ]]; then
    warn "Python ${PY_VER}: litellm>=1.87 is unavailable — requirements use litellm 1.83.x on 3.14+"
    warn "For full dep parity, recreate .venv-dev with Python 3.11–3.13"
fi
ok "Python ${PY_VER}"

# ── 2. ~/.willow runtime home (optional willow-config merge) ─────────────────

mkdir -p "${GITHUB_ROOT}/SAFE/Applications" "${GITHUB_ROOT}/SAFE/Agents"
# Legacy symlinks so old paths keep working
[[ -e "${HOME}/.willow" ]] || ln -sfn "${WILLOW_HOME}" "${HOME}/.willow"
[[ -e "${HOME}/SAFE" ]] || ln -sfn "${GITHUB_ROOT}/SAFE" "${HOME}/SAFE"
[[ -e "${HOME}/willow-2.0" ]] || ln -sfn "${REPO_ROOT}" "${HOME}/willow-2.0"
[[ -d "${GITHUB_ROOT}/safe-app-store" && ! -e "${HOME}/safe-app-store" ]] && ln -sfn "${GITHUB_ROOT}/safe-app-store" "${HOME}/safe-app-store"

hdr "~/github/.willow (willow-config)"
if [[ "${PUBLIC_MODE}" -eq 1 ]]; then
    warn "Public mode — skipping willow-config clone (using repo public pack)"
elif [[ -d "${WILLOW_HOME}/.git" ]]; then
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
    if git clone "${WILLOW_CONFIG_REPO}" "${WILLOW_HOME_TMP}" 2>/dev/null; then
        rsync -a --ignore-existing "${WILLOW_HOME_TMP}/" "${WILLOW_HOME}/"
        rm -rf "${WILLOW_HOME_TMP}"
        ok "Merged willow-config into existing ~/.willow"
    else
        warn "willow-config clone failed — continuing with public fallback pack"
        PUBLIC_MODE=1
    fi
else
    if git clone "${WILLOW_CONFIG_REPO}" "${WILLOW_HOME}" 2>/dev/null; then
        ok "Cloned willow-config → ~/.willow"
    else
        warn "willow-config unavailable — continuing with public fallback pack"
        PUBLIC_MODE=1
    fi
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
rm -rf "${REPO_ROOT}/willow.egg-info"
"${VENV}/bin/pip" install --quiet -e "${REPO_ROOT}" --no-deps --no-build-isolation
"${VENV}/bin/pip" install --quiet -r "${REPO_ROOT}/requirements-dev.txt"
ok "Requirements + editable willow + dev tools installed"

hdr "Pre-commit hooks"
if [[ -x "${VENV}/bin/pre-commit" ]]; then
    "${VENV}/bin/pre-commit" install
    "${VENV}/bin/pre-commit" install --hook-type pre-push
    ok "pre-commit installed (commit + pre-push — ruff matches CI lint job)"
else
    warn "pre-commit missing from venv — run: ${VENV}/bin/pip install -r requirements-dev.txt"
fi

hdr "Fleet venv (\$WILLOW_HOME/venv)"
PYTHONPATH="${REPO_ROOT}" WILLOW_HOME="${WILLOW_HOME:-${HOME}/github/.willow}" \
    "${VENV}/bin/python3" -m willow.fylgja.fleet_venv sync \
    && ok "Fleet venv symlinked to .venv-dev" \
    || warn "Fleet venv sync skipped (run: ./willow.sh venv sync)"

# Fleet contract: private willow-config when present, else repo public pack
LINK_ARGS=()
if [[ "${PUBLIC_MODE}" -eq 1 ]]; then
    export WILLOW_CONFIG_MODE=public-fallback
    export WILLOW_HOME="${REPO_ROOT}/.willow/generated"
    LINK_ARGS+=(--public)
fi
PYTHONPATH="${REPO_ROOT}" WILLOW_CONFIG_MODE="${WILLOW_CONFIG_MODE:-}" WILLOW_HOME="${WILLOW_HOME:-}" \
    "${VENV}/bin/python3" -m willow.fylgja.link_fleet_home "${LINK_ARGS[@]}"
if [[ "${PUBLIC_MODE}" -eq 1 ]]; then
    ok "Linked willow-2.0 → public fallback pack (.willow/generated)"
else
    ok "Linked willow-2.0 runtime config → ~/.willow (willow-config); root willow.md remains public"
fi

hdr "IDE + agent install"
ACTIVE_FILE="${REPO_ROOT}/.willow/active-agent"
if [[ -n "${WILLOW_AGENT_NAME:-}" ]]; then
    AGENT="${WILLOW_AGENT_NAME}"
elif [[ -f "${ACTIVE_FILE}" ]]; then
    AGENT="$(tr -d '[:space:]' < "${ACTIVE_FILE}")"
elif [[ "${PUBLIC_MODE}" -eq 1 ]]; then
    AGENT="willow"
    mkdir -p "$(dirname "${ACTIVE_FILE}")"
    echo "${AGENT}" > "${ACTIVE_FILE}"
    warn "No active agent — defaulted to ${AGENT} (public mode)"
else
    fail "No active agent. Run: cd ${REPO_ROOT} && ./willow agents active <id> && ./willow agents install <id> --ide all"
fi
export WILLOW_AGENT_NAME="${AGENT}"
PYTHONPATH="${REPO_ROOT}" WILLOW_CONFIG_MODE="${WILLOW_CONFIG_MODE:-}" WILLOW_HOME="${WILLOW_HOME:-}" \
    "${VENV}/bin/python3" -m willow.fylgja.install_project "${AGENT}" --ide all
ok "install_project ${AGENT} (active-agent=${ACTIVE_FILE})"

hdr "Systemd fleet units"
SYSTEMD_USER="${HOME}/.config/systemd/user"
mkdir -p "${SYSTEMD_USER}"
for unit in "${REPO_ROOT}"/systemd/*.service "${REPO_ROOT}"/systemd/*.socket "${REPO_ROOT}"/systemd/*.timer; do
    [[ -f "${unit}" ]] || continue
    cp -f "${unit}" "${SYSTEMD_USER}/$(basename "${unit}")"
done
for unit in willow-metabolic.socket willow-metabolic.service grove-mcp.service \
            willow-grove-listen.service drop-server.service nest-watcher.service \
            journal-watcher.service; do
    src="${REPO_ROOT}/systemd/${unit}"
    [[ -f "${src}" ]] || warn "Missing expected systemd unit: ${unit}"
done
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload
    systemctl --user enable --now willow-metabolic.socket willow-metabolic.timer grove-mcp.service \
        willow-grove-listen.service drop-server.service nest-watcher.service \
        journal-watcher.service willow-w8-census.timer willow-wce.timer \
        willow-bridge-cross-runtime.timer 2>/dev/null \
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
