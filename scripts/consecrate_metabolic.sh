#!/usr/bin/env bash
# consecrate_metabolic.sh — install + enable metabolic socket/timer and run first Norn pass.
# Must run on the HOST (not Kart/bwrap): ~/.config/systemd is not writable in the sandbox.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER="${HOME}/.config/systemd/user"

echo "[consecrate] Installing willow-metabolic units to ${SYSTEMD_USER}"
mkdir -p "${SYSTEMD_USER}"
for unit in willow-metabolic.socket willow-metabolic.service willow-metabolic.timer; do
  src="${REPO_ROOT}/systemd/${unit}"
  dest="${SYSTEMD_USER}/${unit}"
  [[ -f "${src}" ]] || { echo "Missing ${src}" >&2; exit 1; }
  src_real="$(readlink -f "${src}")"
  dest_real="$(readlink -f "${dest}" 2>/dev/null || true)"
  if [[ "${src_real}" == "${dest_real}" ]]; then
    echo "  ${unit}: already present (${dest})"
  else
    cp -f "${src}" "${dest}"
  fi
done

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now willow-metabolic.socket willow-metabolic.timer
  echo "[consecrate] Socket: $(systemctl --user is-active willow-metabolic.socket 2>/dev/null || echo inactive)"
  echo "[consecrate] Timer:  $(systemctl --user is-active willow-metabolic.timer 2>/dev/null || echo inactive)"
  systemctl --user list-timers willow-metabolic.timer --no-pager 2>/dev/null || true
else
  echo "[consecrate] systemctl not available — units copied only" >&2
fi

echo "[consecrate] Running first Norn pass (may take several minutes)..."
"${REPO_ROOT}/willow.sh" metabolic

echo "[consecrate] Status:"
(
  cd "${REPO_ROOT}"
  "${REPO_ROOT}/.venv-dev/bin/python3" - <<'PY'
import json
from core.metabolic_status import check_metabolic_status
print(json.dumps(check_metabolic_status(), indent=2))
PY
)
