#!/usr/bin/env bash
# Boot splash wrapper — shows persona art in the raw terminal before Claude Code starts.
# Usage: alias claude='bash ~/github/willow-2.0/scripts/willow-claude.sh'

PYTHON="/home/sean-campbell/github/willow-2.0/.venv-dev/bin/python3"
SPLASH="/home/sean-campbell/github/willow-2.0/willow/fylgja/boot_splash.py"

"$PYTHON" "$SPLASH" 2>/dev/null
exec claude "$@"
