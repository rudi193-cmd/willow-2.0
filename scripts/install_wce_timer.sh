#!/usr/bin/env bash
# install_wce_timer.sh — copy willow-wce units and enable weekly timer (existing installs).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER="${HOME}/.config/systemd/user"

mkdir -p "${SYSTEMD_USER}"
for unit in willow-wce.service willow-wce.timer; do
  cp -f "${REPO_ROOT}/systemd/${unit}" "${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload
systemctl --user enable --now willow-wce.timer
