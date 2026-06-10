#!/data/data/com.termux/files/usr/bin/bash
ratatosk panic --note "widget emergency stop" 2>/dev/null || python -m ratatosk.cli panic
pkill -f "python main.py --listen" 2>/dev/null || true
termux-notification -t "Ratatosk" -c "Emergency stop activated" 2>/dev/null || true
