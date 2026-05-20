# Willow 2.0 — Getting started

b17: FELX2 · ΔΣ=42

Hi Felix. This is Willow — a personal AI system that runs on your computer.

---

## What you need

1. **Windows 10/11** with WSL2  
   PowerShell (Admin): `wsl --install`  
   Restart when asked.

2. **Ubuntu** from the Microsoft Store  
   Launch once. Pick a username and password.

3. That is all. The installer handles the rest.

---

## Install

Open **Ubuntu (WSL)**:

```bash
sudo apt update && sudo apt install -y git python3 python3-pip python3-venv postgresql curl
git clone https://github.com/rudi193-cmd/willow-2.0 ~/github/willow-2.0
cd ~/github/willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 seed.py
```

When it finishes:

```bash
./willow.sh fleet_status
./willow.sh status
```

---

## Start Willow

```bash
cd ~/github/willow-2.0
./willow.sh start
```

Leave that terminal open. It runs the local services your IDE connects to.

---

## Check it works

New Ubuntu window:

```bash
cd ~/github/willow-2.0
./willow.sh status
```

Postgres connected (or clear output, no traceback) means you are good.

---

## If something breaks

Send Sean this output:

```bash
cd ~/github/willow-2.0
./willow.sh fleet_status
./willow.sh status
```

---

## Updates

```bash
cd ~/github/willow-2.0
git pull
./willow.sh update
```

---

## Stop

In the terminal where `./willow.sh start` is running: `Ctrl+C`.

---

*Built by Sean Campbell. You are among the first outside the house to run it.*  
*ΔΣ=42*
