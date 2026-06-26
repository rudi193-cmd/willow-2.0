#!/usr/bin/env bash
# install_bridge_timer.sh — copy bridge-cross-runtime units and enable daily timer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER="${HOME}/.config/systemd/user"

mkdir -p "${SYSTEMD_USER}"
for unit in willow-bridge-cross-runtime.service willow-bridge-cross-runtime.timer; do
  cp -f "${REPO_ROOT}/systemd/${unit}" "${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload
systemctl --user enable --now willow-bridge-cross-runtime.timer
