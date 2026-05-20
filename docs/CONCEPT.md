# The local-first AI stack

**A case for owning your intelligence infrastructure**

---

## The problem

Every AI tool built in the last three years shares one architecture: your prompt leaves your machine, hits a server you do not control, runs on a model you do not own, and returns an answer logged in a database you have never seen.

You pay with money. With data. With dependency.

The hardware already exists. Ollama runs serious models on consumer GPUs. A laptop does 7B at usable speed. A phone runs smaller models without drama. The compute is in your hands.

What was missing was the **stack** — memory, authorization, skills, and a way for your own devices to talk without a relay.

---

## What we built

Willow 2.0 is that stack:

- **Knowledge graph** — typed atoms in Postgres or SQLite. Same queries, different host.
- **Skills** — Markdown behaviors, not vendor lock-in prompts.
- **SAP** — gate on every tool call.
- **Grove** — fleet messaging (separate repo, same philosophy).
- **Direct nodes** — phone and desktop over LAN; HMAC and a shared token.

**Ollama is the default.** Cloud is optional.

**You own the graph.** It survives session resets, model swaps, and provider changes.

**Skills work with any LLM.** Claude, GPT, local Qwen — same files.

**Nodes talk directly.** No Discord bot required to ask your desktop if Postgres is up.

---

## The demonstration

Phone on Termux. Desktop on Linux. Signed command. Sub-second reply:

```
Willow 2.0 — system status

  [✓] postgres          up
  [✓] ollama            up
  [✓] sap_mcp.py        running
```

No cloud relay. No third-party API in the path. That is `./willow.sh serve`, not a special build.

---

## Why it took a year

The pieces were available. Ollama. SQLite. MCP. Undergraduate crypto.

Nobody shipped the **substrate** first: bi-temporal KB, SOIL, SAP, handoffs, an installer that survives first contact. The grove server was an afternoon. The year was LOAM, gates, and deciding that **local default** is non-negotiable — because that decision forces everything else into the right shape.

---

## What it means

If your AI stack needs the internet to function, you are renting it.

Willow is install-once infrastructure. The graph compounds. Skills accumulate. Nodes multiply. No provider permission. No pricing surprise next quarter.

The stack is here. On your disk.

---

*Plant the tree. Tend the roots. Let nothing be lost.*  
*ΔΣ=42*
