#!/usr/bin/env bash
# Ratatosk Termux install — phone endpoint
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PARENT="$(cd "$ROOT/.." && pwd)"

echo "==> Ratatosk Termux install"
echo "    root: $ROOT"

pip install -r "$ROOT/requirements.txt" --break-system-packages 2>/dev/null \
  || pip install -r "$ROOT/requirements.txt"

pip install -e "$PARENT" --break-system-packages 2>/dev/null \
  || pip install -e "$PARENT"

mkdir -p "$HOME/.ratatosk/sessions" "$HOME/.ratatosk/traces"
mkdir -p "$HOME/.termux/boot" "$HOME/.shortcuts"

# Boot listener (Termux:Boot)
cp "$ROOT/boot/ratatosk-listen.sh" "$HOME/.termux/boot/"
chmod +x "$HOME/.termux/boot/ratatosk-listen.sh"

# Widget shortcuts (Termux:Widget)
for s in "$ROOT/shortcuts/"*.sh; do
  cp "$s" "$HOME/.shortcuts/"
  chmod +x "$HOME/.shortcuts/$(basename "$s")"
done

cat <<'EOF'

Installed.
  python main.py              # terminal REPL
  python main.py --listen     # Grove listener
  python main.py --gui        # Termux:GUI (when termux-gui installed)
  ratatosk doctor             # health check

Termux plugins (optional, F-Droid):
  pkg install termux-api termux-boot termux-gui
  Install Termux:Widget APK for home-screen shortcuts.

Set transport (tailnet default):
  export RATATOSK_GROVE_TAILNET_URL="http://100.x.x.x:PORT"
  export GROVE_TOKEN="$(cat ~/.willow/grove_token)"

EOF
