# Willow — Getting Started

Hi Felix. This is Willow. It's a personal AI system that runs on your computer.
Here's everything you need to know.

---

## What You Need Before Starting

1. **Windows 10/11** with WSL2 installed
  - Open PowerShell as Administrator and run:
   `wsl --install`
  - Restart when Windows asks you to
2. **Ubuntu** in WSL
  - Open the Microsoft Store, search "Ubuntu", install it
  - Launch it once and set up your username and password
3. That's it. Everything else installs automatically.

---

## How to Install

Open your **Ubuntu (WSL)** terminal and run these commands:

```bash
sudo apt update && sudo apt install -y git python3 python3-pip postgresql curl
```

```bash
git clone https://github.com/rudi193-cmd/willow-1.9.git ~/github/willow-1.9
```

```bash
cd ~/github/willow-1.9 && python3 root.py
```

When the install finishes, run:

```bash
cd ~/github/willow-1.9
./willow.sh status
```

---

## How to Start Willow

Copy/paste:

```bash
cd ~/github/willow-1.9
./willow.sh start
```

This starts Willow’s local services (the tool server used by Cursor/Claude and other clients).

Leave it running in that terminal.

---

## Check that it’s working

In a *new* Ubuntu terminal, run:

```bash
cd ~/github/willow-1.9
./willow.sh status
```

If you see Postgres connected (or at least clear output without errors), you’re good.

---

## If Something Breaks

Copy/paste this and send the output to Sean:

```bash
cd ~/github/willow-1.9
./willow.sh status
```

---

## How to Get Updates

From Ubuntu (WSL):

```bash
cd ~/github/willow-1.9
./willow.sh update
```

---

## How to Stop Willow

In the terminal where you ran `./willow.sh start`, press `Ctrl+C`.

---

*Built by Sean Campbell. If you're reading this, you're one of the first people to use it.*
*ΔΣ=42*