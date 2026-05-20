# Willow 2.0 — branding schema

b17: BRND2 · ΔΣ=42

Canonical identity for docs, code headers, Grove posts, and packaging. Match this on new files; migrate old files when you touch them.

---

## Product

| Field | Value |
|-------|--------|
| Name | **Willow 2.0** (never “Willow 1.9” in active tree) |
| Repo | `willow-2.0` |
| Database | `willow_20` |
| Tagline | Local-first AI stack · Ollama by default |
| Closing line | *Plant the tree. Tend the roots. Name the ones you love. Let nothing be lost.* |

Version strings: single source [`VERSION`](../VERSION) file → `core/version.py` → `~/.willow/version` (synced by `willow.sh status` / `fleet_status` / install).

---

## Seal

Every branded artifact ends with the fleet seal:

```text
· ΔΣ=42
```

- Use the **middle dot** (`·`), not a hyphen or double space.
- Docs: footer `*ΔΣ=42*` or line `· ΔΣ=42` under the header.
- Code: same seal on the `b17` / `b20` line.

---

## b17 — artifact codes

**b17** tags a document, module, or Grove event. One primary code per artifact.

### Format

```text
b17: <CODE> · ΔΣ=42
```

| Context | Placement |
|---------|-----------|
| Markdown | Line 3, immediately under the `#` title |
| Python | Line 2–4 of module docstring, or `# b17: …` after shebang |
| Shell | Comment on line 2–3 after the description |
| YAML frontmatter | `b17: <CODE> · ΔΣ=42` |

### Code rules

- **Length:** 5 characters preferred (4–6 allowed for legacy).
- **Charset:** `A–Z`, `0–9` only.
- **Meaning:** stable ID for the file or event — **not** the product version (use `WLW20`, not `WLW19`, for the 2.0 launcher).
- **Uniqueness:** one code per file; don’t reuse across unrelated artifacts.
- **Grove:** `b17: <CODE> — <one-line summary>` as the **last line** of agent event posts (see [`archive/docs/superpowers/specs/2026-04-27-grove-b17-message-convention.md`](../archive/docs/superpowers/specs/2026-04-27-grove-b17-message-convention.md)).

### Prefix hints (informal)

| Prefix | Domain |
|--------|--------|
| `WLW` | Willow product / launcher |
| `SLP` | Sleipnir (`root.py` install) |
| `WGR` | Grove dashboard (`app.py`) |
| `PGB`, `SOIL`, `INT` | Core bridges / store / intelligence |
| `RB*` | Runbooks (`RBPGW`, `RBMCP`, …) |
| `FYL*` | Fylgja powers/skills |
| `SAP` / `b20` | SAP MCP (see below) |

Generate new codes via MCP `fleet_base17` or pick an unused mnemonic before committing.

---

## b20 — SAP MCP generation

**b20** is reserved for the SAP MCP server surface only (protocol generation 2).

```text
b20: SAPMCP2 · ΔΣ=42
```

Used in `sap/sap_mcp.py`, `sap/README.md`, `sap/ONBOARDING.md`. Do not use `b20` on general Willow docs.

---

## Markdown template

```markdown
# Title — Willow 2.0

b17: XXXXX · ΔΣ=42

One-line subtitle or audience.

---

…body…

---

*ΔΣ=42*
```

Runbooks: `b17: RBxxx · ΔΣ=42`  
Wiki pages: `b17: WIKxx · ΔΣ=42` (pick per page)

---

## Python template

```python
#!/usr/bin/env python3
"""
module.py — Short description.
b17: MOD01 · ΔΣ=42
"""
```

---

## Voice (docs)

- Short sentences. No SEO filler.
- Second person for humans (“you”), imperative for agents (“call `kb_search` first”).
- Name real paths and tools (`willow_20`, `kb_ingest`, not legacy `willow_knowledge_*`).
- Philosophy is welcome in one line; procedure wins for onboarding.

---

## Top-level registry (2.0)

| Code | Artifact |
|------|----------|
| `RDM20` | `README.md` |
| `WLWMD` | `willow.md` |
| `WLW20` | `willow.sh` |
| `SLP20` | `root.py` |
| `WGRV1` | `app.py` |
| `AGNTW` | `AGENTS.md` |
| `GEMW2` | `GEMINI.md` |
| `BRND2` | This file |
| `ROOTL` | `docs/ROOT_LAYOUT.md` |
| `DOCIDX` | `docs/INDEX.md` |
| `SAPMCP2` | `sap/sap_mcp.py` (b20) |

---

## A×W-20 (optional crossover)

For **AllHailSeizure** / 40k / r/LLMPhysics beta voice, use the parallel lexicon in [`nomenclature/AXW-20.md`](nomenclature/AXW-20.md). Canonical names remain in code; crossover is for docs, Grove flavor, and friend comms.

---

## Anti-patterns

| Don’t | Do |
|-------|-----|
| `b17: BTA1` without seal | `b17: BTA1 · ΔΣ=42` |
| `b17: WLW19` on 2.0 launcher | `b17: WLW20` |
| `**b17:**` mixed with `b17:` | Pick `b17:` for new docs |
| `willow-1.9` / `willow_19` as defaults | `willow-2.0` / `willow_20` |
| `willow_knowledge_search` in new prose | `kb_search` |

---

*ΔΣ=42*
