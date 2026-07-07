#!/usr/bin/env bash
# install_stuck_loop_watch_timer.sh — copy stuck-loop-watch units and enable 15min timer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER="${HOME}/.config/systemd/user"

mkdir -p "${SYSTEMD_USER}"
for unit in stuck-loop-watch.service stuck-loop-watch.timer; do
  cp -f "${REPO_ROOT}/systemd/${unit}" "${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload
systemctl --user enable --now stuck-loop-watch.timer
