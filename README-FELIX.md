# Felix — your path into Willow

Hi Felix.

USER built this for people he trusts, not for engineers. You do not need to understand databases, MCP, or any of that. You need a computer that can hold memory for you, and a front room where you can see what the system knows and talk to it.

That front room is **Grove**. This page is the story of how you get there once.

---

## What you are actually doing

Think of Willow as a **house on your PC**:

- **The basement** is where things are stored (your notes, history, what mattered last week). You never have to go down there.
- **The install wizard** is `seed.py`. It asks your name, walks you through setup step by step, and does the boring work while FRANK narrates the show. If something is wrong, it will stop and tell you — you are not expected to diagnose it.
- **Grove** is the **living room**. Channels, messages, the dashboard. When setup is done, you live here.

You are not “deploying a stack.” You are moving in.

---

## Before you start (one-time on Windows)

You need **Windows 10 or 11** and **WSL** so Linux can run quietly in the background. USER can sit with you for this part if you want; it is the only Windows-shaped hurdle.

1. Open **PowerShell as Administrator** (right-click → Run as administrator).
2. Paste this and press Enter:

   ```
   wsl --install
   ```

3. Restart when Windows asks.
4. Open the **Microsoft Store**, install **Ubuntu**, open it once, and pick a username and password. Remember the password.

After that, you mostly live inside **Ubuntu** for Willow — not because you are becoming a Linux person, but because that is where the house was built.

---

## The only install block you need to copy

Open **Ubuntu** from the Start menu. Paste this whole block, press Enter, and let it run. Go get coffee. It may ask for your Ubuntu password once or twice — that is normal.

```bash
sudo apt update && sudo apt install -y git python3 python3-pip python3-venv postgresql curl
git clone https://github.com/rudi193-cmd/willow-2.0 ~/github/willow-2.0
cd ~/github/willow-2.0
python3 -m venv .venv-dev && source .venv-dev/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
python3 seed.py
```

### What `seed.py` will do (so you are not surprised)

You are not supposed to run health checks afterward. **Seed is the check.** While it runs you will see lines scrolling — directories, vault, database, a little theater from FRANK. Answer the prompts when it asks (your name, email for the vault, whether you want Grove network features, and so on). If you are unsure, say yes to **Grove** when it offers — that is how you end up in the right place.

When seed finishes without a red error wall, **you are installed.** USER can help if it stops hard; send him a photo of the screen or the last few lines of text.

---

## How you will use it day to day

After a good seed on Windows, you should have a shortcut on your **Windows Desktop**:

**Launch Willow.bat**

Double-click it. A window opens — that is **Grove**. No terminal commands required for normal use.

From there:

- You will see **channels** (like rooms). `#general` is the main room.
- You can **read** what agents and people have posted.
- You can **write** — ask a question, leave a note, pick up where you left off. Willow and the other voices are meant to remember context that normal chat apps throw away.

That is the habit: **open Grove, read the room, say what you need.** The system keeps the thread on your machine, not in someone else’s cloud.

If the desktop shortcut is missing, tell USER — seed usually creates it; he can fix the path once.

---

## When something feels broken

You do not need to run `fleet_status` or decode JSON. Try in order:

1. Close the Grove window and double-click **Launch Willow.bat** again.
2. If it still fails, text USER. He will ask you to open Ubuntu and paste one thing — he will send it. That is his job, not yours.

---

## Updates (rare)

USER or the repo will tell you when to pull an update. Until then, ignore git. If he says “update Willow,” he will give you a short paste block — same as install, but shorter.

---

## Why you are here

You are in the **found family** line on the main README for a reason. This tree is tended for people who show up in real life. Grove is where you land after the wizard does its work — not a homework assignment, a place to think out loud with memory that stays.

Welcome in.

*Built by USER. You are among the first outside the house to run it.*
