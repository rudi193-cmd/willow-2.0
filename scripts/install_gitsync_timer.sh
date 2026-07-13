#!/usr/bin/env bash
# install_gitsync_timer.sh — deploy host git-universe sync + enable 25min timer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITSYNC_HOME="${HOME}/.local/share/gitsync"
SYSTEMD_USER="${HOME}/.config/systemd/user"

mkdir -p "${GITSYNC_HOME}" "${SYSTEMD_USER}"
install -m 0755 "${REPO_ROOT}/scripts/gitsync/gitsync-loop.py" "${GITSYNC_HOME}/gitsync-loop.py"
if [[ ! -f "${GITSYNC_HOME}/owners.json" ]]; then
  install -m 0644 "${REPO_ROOT}/scripts/gitsync/owners.json.example" "${GITSYNC_HOME}/owners.json"
fi
for unit in gitsync.service gitsync.timer; do
  cp -f "${REPO_ROOT}/systemd/${unit}" "${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload
systemctl --user enable --now gitsync.timer
echo "gitsync installed — status: ${GITSYNC_HOME}/gitsync-status.txt"
