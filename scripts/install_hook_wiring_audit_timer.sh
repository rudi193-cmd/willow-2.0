#!/usr/bin/env bash
# install_hook_wiring_audit_timer.sh — copy hook-wiring-audit units and enable daily timer (existing installs).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER="${HOME}/.config/systemd/user"

mkdir -p "${SYSTEMD_USER}"
for unit in hook-wiring-audit.service hook-wiring-audit.timer; do
  cp -f "${REPO_ROOT}/systemd/${unit}" "${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload
systemctl --user enable --now hook-wiring-audit.timer
