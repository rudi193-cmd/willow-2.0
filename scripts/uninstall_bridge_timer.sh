#!/usr/bin/env bash
# uninstall_bridge_timer.sh — retire the daily cross-runtime bridge timer.
#
# ADR-20260703: the bridge is now rebuilt at READ time by
# willow.fylgja.cross_runtime.ensure_fresh_bridge / anchor_lines, so the
# 06:00 timer only produces an artifact nobody should trust. Run this once
# on the host (not inside Kart — systemd needs the user D-Bus socket).
set -euo pipefail

systemctl --user disable --now willow-bridge-cross-runtime.timer 2>/dev/null || true
for unit in willow-bridge-cross-runtime.service willow-bridge-cross-runtime.timer; do
  rm -f "$HOME/.config/systemd/user/$unit"
done
systemctl --user daemon-reload
echo "willow-bridge-cross-runtime timer retired (bridge now rebuilds at read time)"
