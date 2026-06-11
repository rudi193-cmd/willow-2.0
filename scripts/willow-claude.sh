#!/usr/bin/env bash
# Boot splash wrapper — shows persona art in the raw terminal before Claude Code starts.
# Usage: alias claude='bash ~/github/willow-2.0/scripts/willow-claude.sh'

WILLOW_ROOT="${WILLOW_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON="${WILLOW_ROOT}/.venv-dev/bin/python3"
SPLASH="${WILLOW_ROOT}/willow/fylgja/boot_splash.py"

"$PYTHON" "$SPLASH" 2>/dev/null
exec claude "$@"
