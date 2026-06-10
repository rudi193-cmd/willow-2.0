#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot — start Ratatosk Grove listener in background
cd "$HOME/ratatosk/termux" 2>/dev/null || cd "$(dirname "$0")/../.." || exit 0
export RATATOSK_TRANSPORT="${RATATOSK_TRANSPORT:-tailnet}"
nohup python main.py --listen >> "$HOME/.ratatosk/listener.log" 2>&1 &
