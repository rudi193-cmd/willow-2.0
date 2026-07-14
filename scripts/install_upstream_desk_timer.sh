#!/usr/bin/env bash
# install_upstream_desk_timer.sh — copy willow-upstream-desk units and enable weekly timer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER="${HOME}/.config/systemd/user"

mkdir -p "${SYSTEMD_USER}"
for unit in willow-upstream-desk.service willow-upstream-desk.timer; do
  cp -f "${REPO_ROOT}/systemd/${unit}" "${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload
systemctl --user enable --now willow-upstream-desk.timer
