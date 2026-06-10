#!/data/data/com.termux/files/usr/bin/bash
# Quick dispatch to desktop node via Grove envelope
cd "$HOME/ratatosk/termux" 2>/dev/null || cd "$(dirname "$0")/.."
python - <<'PY'
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from ratatosk.protocol.envelope import build_envelope, Intent
from ratatosk.transport.grove_client import GroveClient
prompt = os.environ.get("RATATOSK_PROMPT", "status")
env = build_envelope(to="ratatosk", prompt=prompt, intent=Intent.OPEN_STATUS.value, reply_channel="general")
GroveClient().post_envelope("dispatch", env)
print("sent", env.trace_id)
PY
