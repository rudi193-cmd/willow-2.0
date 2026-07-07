@markdownai v1.0
# The Illusion of Sovereign AI
### Working outline — research-backed long-form essay
### Evidence base: sociotechnical.db (30 creators, 76 people, 80 edges, 56 observations)

**Citation lanes:** Essay (v3) uses light inline attribution; formal paper (v2) uses full References block below. DB edges are reproducible queries — cite as `sociotechnical.db` + edge type + node IDs in methods footnote.

---

## Working thesis

Every entity claiming to build "sovereign AI" — nations, corporations, communities — is
captured at one or more chokepoints they don't control and can't replace. True AI sovereignty
isn't a model. It's a stack. And the only configuration where that stack is actually sovereign
is local-first, open-weight, running on hardware you own. The AI bubble correcting will make
this not just ideologically compelling but economically obvious.

---

## I. The Promise (hook, ~500 words)

Every government has a sovereign AI story right now.
- France: Mistral. "European AI that doesn't bow to Washington."
- Germany: Aleph Alpha. "GDPR-safe, on-prem, built for regulated industry."
- Saudi Arabia: HUMAIN. "$100B, NVIDIA partnership, Vision 2030."
- India: IndiaAI. "$1.25B, 10,000 GPUs, leveraging the IIT diaspora."
- China: DeepSeek, Qwen, Baidu. "We don't need American models."
- US: OpenAI, Anthropic, SSI, TML, Stargate. "$500B infrastructure. We will not be caught."

They are all, to varying degrees, describing the wrong thing.

**Key argument**: "Sovereign AI" as currently used means "we trained the model." It says
nothing about who makes the chips, who owns the fabrication equipment, who controls the
distribution layer, or whose capital funded the whole thing.

### Citations — Section I

| Claim | Primary sources | DB / notes |
|-------|-----------------|------------|
| France / Mistral sovereignty framing | Vinocur & Cerulus (2023, *Politico*); Mistral AI (2023) | `creators.mistral_ai` |
| Germany / Aleph Alpha on-prem framing | Stokel-Walker (2023, *Wired*); Aleph Alpha (2023 press) | `creators.aleph_alpha` |
| Saudi HUMAIN scale + NVIDIA | PIF (2025); NVIDIA News (2025) HUMAIN partnership | `creators.humain` — cite **NVIDIA partnership** firmly; **$100B** = reported PIF backing (secondary — frame as reported, not audited) |
| India IndiaAI mission | MEITY (2024) | GPU count, diaspora rhetoric |
| China ecosystem (DeepSeek, Qwen) | Roberts (2024, *MIT Technology Review*); DeepSeek (2024, 2025) | `creators.deepseek`, `alibaba_qwen` |
| US Stargate scale | OpenAI (2025) Stargate announcement; AP/CNN Jan 2025 | **Up to $500B over 4 years**; **$100B initial** commitment (not fully deployed Day 1) |
| Thesis: training ≠ sovereignty | Author framing; developed in §II–§VI | No single cite — definitional move |

**Jeles retrieval targets:** EU AI sovereignty policy docs (EC, 2024+); IndiaAI mission primary page; HUMAIN founding announcements (Reuters/FT).

---

## II. The Map (the capture, ~1200 words)

**Tracing the actual dependency chains, not the press releases.**

### The physical chokepoint

```
Every AI model → runs on GPUs → designed by NVIDIA (fabless) → fabricated by TSMC
TSMC requires EUV lithography machines → only made by ASML (Netherlands)
ASML is a de facto monopoly → one Dutch company enables all advanced chip production
```

Wernher von Braun built the rocket. TSMC built the substrate that everything above runs on.
The US pressured the Netherlands to stop selling EUV machines to China (2023). That single
export control decision — one Dutch company, one machine type — does more to constrain
Chinese AI capability than any model-level regulation.

Every "sovereign AI" story terminates here. France's Mistral runs on NVIDIA H100s. Germany's
Aleph Alpha runs on NVIDIA GPUs. India's IndiaAI mission is purchasing GPU clusters. China's
DeepSeek trained on A100s accumulated before export controls hit. Saudi HUMAIN is partnering
with NVIDIA directly.

**DB evidence**: `infrastructure_dependency` edges: OpenAI → NVIDIA → TSMC → ASML.
The chain is documented. Five hops from a ChatGPT query to a Dutch export license.

### The capital map

The Stargate announcement (Jan 2025, White House): OpenAI, SoftBank, Oracle, and **MGX**
(UAE sovereign fund) pledged **up to $500B over four years**, with **$100B initially**
(TechCrunch/OpenAI). Foreign capital is structural. **G42** appears in **Stargate UAE**
(May 2025) as a parallel Gulf cluster — do not conflate with the Jan founding LP list.

Alibaba holds strategic positions in Qwen (in-house), Moonshot AI (Series A lead, $300M),
and Zhipu AI simultaneously — controlling a plurality of the Chinese open-weight ecosystem
from one corporate entity.

Open Philanthropy funds Anthropic (~$580M) AND funds METR — the organization whose job is
to tell Anthropic whether its models are safe to ship. The evaluator's independence is
structurally compromised by the same funder.

**DB evidence**: `strategic_backer` edges, funder exposure table.
The capital layer is not sovereign. It is captured.

### The talent pipeline

Three pipelines feed almost every lab:
1. **OpenAI diaspora**: Anthropic, SSI, TML all trace direct lineage. OpenAI is the
   university of the AI era.
2. **IIT → US tech → now being asked to "return"**: Pichai (Google), Nadella (Microsoft),
   Srinivas (Perplexity) — the talent that built American tech empires is now the resource
   India wants back. The pipeline flows one way because of 10-20x salary differentials.
3. **Returned talent (China)**: Yang Zhilin (Moonshot) — CMU PhD, Google Brain, returned
   to Hangzhou. Same arc as Paperclip in reverse: train talent in one context, deploy it in
   another.

### The distribution layer

Hugging Face: every major open-weight model (LLaMA, Mistral, Qwen, DeepSeek-R1) distributed
through a single neutral platform. Series D investors: Google, Amazon, NVIDIA, Salesforce,
Intel — the four largest closed-model competitors all holding equity in the neutral
infrastructure. They own the platform that distributes their competitors' weights.
That is not neutral. That is managed neutrality.

### Citations — Section II

#### II.A Physical chokepoint

| Claim | Primary sources | DB edges |
|-------|-----------------|----------|
| NVIDIA fabless → TSMC fabs | ASML (2024 annual report); industry primers | `infrastructure_dependency`: nvidia → tsmc |
| ASML EUV monopoly | ASML (2024); BIS (2023) | `infrastructure_dependency`: tsmc → asml |
| US/NL/JP export controls on China | BIS (2022 interim final rule); BIS (2023 expansion) | observation: export controls efficiency acceleration |
| Mistral / Aleph / IndiaAI on NVIDIA | Mistral AI (2023); Aleph Alpha (2023); MEITY (2024) | per-creator `infrastructure_dependency` |
| DeepSeek on pre-control A100s | DeepSeek (2024 V3 report); Roberts (2024) | `creators.deepseek` + BIS (2022) timeline |
| Five-hop chain OpenAI → ASML | Author analysis | `infrastructure_dependency` chain documented in DB |

#### II.B Capital map

| Claim | Primary sources | DB edges |
|-------|-----------------|----------|
| Stargate $500B / $100B initial, foreign LPs | OpenAI (2025); AP (2025-01-21) | OpenAI, SoftBank, Oracle, MGX; G42 = Stargate UAE (May 2025) |
| Alibaba three-prong (Qwen, Moonshot, Zhipu) | Crunchbase; Moonshot (2023) | `strategic_backer`: alibaba_group → moonshot_kimi, zhipu_ai, alibaba_qwen |
| Open Phil → Anthropic + METR | Open Philanthropy (2023, 2024a, 2024b) | `strategic_backer` + observation: evaluator capture |
| Sequoia China decoupling | News coverage 2023 | `geopolitical_split`: sequoia_china → openai |

#### II.C Talent pipeline

| Claim | Primary sources | DB edges |
|-------|-----------------|----------|
| OpenAI → Anthropic founders | Anthropic (2021) | `spawned_talent`: openai → anthropic |
| OpenAI → SSI (Sutskever) | SSI (2023) | `spawned_talent`: openai → ssi |
| OpenAI → TML | TML (2024) | `spawned_talent`: openai → tml |
| IIT diaspora / IndiaAI repatriation | MEITY (2024); biographical (Pichai, Srinivas — Wikipedia/Corp bios for essay only) | `returned_talent` / `academic_origin` where populated |
| Yang Zhilin / Moonshot return arc | Moonshot (2023) | `returned_talent`: yang_zhilin pattern |

#### II.D Distribution layer

| Claim | Primary sources | DB edges |
|-------|-----------------|----------|
| HF hosts LLaMA, Mistral, Qwen, DeepSeek-R1 | Meta AI (2023); Mistral (2023); Hugging Face hub pages | `ecosystem_node`: huggingface |
| HF Series D investors (Google, Amazon, NVIDIA, Salesforce, Intel) | Hugging Face (2023 press) | observation: HF Switzerland / managed neutrality |
| Closed labs invested in open distribution | Hugging Face (2023) | observation: all competitors in neutral infra |

**Jeles retrieval targets:** BIS Federal Register texts; ASML annual report EUV section; Reuters Stargate investor breakdown; Crunchbase Alibaba–Moonshot round.

---

## III. The Money (bubble analysis, ~1000 words)

**The numbers:**

| Entity | Raised | Peak Valuation | Revenue est. |
|---|---|---|---|
| OpenAI | **$122B** committed (Mar 2026) | **$852B** post-money | **~$24B ARR** ($2B/mo) |
| Anthropic | **$65B** Series H (May 2026) | **$965B** post-money | **~$47B** run-rate |
| SSI | $4B | $32B | $0 |
| TML | $2B | unknown | $0 |
| xAI | $12B | $50B | limited |
| Perplexity | $0.6B | $9B | limited |

Hyperscaler AI CapEx: **~$650–700B** combined guide for **2026** (~2× FY2025 ~$300B Big Four total).
At illustrative 5×: **~$130B** AI-attributed revenue to justify 2026 capex (not ~$51B implied by 2025 guides).
**Lab revenue exists at scale:** OpenAI ~$24B ARR + Anthropic ~$47B run-rate (Jun 2026 primary sources).
**Tightened thesis:** capex/valuation got there first; stress test = leverage, margin direction, financing appetite — not "will AI ever monetize.
**Causality bridge (v3):** §II physical scarcity (ASML/TSMC/GPU allocation) → §III capex arms race; hyperscalers bid up constrained assets from fear of lockout.

**The three triggers:**

**1. The efficiency cliff** (running in H1 2026)
DeepSeek-V3 ~$5–6M final pretrain; **V4 Apr 2026**; API cuts through H1 2026.
Sub-$1M = distilled/inference scenario, not next frontier pretrain (Epoch: frontier costs rising).
**Trigger mechanism:** margin compression on **$850B+** valuations, not absence of revenue.
The constraint that US export controls created — forcing DeepSeek to optimize on A100s
rather than H100s — produced the breakthrough that is now threatening the entire US AI
business model. A classic unintended consequence.

**2. The CapEx disappointment** (2026–2027 earnings)
**$650–700B** 2026 capex guides vs AI-attributed **margin** (not raw lab run-rates).
Three–four quarters of spend outrunning margin triggers repricing. The hyperscalers don't die —
they're profitable. But their AI bets get discounted, and every lab dependent on cloud
partnerships loses leverage.

**3. Recession accelerant** (wildcard)
AI is still a software budget line to most CFOs. A real recession freezes enterprise
procurement. Labs burning $3-5B/year cannot survive a 6-month freeze.

**Prediction timeline:**

- **Now (Jun 2026)**: Peak valuation + margin compression coexist. OpenAI $122B/$852B; Anthropic $65B/$965B; V4/Kimi/Qwen3.5 H1 2026.
- **Late 2026**: First cracks. Mid-tier labs fail to raise follow-ons at 2024 valuations.
- **2026-2027**: Efficiency trigger. Next DeepSeek moment. API prices drop. Revenue falls.
- **2027**: CapEx reckoning in earnings. NVIDIA gives back 40-60% (it did 65% in 2022).
- **2027-2028**: Consolidation. 40-60% valuation haircut sector-wide.

**Who survives:**
NVIDIA/TSMC/ASML (substrate), **OpenAI + Anthropic** (revenue scale — return on $850B–$965B entries is separate question), Mistral, DeepSeek, Hugging Face, Cohere.

**Who doesn't:**
SSI ($32B, $0 revenue — can't raise follow-on in a down market), TML (credibility doesn't
pay salaries forever), several Chinese consumer labs, Scale AI (automating its own core
business).

### Citations — Section III

| Claim | Primary sources | DB / notes |
|-------|-----------------|------------|
| Lab valuations & raises | Crunchbase; Bloomberg/WSJ round coverage | `funding_rounds` table |
| Hyperscaler CapEx ~$650–700B (2026 guide) | CNBC Feb 2026; Fortune Apr 2026; Futurum Feb 2026 | ~2× 2025 Big Four total; Google ~$180–190B alone |
| ~$130B revenue @ 5× (2026 capex) | Author calc from $650B guide | Replaces ~$51B / 2025-capex frame |
| Lab run-rates OpenAI + Anthropic ~$70B | OpenAI Mar 31 2026; Anthropic May 28 2026 | Primary — company-reported; not whole-stack revenue |
| Sector AI revenue $20–30B (2025 est.) | Goldman Sachs (2025); Sequoia (2024) | **Superseded** for frontier labs — keep for historical contrast only |
| DeepSeek-V3 ~$6M training | DeepSeek (2024); Epoch AI (2025) | `triggered` edges: deepseek → price war |
| API price cuts post-DeepSeek | The Verge (2025) | observation + news |
| Export control → efficiency irony | BIS (2022); DeepSeek (2024); author synthesis | observation: export controls efficiency acceleration |
| NVIDIA 65% drawdown 2022 | NVIDIA Corporation (2022 annual report) | Historical analog — not prediction |
| SSI $0 revenue / follow-on risk | SSI (2023); Crunchbase | `creators.ssi` |
| Scale AI revenue / automation risk | Scale.com blog (2025); Sacra; TechCrunch Series F | **$870M FY2024**, **~$2B ARR 2025** est.; dual lines: **data** (labeling, profitable 2025) + **applications** (2× H2 2025) — no public % split; Meta ~$14.3B stake 2025 |

**Jeles retrieval targets:** Goldman Sachs AI spend note; Sequoia "rule of 40" AI piece; Epoch AI training cost dataset; hyperscaler 10-Q CapEx footnotes.

---

## IV. The Efficiency Convergence (the key insight, ~700 words)

**Broader pattern (opening — DRAFTED in v3):** Scarcity/policy constraint → algorithmic optimization. Paperclip, export controls, Mistral, DeepSeek. Pattern: **constraint → invention → ratchet**.

Two labs. Different continents. Different constraints. Same conclusion.

**Mistral** (Paris, 2023): European sovereignty framing. No access to closed US APIs.
No massive corporate backer. Trained Mistral 7B on commodity hardware. Matched LLaMA 2 13B.
Released weights. Proved small + efficient > large + expensive.

**DeepSeek** (Hangzhou, 2024): US export controls blocked H100 access. High-Flyer had
~10,000 A100s accumulated before the window closed. Forced to find algorithmic efficiency
rather than throw compute at the problem. Result: DeepSeek-V3 trained for $6M, matched GPT-4.
R1 matched o1.

The constraint produced the insight. This is not coincidence.

When you cannot buy more compute, you have to think harder about the compute you have.
Both labs independently discovered mixture-of-experts, better data curation, and training
efficiency techniques that the US frontier labs — who could always just buy more H100s —
had no incentive to pursue.

The efficiency trend is a one-way ratchet. Models get smaller, faster, more capable per
parameter. The direction does not reverse.

### Citations — Section IV

| Claim | Primary sources | DB / notes |
|-------|-----------------|------------|
| Mistral 7B matches LLaMA 2 13B at half params | Jiang et al. (2023, arXiv:2310.06825); Mistral AI (2023) | `model_releases.mistral_7b` |
| Mistral founding / constraint context | Mistral AI (2023); Vinocur & Cerulus (2023) | `spawned_talent` from meta/deepmind |
| DeepSeek-V3 cost & GPT-4 parity | DeepSeek (2024, arXiv:2412.19437); Epoch AI (2025) | `triggered` downstream |
| DeepSeek-R1 / o1-class reasoning | DeepSeek (2025, arXiv:2501.12948) | |
| A100 accumulation pre–Oct 2022 controls | Reuters (2025-01-29); SemiAnalysis; Fortune (2025-01-27) | **~10,000 A100s by 2021** (High-Flyer) — press/analyst corroborated, not DeepSeek filing |
| MoE / efficiency techniques | DeepSeek (2024) technical report | |
| Constraint-insight mechanism (thesis) | Author synthesis; parallel to §II export-control observation | Not empirical claim — structural argument |
| Efficiency ratchet one-way | Epoch AI (2025) trends; DeepSeek V3 report | Frontier **costs rising** (Epoch); sub-$1M = **author projection** for efficient/distilled tier — label explicitly |

**Jeles retrieval targets:** DeepSeek V3/R1 papers (arXiv); Mistral 7B paper; Epoch AI compute trend charts; BIS 2022 rule effective date.

---

## V. The Post-Bubble Landscape (the prediction, ~600 words)

**Broader pattern (opening — DRAFTED in v3):** Overbuild → repricing → survivors matched to substrate. Postwar aerospace rhyme; post-AI survivors = chokepoint owners + efficiency-native open-weight — not infinite-API-margin labs.

When API prices collapse to near-zero (efficiency cliff), the cost argument for remote
AI disappears. The delta between "pay $0.03/M tokens" and "run it locally for free after
hardware amortization" narrows to noise. The only remaining argument for the cloud API is
convenience.

Convenience is not sovereignty.

Every institution, government, school system, hospital, and individual who wants:
- Data privacy (their queries don't train someone else's model)
- Operational independence (works without internet, without a vendor relationship)
- Budget certainty (no surprise API pricing changes)
- Jurisdictional compliance (data doesn't leave the building)

...will have no financial reason *not* to go local. The ideology and the economics align.

The labs that survive the bubble are the ones that positioned on efficiency. Which is
exactly the cluster the sovereignty argument needs.

### Citations — Section V

| Claim | Primary sources | DB / notes |
|-------|-----------------|------------|
| API pricing collapse scenario | The Verge (2025); Sequoia (2024); author forecast | Tied to §III triggers |
| Hospital / legal / gov data-sovereignty needs | GDPR, HIPAA, FERPA (legal frameworks — cite statutes in v2 only) | Essay: name regimes, no full legal cite required |
| Local vs API cost crossover | arnesund.com (2024) M3 Pro 36GB; mljourney.com M-series tests | **7B Q4: ~50–80 tok/s** (M3/M4 class); **13B: ~25–45 tok/s** ballpark — cite range, not point |
| Survivors = efficiency cluster | §III survivor table; Mistral, DeepSeek, HF | `creators` cost structure |
| "Convenience is not sovereignty" | Author framing | Rhetorical capstone |

**Jeles retrieval targets:** Enterprise AI procurement surveys 2025–26; OpenAI/Anthropic pricing history; GDPR AI Act deployment guidance for on-prem.

---

## VI. What Sovereignty Actually Requires (the local-first thesis, ~700 words)

**Broader pattern (opening — DRAFTED in v3):** Sovereignty = stack runnable without permission. Paperclip/Huntsville facilities persist; rented H100 + API = title without control.

Not a national model. Not a national compute cluster. Those are sovereign the way a house
on a floodplain is "owned" — you hold the title, but you don't control the conditions.

Real sovereignty requires:
1. **Weights you can download and keep** — open-weight models, not API-only access
2. **Hardware you own** — not cloud instances you rent
3. **Inference software you run** — llama.cpp, Ollama, or equivalent
4. **Isolated local data infrastructure** — local RAG, on-prem fine-tuning; anchor models to
   your records/reality, not the internet average
5. **No dependency that can be revoked** — no license that expires, no API key that gets
   suspended, no vendor that can raise prices or shut down

The stack that meets these requirements exists today:
- **Models**: Mistral 7B, LLaMA 3 8B, Qwen 2.5 7B, DeepSeek-R1-Distill
- **Inference**: llama.cpp / Ollama (runs on Apple Silicon, Linux, even Raspberry Pi 5)
- **Distribution**: Hugging Face (with caveats — you should mirror locally)
- **Hardware**: Apple M-series, NVIDIA consumer GPUs (3090/4090), AMD RDNA
- **Architecture future**: RISC-V (open instruction set, no company controls it)

The gap between this stack and frontier API performance is closing every 6 months.
By the time the bubble corrects (2027-2028), a locally-run open model will be within
acceptable range of GPT-5 for 80-90% of use cases.

**The companies to watch** (the ones actually enabling sovereignty):
- Mistral: small models, open weights, European jurisdiction
- DeepSeek: efficiency research, open weights, no VC dependency
- Hugging Face: distribution infrastructure (with the caveat that you should mirror)
- The llama.cpp/Ollama ecosystem: the inference runtime that makes it practical
- RISC-V Foundation: the hardware future that escapes the TSMC/NVIDIA chokepoint
  (longer timeframe — 5-10 years, but the only path to true hardware sovereignty)

**The companies that claim sovereignty but don't deliver it:**
- Any national AI mission that runs on NVIDIA GPUs (all of them, currently)
- Any "sovereign cloud" that still routes through US hyperscaler infrastructure
- Any open-weight model distributed only through Hugging Face without a mirror strategy

### Citations — Section VI

| Claim | Primary sources | DB / notes |
|-------|-----------------|------------|
| Four sovereignty criteria (framework) | Author operational definition; aligned with v2 §7 | Normative — not disputed fact |
| Mistral 7B / 8x7B Apache 2.0 | Jiang et al. (2023); Mistral license pages | |
| LLaMA 3 license (partial sovereignty) | Meta AI (2023) | Meta license restricts some commercial use |
| Qwen 2.5 Apache | Alibaba DAMO / Qwen release notes | |
| DeepSeek-R1-Distill MIT | DeepSeek (2025) | |
| llama.cpp MIT | Gerganov (2023) | |
| Ollama | Ollama (2024) | |
| Apple Silicon / consumer GPU viability | arnesund.com (2024); llama.cpp Metal discussion; modelpiper.com | M3 Pro 36GB: 7B fast; 13B usable (~25–45 tok/s Q4_K_M); 70B marginal |
| RISC-V open ISA | RISC-V International (2024) | 5–15 yr horizon — state explicitly |
| HF mirror caveat | Hugging Face ToS; author ops guidance | |
| National GPU clusters still on NVIDIA | §II hardware chain | |
| "Sovereign cloud" on Azure/AWS | EC Cloud Sovereignty Framework (2024); Delos Cloud; IONOS/govdigital (2024); OVH; T-Systems ISG 2024; Microsoft sovereign EU (2025) | **Pattern:** EU operator wrapper on hyperscaler — Delos (Azure/DE public sector), T-Systems, IONOS, OVH; Gaia-X = federation framework not a vendor |

**Jeles retrieval targets:** Meta LLaMA 3 license text; RISC-V spec; Ollama hardware docs; EU sovereign cloud offerings (Gaia-X, etc.).

---

## VII. The Synthesis (closing, ~400 words)

The through-line from the Paperclip DB to the sociotechnical DB to the bubble prediction:

Every era of strategic technology has the same structure:
- A small number of physical or intellectual chokepoints
- A capital layer that flows toward those chokepoints
- A "national security" or "strategic advantage" framing that overrides ethical scrutiny
- A reckoning when the bets don't pay out at the implied scale

Wernher von Braun built rockets. The US decided the strategic value exceeded the ethical
cost. The institutional lineage runs unbroken to Leidos (**$16.66B FY2024 revenue**), to Cummings Research Park
(**26,000 employees** per CRP official site — park aggregate; Huntsville Business Journal Jul 2024), to Blue Origin testing engines at **NASA Marshall Test Stand 4670** on the Redstone/MSFC campus (not necessarily von Braun's Redstone Test Stand NHL).

The AI version of this story is being written right now. Saudi capital flowing into US AI
infrastructure. UAE tech deals conditioned on removing Chinese components. Export controls
that accidentally created the efficiency breakthroughs that destabilized the labs they were
meant to protect.

The difference this time: the technology is becoming small enough to escape the chokepoints.
A 7B parameter model runs on a MacBook. A quantized reasoning model runs on a Raspberry Pi 5.
The efficiency ratchet is turning in one direction.

The bubble will correct. The chokepoints will remain. But for the first time, the capability
you need for real AI sovereignty fits on a device that costs less than a month of API access.

### Citations — Section VII

| Claim | Primary sources | DB / notes |
|-------|-----------------|------------|
| Paperclip → Redstone → MSFC lineage | Public OSINT; Dispatches postwar packet | `operation_paperclip_genealogy.db` — private; cite published histories for essay |
| von Braun / test stand continuity | Blue Origin (2020) — engines tested at **NASA Marshall Test Stand 4670** on Redstone/MSFC campus | **Do not** claim von Braun's Redstone Test Stand NHL unless sourced — use 4670 / MSFC infrastructure |
| Leidos / Cummings scale | Leidos FY2024 (PR Newswire 2025-02-11); [CRP About](https://cummingsresearchpark.com/about) | **$16.66B** Leidos; **26,000** CRP park-wide aggregate (marketing) |
| Saudi / UAE capital in US AI | OpenAI Stargate (2025); Gulf tech deal reporting | §II overlap |
| Export controls → DeepSeek irony | BIS (2022); DeepSeek (2024) | §III–IV overlap |
| 7B on MacBook / Pi 5 | Stratosphere IPS (2025); Jeff Geerling (2025); buyzero.de | **Pi 5:** 1–3B models **~8–10 tok/s**; 3B ~5 tok/s; **R1-distill 1.5B ~10 tok/s** — not full R1 at usable speed; debunk 200 tok/s viral claim |
| Cross-era pattern (thesis) | Author synthesis across sociotechnical.db + Paperclip DB | Methods section in v2 |

**Jeles retrieval targets:** NASA MSFC historical timeline; Blue Origin Huntsville engine test announcements; Operation Paperclip public histories (Ordway, Neufeld).

---

## Master reference list (v2 formal lane)

Use in `DRAFT_v2.md` References; essay lane picks 1–2 cites per section inline.

- Aleph Alpha. (2023). Series B press release.
- Alphabet Inc. (2025). Q4 2024 earnings.
- Amazon.com, Inc. (2025). Q4 2024 earnings.
- Anthropic. (2021). Founding announcement.
- ASML Holding N.V. (2024). Annual report 2023.
- Blue Origin. (2020). Huntsville engine factory / Test Stand 4670 testing.
- Bureau of Industry and Security. (2022). Advanced computing export controls (87 FR 62186).
- Bureau of Industry and Security. (2023). China semiconductor expansion controls.
- DeepSeek. (2024). V3 technical report (arXiv:2412.19437).
- DeepSeek. (2025). R1 report (arXiv:2501.12948).
- Epoch AI. (2025). Training compute dataset.
- Gerganov, G. (2023). llama.cpp.
- Goldman Sachs. (2025). AI investment framing.
- Hugging Face. (2023). Series D press release.
- Jiang et al. (2023). Mistral 7B (arXiv:2310.06825).
- Leidos. (2025). FY2024 results press release.
- Meta AI. (2023). LLaMA announcement.
- Microsoft Corporation. (2025). FY25 Q2 earnings.
- MEITY, Government of India. (2024). IndiaAI mission.
- Mistral AI. (2023). Mistral 7B release.
- Moonshot AI. (2023). Company overview.
- NVIDIA Corporation. (2022). Annual report (2022 drawdown).
- NVIDIA Corporation. (2025). HUMAIN strategic partnership press release.
- Ollama. (2024). Project repository.
- Open Philanthropy. (2023, 2024a, 2024b). Anthropic + METR grants.
- OpenAI. (2025). Announcing The Stargate Project.
- OpenAI. (2025). Introducing Stargate UAE.
- Public Investment Fund. (2025). HUMAIN launch press release.
- Reuters. (2025-01-29). High-Flyer / DeepSeek GPU accumulation.
- OpenAI. (2026). $122B funding round (Mar 31).
- Anthropic. (2026). Series H ($65B, May 28).
- Reuters. (2025-03-31). OpenAI $40B funding round [superseded by Mar 2026 round].
- RISC-V International. (2024). Specifications overview.
- Roberts, H. (2024). China's AI efficiency turn. *MIT Technology Review*.
- Saudi Press Agency. (2025). HUMAIN launch.
- Sequoia Capital. (2024). Generative AI revenue note.
- SSI. (2023). Founding announcement.
- Stokel-Walker, C. (2023). Aleph Alpha. *Wired*.
- The Machine Learning Institute. (2024). Founding announcement.
- The Verge. (2025). API price cuts after DeepSeek.
- Vinocur, J., & Cerulus, L. (2023). Mistral / Europe. *Politico*.
- White House. (2025). Stargate fact sheet.

---

## DB edge index (reproducible)

| Edge type | Example chain | Sections |
|-----------|---------------|----------|
| `infrastructure_dependency` | openai → nvidia → tsmc → asml | II, VI, VII |
| `strategic_backer` | alibaba_group → moonshot_kimi, zhipu_ai, alibaba_qwen | II |
| `strategic_backer` | open_philanthropy → anthropic; open_philanthropy → metr | II |
| `spawned_talent` | openai → anthropic, ssi, tml | II |
| `returned_talent` | US training → moonshot (Yang Zhilin) | II |
| `geopolitical_split` | sequoia_china decoupling | II |
| `triggered` | deepseek releases → API price cuts / competitor response | III, IV |
| `ecosystem_node` | huggingface as distribution hub | II, VI |

**Key observations (titles from research log — query DB for full text):**
- HF Switzerland / managed neutrality (closed labs fund open hub)
- Google Transformer paradox (invented architecture, lost product moment)
- Export controls → efficiency acceleration
- Alibaba kingmaker (three-prong Chinese open-weight)
- Amazon/Microsoft deal quality comparison

---

## Jeles verification pass (2026-06-22)

**Method:** `mem_jeles_ask` (verify=true) hit local corpus only on current-events queries — irrelevant lesson hits. Follow-up: `mem_jeles_web_search` + `willow_web_search` for primary/press sources. Results written back above.

| Flag | Verdict | Best cite | Essay framing |
|------|---------|-----------|---------------|
| Stargate $500B | **Corroborated** | [OpenAI — Announcing The Stargate Project](https://openai.com/index/announcing-the-stargate-project/); [AP Jan 2025](https://apnews.com/article/trump-ai-openai-oracle-softbank-son-altman-ellison-be261f8a8ee07a0623d4170397348c41) | "Up to $500B over four years"; $100B initial — aspiration + phased, not cash on hand |
| Stargate LPs / G42 | **Partially resolved** | Jan founders: OpenAI, SoftBank, Oracle, **MGX**. G42 = [Stargate UAE May 2025](https://openai.com/index/introducing-stargate-uae/) | Split US founding vs Gulf cluster; fix conflation in §II prose |
| HUMAIN + NVIDIA | **Corroborated** (partnership) | [NVIDIA News — HUMAIN partnership](https://nvidianews.nvidia.com/news/humain-and-nvidia-announce-strategic-partnership-to-build-ai-factories-of-the-future-in-saudi-arabia); [PIF press](https://www.pif.gov.sa/en/news-and-insights/press-releases/2025/hrh-crown-prince-launches-humain-as-global-ai-powerhouse/) | NVIDIA partnership: firm. $100B: reported backing — cite PIF/NVIDIA first |
| OpenAI raised | **Updated Jun 2026** | [OpenAI Mar 31 2026](https://openai.com/index/accelerating-the-next-phase-ai/); CNBC | **$122B committed**, **$852B** post-money, **~$24B ARR** ($2B/mo) |
| High-Flyer ~10k A100 | **Corroborated** (press) | [Reuters Jan 2025](https://www.reuters.com/technology/artificial-intelligence/high-flyer-ai-quant-fund-behind-chinas-deepseek-2025-01-29/); SemiAnalysis | ~10,000 A100s completed **2021**, pre-export controls |
| Hyperscaler CapEx | **Updated Jun 2026** | CNBC Feb 2026; Fortune Apr 2026 | **~$650–700B** 2026 guide; ~$130B revenue @ 5× implied |
| Anthropic Series H | **Updated Jun 2026** | [Anthropic May 28 2026](https://www.anthropic.com/news/series-h) | **$65B**, **$965B**, **~$47B** run-rate |
| Blue Origin / test stands | **Corroborated** (narrow) | [Blue Origin Huntsville factory](https://www.blueorigin.com/news/blue-origin-opens-huntsville-engine-factory) | BE-4 tested at **Marshall Test Stand 4670** — campus continuity, not specific von Braun stand |
| Leidos revenue | **Corroborated** | Leidos FY2024: **$16.66B** (Feb 2025 release) | Update essay from $16.7B; stamp FY2024 |
| DeepSeek $6M training | **Single-source** (paper) | DeepSeek V3 report; Epoch AI | Keep; cross-check Epoch for essay |
| Pi 5 / M3 benchmarks | **Corroborated** (ranges) | Stratosphere IPS (2025); arnesund.com (2024) | Pi 5: small/distill only; M3 Pro: 7B fast, 13B usable |
| Scale AI revenue mix | **Partially resolved** | [Sacra](https://sacra.com/c/scale-ai/); [Scale blog 2025](https://scale.com/blog/scales-next-era-building-for-2026) | Data + applications lines; data profitable 2025; no audited split |
| sub-$1M frontier forecast | **Reframed** | [Epoch AI trends](https://epoch.ai/trends); [Epoch DeepSeek R1](https://epoch.ai/gradient-updates/what-went-into-training-deepseek-r1) | Epoch: frontier **rising**; $5.3M = V3 **final pretrain** only; sub-$1M = author scenario for efficient tier / API collapse — not Epoch baseline |

**Jeles corpus note:** For 2025–26 tech/finance claims, start with `willow_web_search` or empty corpus + live fallback; `mem_jeles_ask` alone can miss when corpus returns irrelevant hits.

## Jeles verification pass 2 (2026-06-22)

**Remaining [VERIFY] flags — Epoch / web / bench synthesis.**

| Flag | Verdict | Best cite | Essay framing |
|------|---------|-----------|---------------|
| sub-$1M frontier training | **Reframed — not Epoch** | [Epoch trends](https://epoch.ai/trends); [Epoch on DeepSeek V3 ~$5.3M](https://epoch.ai/gradient-updates/what-went-into-training-deepseek-r1) | Epoch documents **rising** frontier spend ($390M class 2024; $1B+ by 2027). DeepSeek **$5–6M** = final V3 pretrain slice only (excludes prior R&D/cluster). Sub-$1M = **author scenario** for API-margin collapse via efficiency — distinguish from next-gen pretrain budget |
| Scale AI revenue mix | **Partially resolved** | [Sacra](https://sacra.com/c/scale-ai/); [Scale CEO blog 2025](https://scale.com/blog/scales-next-era-building-for-2026); [TechCrunch Series F](https://techcrunch.com/2024/05/21/data-labeling-startup-scale-ai-raises-1b-as-valuation-doubles-to-13-8b/) | $870M→~$2B ARR; **data business** (labeling) + **applications** (fast-growing); data profitable 2025; Meta strategic stake — no public revenue % |
| EU sovereign cloud vendors | **Corroborated** | [EC Cloud Sovereignty Framework PDF](https://commission.europa.eu/document/download/09579818-64a6-4dd5-9577-446ab6219113_en); [Delos Cloud](https://www.deloscloud.de/); [IONOS/govdigital Jul 2024](https://www.ionos-group.com/investor-relations/newsroom/sovereign-cloud-for-the-public-sector-ionos-available-via-govdigital.html); [OVH sovereign](https://www.ovhcloud.com/en/about-us/sovereign-cloud/); [T-Systems ISG 2024](https://www.t-systems.com/de/en/insights/analyst-ratings/cloud-services/isg-provider-lens-2024-multi-public-cloud-europe) | Gaia-X = **standards/federation**, not a cloud. "Sovereign" offerings = **EU-operated** layers on Azure/AWS/GCP (Delos, T-Systems) + native EU hosts (OVH, IONOS) |
| Cummings 26,000 workers | **Corroborated** | [CRP About](https://cummingsresearchpark.com/about/); [Encyclopedia of Alabama](https://encyclopediaofalabama.org/article/cummings-research-park/); [Huntsville Business Journal Jul 2024](https://huntsvillebusinessjournal.com/news/2024/07/15/huntsville-best-in-state-for-new-tech-grads-ranks-top-ten-nationwide/) | 26,000 = **park-wide** employee count (300+ companies); current marketing — not Leidos-only |
| M3 Pro inference (13B) | **Corroborated** (range) | [arnesund.com M3 Pro Dec 2024](https://arnesund.com/2024/12/02/performance-benchmarking-local-llms-on-macbook-pro-m3-pro/); [mljourney M-series](https://mljourney.com/mac-m1-vs-m2-vs-m3-vs-m4-for-running-llms-real-tests/) | 36GB M3 Pro: **7B Q4 ~50–80 tok/s** class; **13B ~25–45 tok/s** — cite range; 70B too slow for interactive |
| Pi 5 / R1 distill | **Corroborated** (narrow) | [Stratosphere IPS May 2025](https://www.stratosphereips.org/blog/2025/6/5/how-well-do-llms-perform-on-a-raspberry-pi-5); [Jeff Geerling 2025](https://www.jeffgeerling.com/blog/2025/how-deepseek-r1-on-raspberry-pi/); [ITS FOSS debunk](https://itsfoss.com/deepseek-r1-raspberry-pi-5/) | **1–3B** models only at usable speed (~8–10 tok/s); 3B ~5 tok/s; viral **200 tok/s** debunked — use **distill** sizes, not full R1 |


## Jeles verification pass 3 (2026-06-21)

**June 2026 financial refresh — primary sources.**

| Item | Verdict | Source |
|------|---------|--------|
| OpenAI | **Updated** | [OpenAI Mar 31 2026](https://openai.com/index/accelerating-the-next-phase-ai/) — $122B, $852B, $2B/mo |
| Anthropic | **Updated** | [Anthropic May 28 2026](https://www.anthropic.com/news/series-h) — $65B Series H, $965B, $47B run-rate |
| Hyperscaler CapEx 2026 | **Updated** | CNBC/Fortune/Futurum Feb–Apr 2026 — ~$650–700B guide |
| §III bubble thesis | **Retargeted** | Capex/valuation ahead of margins; efficiency compresses unit economics |
| Leidos | **Updated** | FY2025 **$17.17B** (Feb 2026 results) |


---

## Format notes

- **Length**: 5,000-7,000 words
- **Tone**: Data-grounded, not alarmist. The point is structural, not conspiratorial.
- **Audience**: Tech-literate but not insider. Someone who has heard of OpenAI and Mistral
  but hasn't traced the dependency chains.
- **Format**: Long-form essay (Substack / Works in Progress / Asterisk style)
- **What makes it different**: The DB evidence. This isn't vibes-based. The edges and
  observations are citable, reproducible, and the DB is queryable.
- **Next drafting pass**: Voice/through-line rewrite landed in DRAFT_v3 (Jun 21, 2026) — human cadence, Paperclip/Huntsville woven §I–VI, §VII shortened to Coda (~2.7k words). Optional: expand §III/§IV if depth needed; public excerpt to DispatchesFromReality.
