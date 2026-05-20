# Smart home (optional)

Textual + TinyTuya dashboard. **Not required for Willow core.**

## Setup (local only — never commit secrets)

1. Copy examples and fill in your devices (from TinyTuya scan / Tuya IoT):

   ```bash
   cp devices.json.example devices.json
   cp keys.json.example keys.json
   cp tinytuya.json.example tinytuya.json   # optional cloud API
   ```

2. `keys.json` maps device `id` → local key. Keep it out of git (see repo `.gitignore`).

3. Run from this directory:

   ```bash
   pip install tinytuya textual
   python3 app.py
   ```

Do **not** commit `devices.json`, `keys.json`, `tinytuya.json`, `tuya-raw.json`, or `snapshot.json`.
