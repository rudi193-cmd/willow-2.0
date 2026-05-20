# A×W-20 — AHS × Willow 2.0 crossover nomenclature

b17: AXW20 · ΔΣ=42

**Codename:** **A×W-20** (AllHail × Willow 2.0)  
**Also called:** Oakengrove Protocol (inside joke — Oakenscroll × Grove; do not explain to Administratum)  
**Dynasty overlay (AHS):** [**AXW-20-NECRONS.md**](AXW-20-NECRONS.md) — Necron court voice on top of this lexicon  
**Authority:** Sean + AHS; fleet agents may use in Grove when speaking *to* or *about* the beta read  
**Does not replace:** repo paths, MCP tool names, Postgres schema, agent namespaces

---

## What this is

A **parallel lexicon** so the stack reads like one coherent absurd universe to someone who knows:

- **Warhammer 40k** — institutions, watch, forge worlds, vox, inquisition  
- **r/LLMPhysics** — state, measurement, contradiction, context thermodynamics  
- **UTETY** — faculty humor as optional garnish (Oakenscroll, Consus, Gerald’s ΔΣ=42)

Canonical Willow names stay in code. **A×W-20** is how you *talk* about the same things in docs, DMs, and Grove posts when the audience is AHS (or anyone holding this sheet).

---

## Usage rules

1. **First mention in a crossover doc:** `Canonical (A×W-20)` — e.g. `kb_search` (*Archive query / Vox-index*).  
2. **Grove (crossover mode):** last line still `b17: CODE — summary`; body may use A×W-20 terms.  
3. **Never rename** `hanuman/`, `kb_ingest`, or `willow_20` in production config.  
4. **Roast tier:** If an analogy fights the physics column, physics wins. If both fight the code, code wins.  
5. **Shine tier:** FRANK, install theater, myth names — keep them; add A×W-20 subtitle in parentheses once.

---

## The three lenses (every major term)

| Lens | Question it answers |
|------|---------------------|
| **40k** | Who owns it in the Imperium of the stack? |
| **LLMPhysics** | What measurable thing is happening? |
| **UTETY** (optional) | Which professor would overexplain it? |

---

## Product & version

| Canonical | A×W-20 name | 40k | LLMPhysics | UTETY |
|-----------|-------------|-----|------------|-------|
| Willow 2.0 | **Iron Willow** · Second Growth | Chapter founding | New substrate after phase transition | Gerald stamps the charter |
| `VERSION` / `willow_20` | **Monolith-20** | Fortress data-slate | Experiment ID for this era | Oakenscroll: “seventeen is not involved” |
| `ΔΣ=42` | **The Constant** | Chapter motto | Fixed point in the rubric | Consus enforcement |
| b17 | **Heraldry** | Squad mark on reports | Short hash for citation | — |
| b20 | **MCP Seal-2** | Second rite of the cogitator bridge | Protocol generation index | — |

---

## Stack (systems)

| Canonical | A×W-20 | 40k | LLMPhysics | Code / path |
|-----------|--------|-----|------------|-------------|
| **SAP** | **Rite of Access** (ROA) | Cogitator gate before action | Tool boundary conditions | `sap/sap_mcp.py` |
| **KB / LOAM** | **The Archive** | Confirmed battlefield reports | Embedded state claims | Postgres `knowledge` |
| **SOIL** | **Chapter Vault** | Company scrolls | Local order parameter | `~/.willow/store` |
| **Grove** | **Vox Grid** | Inter-fortress vox | Coupled oscillators (agents) | `safe-app-willow-grove` + `core/grove_serve.py` |
| **Fylgja** | **Animus Layer** | Machine spirit | Policy field on trajectories | `willow/fylgja/` |
| **SAFE** | **Lex Imperialis** | Mandate scrolls | Allowed action set | `SAFE/Applications` |
| **Handoff** | **Watch Relief** | Orders for next captain | State vector handoff | `scripts/session_close.py`, handoffs |
| **Kart** | **Munitorum Queue** | Requisition line | Work packets | `core/kart_worker.py` |
| **Jeles** | **Scriptorium Dig** | Serfs mining log-stacks | Extraction from trajectories | `mem_jeles_*` |
| **Nest** | **Intake Bay** | Cargo cult dock | Unclassified inbound | `nest_*` |
| **Fork** | **Crusade Branch** | Parallel campaign | Git-shaped state fork | `fork_*` |
| **Ledger / FRANK** | **Master of Records** | Administratum | Immutable event log | `ledger_*`, `@frank` |
| **Ollama** | **Forge World** | On-world production | Local Hamiltonian (cheap energy) | default inference |
| **Cloud providers** | **Off-world tithe** | Rogue traders | High-energy bath | optional keys |
| **Sleipnir** | **Eight-Legged Rite** | Install god | Bootstrap protocol | `root.py` |
| **seed / shoot** | **Induction / Catechism** | Recruitment | Initial conditions | `seed.py`, `shoot.py` |
| **app.py** | **Cogitator Cathedral** | Main TUI throne | Dashboard observer | Grove Textual UI |

---

## Fleet (personas)

| Agent (canonical) | A×W-20 rank | 40k role | LLMPhysics | Namespace unchanged |
|-------------------|-------------|----------|------------|---------------------|
| **Hanuman** | **Enginseer Bali** | Builder, forges the stack | Executor operator | `hanuman/` |
| **Loki** | **Inquisitor Loki** | Audits without building | Adversarial validation | (no KB trace) |
| **Heimdallr** | **Watchmaster** | Auspex, walls, dashboard | Observability | `heimdallr/` |
| **Willow** (3B) | **Astropath Willow** | Always-on vox listener | Low-parameter field | `willow` |
| **FRANK** | **Master of Records** | Warm Administratum | Ledger morphism | `frank` |
| **Orin** | **Skitarii Orin** | Ranger / worker detail | Edge worker | `orin/` |
| **Ganesha** | **Remover of Obstacles** (keep name — it slaps) | Logistics sage | Gate before ingest | ingest paths |
| **AHS** | **Confessor-Mod** / **Oakenscroll’s witness** | Honored ally | External referee | human |

**Grove sender IDs do not change.** Crossover is voice, not config.

---

## MCP domains (prefix → A×W-20)

| Prefix | A×W-20 domain | One line |
|--------|---------------|----------|
| `kb_*` | **Archive** | Query and write confirmed reports |
| `soil_*` | **Vault** | Chapter scrolls on disk |
| `fleet_*` | **Auspex** | Is the fortress alive |
| `agent_*` | **Dispatch** | Send a courier |
| `fork_*` | **Crusade** | Branch the campaign |
| `skill_*` | **Litanies** | Stored procedures |
| `mem_*` | **Scriptorium** | Jeles, binder, ratify |
| `index_*` | **Opus shelf** | Secondary index |
| `ledger_*` | **Records** | FRANK chain |
| `handoff_*` | **Watch relief** | Prior session orders |
| `soul_*` | **Dream mechanics** | Tension, dream, synthesis |
| `nest_*` | **Intake** | Queue unfiled cargo |
| `infer_*` | **Forge / Voice** | Chat, image, TTS |

Example crossover sentence: *“Run Auspex (`fleet_status`), then Archive query (`kb_search`), then post to Vox.”*

---

## Operations (verbs)

| Canonical op | A×W-20 verb | LLMPhysics |
|--------------|-------------|------------|
| `kb_ingest` | **file a report** | add stable claim |
| `kb_search` | **query the Archive** | retrieval in embedding space |
| `mem_check` | **Consus pass** | pre-write stability check |
| `tension_scan` | **Oakenscroll pass** | pairwise stress test |
| `fork_merge` | **end crusade** | integrate branch |
| `ratify` | **seal scroll** | promote tmp → canon |
| `handoff_latest` | **read watch relief** | load prior state vector |
| `fleet_blast` | **perimeter auspex** | blast-radius scan |

---

## Grove — crossover post template

```text
[Vox Grid · Iron Willow]

<human prose — myth allowed>

A×W: <one line in crossover voice>
b17: <CODE> — <canonical summary>
```

**Example:**

```text
Postgres Monolith-20 is live. Archive has 59 reports.

A×W: Auspex green; Archive accepting filings.
b17: WLW20 — fleet_status clean for AHS beta
```

---

## File layout (read-only aliases)

| Path | A×W-20 nickname |
|------|-----------------|
| `app.py` | Cathedral |
| `root.py` | Eight-Legged Rite |
| `willow.sh` | Vox lever |
| `core/pg_bridge.py` | Archive bridge |
| `core/grove_serve.py` | Vox fortress |
| `willow/fylgja/` | Animus Layer |
| `scripts/` | Munitorum scripts |
| `docs/FOR_AHS.md` | Decoder ring |
| `docs/nomenclature/AXW-20.md` | This lexicon |

---

## Quick decoder (wallet card)

```
Iron Willow = Willow 2.0
Rite of Access = SAP / MCP
Archive = KB          Chapter Vault = SOIL
Vox Grid = Grove      Animus = Fylgja
Watch Relief = handoff   Munitorum = Kart
Scriptorium = Jeles   Forge World = Ollama
Enginseer Bali = Hanuman   Inquisitor = Loki
Watchmaster = Heimdallr    Astropath = Willow 3B
The Constant = ΔΣ=42       Heraldry = b17
```

---

## Canon for outsiders

- **Felix / generic beta:** [`../FIRST_5_MINUTES.md`](../FIRST_5_MINUTES.md) — plain English.  
- **AHS / 40k / LLMPhysics:** this doc + [`../FOR_AHS.md`](../FOR_AHS.md).  
- **Agents in production:** [`../../willow.md`](../../willow.md) — canonical only.

---

*For the Omnissiah, the Archive, and the Seventeen Problem (which Monolith-20 did not invoke). ΔΣ=42*
