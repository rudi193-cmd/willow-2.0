@markdownai v1.0

# The Illusion of Sovereign AI: Chokepoints, Capital, and the Structural Limits of National AI Policy

**Sean Campbell**
Independent Researcher

*Correspondence:* rudi193@gmail.com

*Data availability:* The relational evidence base underlying this analysis (`sociotechnical.db`) is a structured SQLite database of 30 AI organizations, 76 persons of interest, 41 funders, 40 funding rounds, and 80 relationship edges derived from public sources. Available from the author upon request.

---

## Abstract

National governments and major technology corporations have increasingly framed their AI development initiatives under the rubric of "sovereign AI" — the claim that domestically developed AI systems confer strategic autonomy. This paper argues that such claims systematically misidentify the locus of dependency. Through structural analysis of hardware supply chains, capital formation patterns, talent pipelines, and distribution infrastructure, the paper demonstrates that every major sovereign AI initiative is captured at one or more chokepoints that are neither domestically controlled nor practically replaceable on policy-relevant timescales. A relational database of AI ecosystem actors and edges is used to trace the dependency chains underlying prominent national AI narratives. The paper then applies financial analysis to current AI sector valuations and capital expenditure commitments to forecast a market correction in the 2027–2028 window, driven by training efficiency convergence (the "efficiency cliff"), hyperscaler CapEx-to-revenue divergence, and recessionary sensitivity. The paper concludes that post-correction economics will render local-first, open-weight AI deployment not only ideologically preferable but financially dominant for a large class of institutional actors. A framework is proposed for distinguishing genuine AI sovereignty (open weights, owned hardware, revocable-dependency-free inference) from its rhetorical substitutes.

**Keywords:** sovereign AI, AI governance, semiconductor supply chain, open-weight models, AI bubble, local-first AI, geopolitical technology policy, TSMC, ASML, Hugging Face

---

## 1. Introduction

The concept of "sovereign AI" has achieved significant rhetorical currency in national technology policy. France's backing of Mistral AI is framed as "European AI that doesn't bow to Washington" (Vinocur & Cerulus, 2023). Germany's Aleph Alpha positioned itself as a "GDPR-safe, on-premises" alternative for regulated industry (Stokel-Walker, 2023). Saudi Arabia's HUMAIN initiative, announced with $100 billion in committed capital, claims to establish a sovereign AI infrastructure for Vision 2030 (Saudi Press Agency, 2025). India's national AI mission allocates $1.25 billion for domestic GPU clusters, explicitly invoking its diaspora of IIT-trained engineers (Ministry of Electronics and Information Technology, 2024). China's DeepSeek, Qwen, and Baidu are regularly cited as evidence that Chinese AI does not require dependence on American models (Roberts, 2024).

The problem is definitional. "Sovereign AI" as operationalized across these initiatives means, at most, *we trained the model.* It is silent on who designed the chips the model trains on, who fabricates those chips, who controls the equipment that makes fabrication possible, and whose capital underwrote the enterprise. Sovereignty of training does not entail sovereignty of infrastructure, and the distinction is not merely philosophical — it determines whether the strategic autonomy being claimed is real or contingent.

This paper makes three contributions. First, it maps the structural chokepoints in the global AI supply chain using a relational database of ecosystem actors, tracing the dependency paths that national AI narratives obscure. Second, it applies financial analysis to current AI sector valuations to develop a timeline for a market correction and identifies which actors are structurally positioned to survive it. Third, it proposes an operational definition of AI sovereignty grounded in the technical realities of inference deployment, and argues that post-correction economics will align with this definition in ways that current policy does not anticipate.

The paper proceeds as follows. Section 2 describes the relational database methodology underpinning the structural analysis. Section 3 analyzes the four principal chokepoint layers: hardware, capital, talent, and distribution. Section 4 examines the AI sector's financial structure and develops a correction forecast. Section 5 analyzes the efficiency convergence phenomenon — the independent discovery of algorithmic efficiency by resource-constrained actors — and its implications for the forecast. Section 6 describes the post-correction landscape and argues for the economic dominance of local-first deployment. Section 7 proposes an operational framework for genuine AI sovereignty and identifies the actors currently enabling it. Section 8 addresses limitations and concludes.

---

## 2. Methodology

### 2.1 Relational Database Construction

The empirical foundation of this paper is a structured SQLite relational database (`sociotechnical.db`) constructed from public sources between January and June 2026. The database contains seven primary tables: `creators` (AI organizations, n=30), `people` (individuals associated with organizations, n=76), `model_releases` (notable model releases linked to creators), `funders` (capital sources, n=41), `funding_rounds` (investment events, n=40), `relationships` (directed edges between entities, n=80), and `observations` (analytical notes with source attributions, n=56).

Edge types include: `infrastructure_dependency`, `strategic_backer`, `spawned_talent`, `triggered`, `returned_talent`, `geopolitical_split`, `academic_origin`, and `ecosystem_node`. This taxonomy was developed inductively from the literature and refined through iterative database construction. The edge type `infrastructure_dependency` captures physical or technical dependency chains; `strategic_backer` captures equity or funding relationships where the backer holds strategic influence; `spawned_talent` captures organizational lineage through personnel movement.

Sources include corporate SEC filings and equivalents, Crunchbase funding data, academic publication records, news coverage from Reuters, Financial Times, and specialist outlets, and organizational announcements. All claims cited from this database are attributed to their primary public source in the References section.

### 2.2 Financial Analysis

The bubble forecast in Section 4 is developed from a combination of publicly reported financial figures (valuations at funding rounds, revenue estimates from investor disclosures and industry analysts) and capital expenditure commitments reported in hyperscaler quarterly earnings. Revenue figures are estimates drawn from analyst reporting and should be treated as approximate. The forecast timeline is probabilistic, not deterministic, and is presented as a structured scenario rather than a point prediction.

### 2.3 Scope and Limitations

The database covers the period through June 2026 and is necessarily incomplete — private capital structures, non-public talent movements, and internal organizational relationships are not fully represented. The paper makes no claim to comprehensiveness. The chokepoint analysis focuses on the layers most relevant to the sovereign AI claim; it does not address all dimensions of AI governance or national security policy. Limitations are addressed in Section 8.

---

## 3. The Chokepoint Layers

### 3.1 The Hardware Supply Chain

Every AI model of significance — whether trained for national strategic purposes or commercial deployment — runs on graphics processing units (GPUs) designed by NVIDIA Corporation. NVIDIA is a fabless semiconductor company: it designs chips but does not manufacture them. Manufacturing is performed by Taiwan Semiconductor Manufacturing Company (TSMC), which produces NVIDIA's H100, A100, and successor architectures at its facilities in Taiwan. TSMC's advanced manufacturing processes (5nm, 3nm, and below) require extreme ultraviolet (EUV) lithography machines — equipment manufactured exclusively by ASML Holding N.V., headquartered in Eindhoven, Netherlands.

ASML's monopoly on EUV lithography equipment is not a market outcome that can be remedied by investment on policy-relevant timescales. The machines cost approximately $200 million each, require years to produce, and depend on a global supply chain of approximately 5,000 suppliers across 40 countries (ASML, 2024). No second EUV supplier exists, and building one would require decades of coordinated investment.

The structural consequence is direct. The dependency chain from any AI model to physical manufacturing infrastructure terminates at ASML (see Figure 1). The `infrastructure_dependency` edges in `sociotechnical.db` document this chain for the OpenAI ecosystem explicitly: OpenAI → NVIDIA → TSMC → ASML, five hops from a ChatGPT query to a Dutch export license.

**Figure 1.** *Hardware dependency chain for AI training infrastructure.*

```
AI Model → GPU Runtime
GPU Runtime → NVIDIA Design
NVIDIA Design → TSMC Fabrication
TSMC Fabrication → ASML EUV Lithography
ASML EUV → [No upstream dependency: monopoly position]
```

The geopolitical significance of this chain became operationally visible in 2023, when the United States government, in coordination with the Netherlands and Japan, imposed export controls restricting ASML's sale of advanced EUV machines to China (Bureau of Industry and Security, 2023). This single policy action — targeting one machine type from one Dutch manufacturer — constitutes the most consequential constraint on Chinese AI capability development imposed to date.

Sovereign AI claims collapse against this analysis. France's Mistral trains on NVIDIA H100s (Mistral AI, 2023). Germany's Aleph Alpha operates on NVIDIA GPU clusters (Aleph Alpha, 2023). India's national AI mission is purchasing NVIDIA GPU infrastructure (MEITY, 2024). Saudi HUMAIN announced a direct NVIDIA partnership as a headline feature of its founding (Saudi Press Agency, 2025). China's DeepSeek trained DeepSeek-V3 and R1 on NVIDIA A100 GPUs accumulated prior to export control implementation (DeepSeek, 2024). Every sovereign AI initiative currently operates on hardware whose supply chain it does not control.

### 3.2 Capital Formation Patterns

Capital dependency operates at a different layer from hardware but with comparable strategic implications. Three patterns are identified in the `sociotechnical.db` `strategic_backer` edges.

**Foreign capital in domestic infrastructure.** The January 2025 Stargate announcement — $500 billion in US AI infrastructure, presented at the White House as a national strategic initiative — listed SoftBank (Tokyo), Saudi Public Investment Fund (Riyadh), UAE G42 (Abu Dhabi), and Oracle as primary capital sources (White House, 2025). The majority of capital underwriting the initiative framed as the cornerstone of US AI supremacy is of foreign origin. This is not anomalous; it reflects global capital allocation patterns. What is anomalous is the claim of national sovereignty over infrastructure financed this way.

**Oligopoly consolidation in the Chinese ecosystem.** Alibaba Group holds strategic equity positions in three distinct Chinese AI entities: Qwen (developed in-house at DAMO Academy), Moonshot AI (Series A lead investor, $300 million), and Zhipu AI (strategic investor). The `strategic_backer` edges in `sociotechnical.db` document all three. A single corporate entity thus controls a plurality of the Chinese open-weight AI ecosystem. The competitive landscape this produces is more accurately described as managed oligopoly than market competition.

**Evaluator capture.** Open Philanthropy, the effective-altruist grantmaking organization backed by Dustin Moskovitz, is the largest external funder of Anthropic, with approximately $580 million committed across multiple tranches (Open Philanthropy, 2023, 2024). Open Philanthropy also funds the Model Evaluation and Threat Research organization (METR), whose institutional mandate is to provide independent safety evaluations of frontier AI systems — including Anthropic's (Open Philanthropy, 2024b). The structural independence of the evaluator is undermined by shared funder identity with the evaluated. This does not demonstrate bad faith on the part of any party; it demonstrates that in a small, capital-intensive, ideologically coherent field, institutional independence is structurally difficult to maintain.

### 3.3 Talent Pipeline Dynamics

Three talent pipelines dominate the global AI ecosystem, and each cross-cuts national sovereignty narratives.

**The OpenAI diaspora.** Anthropic was founded in 2021 by Dario Amodei, Daniela Amodei, and seven co-founders, all of whom departed OpenAI (Anthropic, 2021). Safe Superintelligence Inc. was founded in 2023 by Ilya Sutskever (former OpenAI Chief Scientist), Daniel Gross, and Edan Ellison (SSI, 2023). The Machine Learning Institute traces similar lineage (TML, 2024). The `spawned_talent` edges in `sociotechnical.db` document these relationships. OpenAI functions, structurally, as the graduate institution of the AI era: researchers train there, develop research agendas and organizational commitments, and exit to found successor entities that compete while sharing substantial intellectual lineage.

**The IIT pipeline.** A significant proportion of senior leadership at major US technology companies holds undergraduate degrees from Indian Institutes of Technology: Sundar Pichai (IIT Kharagpur, Google CEO), Aravind Srinivas (IIT Madras, Perplexity CEO), and others. India's national AI mission explicitly targets the repatriation of this talent, framing diaspora engineers as a strategic resource (MEITY, 2024). The repatriation assumption requires overcoming salary differentials estimated at 10–20x between comparable positions in San Francisco and Bengaluru — a structural constraint that policy announcement does not resolve.

**Returned talent (China).** Yang Zhilin, founder of Moonshot AI, holds a PhD from Carnegie Mellon University and conducted research at Google Brain prior to founding his company in Hangzhou (Moonshot AI, 2023). The knowledge transfer pattern is bidirectional: US research institutions produce researchers who return to deploy that training in non-US contexts. National AI sovereignty claims that assume knowledge respects geopolitical boundaries are inconsistent with the actual movement patterns of AI researchers.

### 3.4 The Distribution Layer

Hugging Face, Inc. operates the dominant platform for distributing open-weight AI models. LLaMA (Meta AI, 2023), Mistral (Mistral AI, 2023), Qwen (Alibaba DAMO, 2023), and DeepSeek-R1 (DeepSeek, 2024) are all primarily distributed through Hugging Face's model hub. The platform functions as the neutral infrastructure through which open-weight AI capability reaches researchers, developers, and deploying institutions globally.

In 2023, Hugging Face completed a Series D funding round at a $4.5 billion valuation. Disclosed investors include Google, Amazon, NVIDIA, Salesforce, and Intel (Hugging Face, 2023). The four largest providers of proprietary, closed-source AI — the organizations most structurally threatened by open-weight model adoption — collectively hold equity in the platform that distributes their competitors' model weights.

This arrangement is not explicable as accidental. The `ecosystem_node` observations in `sociotechnical.db` document the structural logic: open-weight model distribution through an observable, investor-accessible platform serves the interests of incumbent closed-model providers more effectively than a fully adversarial distribution infrastructure would. The platform's operational neutrality is real; its structural neutrality is not.

---

## 4. Financial Structure and Correction Forecast

### 4.1 Current Valuations and Revenue

Table 1 summarizes publicly available financial data for the principal frontier AI laboratory entities.

**Table 1.** *AI laboratory financial data, 2024–2025.*

| Entity | Total Capital Raised | Peak Valuation | Estimated ARR |
|---|---|---|---|
| OpenAI | ~$40B | $300B | ~$4B |
| Anthropic | ~$13B | $61B | ~$3B |
| Safe Superintelligence Inc. | $4B | $32B | $0 |
| The Machine Learning Institute | $2B | Undisclosed | $0 |
| xAI | $12B | $50B | Limited |
| Perplexity AI | $0.6B | $9B | Limited |

*Sources: Crunchbase, Bloomberg, Wall Street Journal, company disclosures. ARR = annual recurring revenue. Figures are estimates.*

The hyperscaler capital expenditure commitment to AI infrastructure is approximately $255 billion annually as of 2025: Microsoft approximately $80 billion (Microsoft, 2025), Amazon approximately $100 billion (Amazon, 2025), Google approximately $75 billion (Alphabet, 2025). At a 5x revenue multiple, sustaining these CapEx commitments requires $51 billion per year in AI-attributable revenue. Industry-wide AI revenue estimates for 2025 range from $20 to $30 billion (Goldman Sachs, 2025; Sequoia Capital, 2024). The gap is structural, not cyclical.

### 4.2 Three Correction Triggers

**4.2.1 The Efficiency Cliff (Estimated: 2026–2027)**

DeepSeek released V3 in late 2024, trained for an estimated $5.6 million in compute costs, achieving benchmark performance comparable to GPT-4 (DeepSeek, 2024; Epoch AI, 2025). The subsequent R1 release demonstrated reasoning capability comparable to OpenAI's o1 using reinforcement learning techniques that reduced dependence on expensive supervised fine-tuning (DeepSeek, 2025). Within weeks of the V3 release, multiple providers implemented significant API price reductions (The Verge, 2025).

The trend line these results establish points toward sub-$1 million frontier training costs within 24–36 months. At that cost structure, API pricing built on premium training-cost amortization becomes untenable. A query currently priced at $30 per million tokens approaches $0.30 per million tokens in a $1 million training cost regime. Revenue projections supporting current valuations require API margin maintenance that training cost convergence makes structurally impossible.

**4.2.2 Hyperscaler CapEx Reckoning (Estimated: 2026–2027)**

Microsoft, Amazon, and Alphabet report capital expenditure quarterly. Three to four consecutive quarters of widening divergence between AI CapEx and AI-attributable revenue will trigger analyst repricing of AI-related assets. The hyperscalers are profitable enterprises and will not face existential risk; however, their AI investment theses will be discounted, and the downstream effect on laboratory valuations that depend on cloud partnership revenue will be material.

**4.2.3 Recessionary Sensitivity (Wildcard)**

AI software remains a discretionary enterprise expenditure for most chief financial officers. A macroeconomic contraction of sufficient severity would freeze enterprise procurement. Laboratory entities burning $3–5 billion annually in operating expenditure cannot sustain a six-month procurement freeze at current cash positions. The recession trigger is less predictable than the efficiency or CapEx triggers but would act as an accelerant to either.

### 4.3 Forecast Timeline

- **Now–mid-2026:** Peak formation. Final large raises. Announced infrastructure projects still flowing.
- **Late 2026:** Initial fractures. Mid-tier laboratories fail to close follow-on rounds at 2024 valuations.
- **2026–2027:** Efficiency trigger activation. Cascading API price reductions. Revenue projections revised downward.
- **2027:** CapEx reckoning visible in quarterly earnings. Historical base case for NVIDIA suggests 40–65% drawdown (cf. 65% drawdown in 2022 correction; NVIDIA Corporation, 2022).
- **2027–2028:** Sector-wide consolidation. Estimated 40–60% valuation haircut. Acquisition of mid-tier laboratories by profitable incumbents.

### 4.4 Structural Survivors and Casualties

*Likely to survive:* NVIDIA, TSMC, and ASML (physical chokepoint positions; no valuation problem). Mistral AI (lean cost structure, open-weight positioning, no VC return obligation). DeepSeek / High-Flyer (internal research division; no external investor base to disappoint). Hugging Face (low cost structure; high strategic value to investors regardless of market conditions). Anthropic (actual enterprise revenue; constitutional backing from Google). Cohere (enterprise revenue independent of consumer hype cycle).

*Structurally at risk:* Safe Superintelligence Inc. ($32 billion valuation, $0 revenue, no product timeline visible to external observers; cannot sustain follow-on raise in cold market). Scale AI (automating its primary revenue source — human data labeling — via the same AI capabilities its business supports; transition to evaluation and enterprise deployment must complete before original business becomes unviable). Several Chinese consumer-facing AI applications (raised on GenAI multiples; lack efficiency-research differentiation that protects DeepSeek).

---

## 5. The Efficiency Convergence

A pattern of independent algorithmic discovery under resource constraint is visible across geographically and organizationally distinct AI laboratories. This pattern has significant implications for the correction forecast and for the post-correction landscape.

### 5.1 Mistral: European Constraint

Mistral AI was founded in Paris in 2023 by Arthur Mensch, Guillaume Lample, and Timothée Lacroix, all three departing from DeepMind or Meta FAIR (Mistral AI, 2023). Operating without access to closed American APIs, without significant corporate compute backing, and in an environment emphasizing data-residency compliance, the team trained Mistral 7B on available hardware with disciplined data curation. The 7-billion-parameter model matched the performance of LLaMA 2 13B on standard benchmarks — achieving competitive performance at approximately half the parameter count (Jiang et al., 2023).

### 5.2 DeepSeek: Export Control Constraint

DeepSeek is the AI research division of High-Flyer Capital Management, a quantitative hedge fund based in Hangzhou, Zhejiang Province. High-Flyer accumulated approximately 10,000 NVIDIA A100 GPUs prior to the implementation of US export controls in October 2022; subsequent controls prevented acquisition of A100 successors (H100, H200) (Bureau of Industry and Security, 2022). DeepSeek's research program therefore developed under a fixed hardware ceiling, without the option of scaling compute to compensate for algorithmic limitations.

The result was DeepSeek-V3 (2024), trained for an estimated $5.6 million in compute costs, achieving GPT-4-level benchmark performance through a combination of mixture-of-experts architecture, multi-head latent attention, and novel training stability techniques (DeepSeek, 2024). The subsequent R1 model matched OpenAI's o1 reasoning benchmark through reinforcement learning approaches that substantially reduced the need for expensive supervised fine-tuning (DeepSeek, 2025).

### 5.3 The Constraint-Insight Mechanism

The pattern is not coincidental. Both laboratories discovered algorithmic efficiency *because* they could not purchase compute. The US frontier laboratories — operating with effectively unlimited GPU access — had no economic incentive to pursue the algorithmic optimizations that Mistral and DeepSeek were compelled to find. The efficiency ratchet these discoveries initiated is a one-way mechanism: models become smaller, faster, and more capable per parameter as researchers optimize. This direction does not reverse.

Notably, the US export controls intended to prevent Chinese AI capability development produced the efficiency breakthrough that is now eroding the premium API margin model on which US AI laboratory valuations depend. This constitutes a structurally significant unintended consequence that merits attention in policy analysis.

---

## 6. The Post-Correction Landscape: Local-First Economics

When training efficiency reaches the point at which API costs approach zero, the economic argument for remote inference dissolves. The deployment decision for any institution shifts from a capability-per-cost calculation to a sovereignty-per-convenience tradeoff.

Consider the institutional actors with genuine reasons to control their AI deployment: healthcare systems (HIPAA compliance, data residency, patient confidentiality); legal institutions (attorney-client privilege, litigation sensitivity, jurisdictional data requirements); government agencies (classification constraints, operational security, data sovereignty law); financial regulators (systemic risk data, insider information rules, jurisdictional compliance); educational institutions (FERPA compliance, student data protection, vendor concentration risk).

For each of these actors, the case for local deployment rests on four requirements: (1) queries do not leave the institution's infrastructure; (2) operations are independent of vendor relationships; (3) budget exposure is bounded and predictable; (4) data remains within the relevant jurisdictional boundary. Currently, these requirements impose a capability penalty — local models underperform frontier API models on a significant proportion of tasks. The efficiency convergence is closing this gap at a rate that will render it acceptable for the majority of institutional use cases within the correction window.

The post-correction scenario in which training costs have fallen to $1 million and API costs have cascaded to near-zero is also the scenario in which a locally-run open-weight model operates within acceptable range of a frontier proprietary model for 80–90% of institutional use cases. At that point, the residual case for the API is convenience, and convenience is insufficient justification for surrendering data sovereignty, operational independence, or budget predictability.

---

## 7. An Operational Framework for AI Sovereignty

The preceding analysis supports a definition of AI sovereignty that is functional rather than rhetorical: sovereignty is not achieved by training a model. It is achieved by deploying AI capability in a configuration where no necessary dependency can be revoked.

Four criteria are proposed:

**7.1 Weights that are owned.** Open-weight models whose parameters are downloadable and persistently storable — not API-access models whose availability is contingent on a vendor relationship. License terms must permit indefinite use without renewal.

**7.2 Hardware that is owned.** Physical compute infrastructure, not cloud instances rented from third-party providers. Cloud instances carry termination risk, pricing revision risk, and jurisdictional risk. Owned hardware depreciates on a known schedule.

**7.3 Inference software that is controlled.** The runtime that loads weights and processes queries must be software whose execution the deploying institution controls. Principal open-source options include llama.cpp (Gerganov, 2023) and Ollama (Ollama, 2024), both permissively licensed and hardware-agnostic across Apple Silicon, NVIDIA consumer GPUs, AMD RDNA, and ARM.

**7.4 No revocable dependency.** No license that expires, no API key that can be suspended, no pricing structure subject to unilateral revision, no geographic restriction that can be applied retroactively.

Table 2 maps current entities against these criteria.

**Table 2.** *Sovereignty criteria assessment for selected AI actors.*

| Actor | Open Weights | Owned Compute | Controlled Runtime | No Revocable Dependency |
|---|:---:|:---:|:---:|:---:|
| Mistral 7B / 8x7B | ✓ | User-dependent | ✓ (llama.cpp) | ✓ (Apache 2.0) |
| LLaMA 3 (8B, 70B) | ✓ | User-dependent | ✓ (llama.cpp) | Partial (Meta license) |
| Qwen 2.5 (7B) | ✓ | User-dependent | ✓ (llama.cpp) | ✓ (Apache 2.0) |
| DeepSeek-R1-Distill | ✓ | User-dependent | ✓ (llama.cpp) | ✓ (MIT) |
| GPT-4o (OpenAI API) | ✗ | ✗ | ✗ | ✗ |
| Claude 3.x (Anthropic API) | ✗ | ✗ | ✗ | ✗ |
| National GPU clusters (e.g., NDIF, IndiaAI) | Varies | ✓ | Varies | Partial (hardware chain) |

The hardware row in the national cluster case warrants elaboration: owned GPU infrastructure satisfies the compute ownership criterion but does not escape the hardware dependency chain analyzed in Section 3.1. NVIDIA GPUs are owned, but the supply chain that produces replacement units — and the firmware and driver stack that runs them — remains under third-party control.

The long-run hardware sovereignty path is RISC-V: an open instruction set architecture not owned by any company, permitting chip design without license obligation to ARM Holdings or Intel (RISC-V International, 2024). Current RISC-V AI acceleration hardware (Ventana Veyron, SpacemiT X60) lags NVIDIA's performance envelope significantly. The horizon for RISC-V to be relevant to sovereignty-conscious deployment is estimated at 5–15 years depending on investment trajectories — beyond the scope of near-term policy but relevant to infrastructure planning.

---

## 8. Discussion and Limitations

### 8.1 The Policy Implication

The analysis suggests a reorientation of sovereign AI policy away from model training and toward the hardware-software stack required for genuinely independent deployment. A national AI policy that results in a domestically trained model running on rented NVIDIA GPUs via hyperscaler cloud, distributed through Hugging Face, has achieved rhetorical sovereignty without operational sovereignty. The policy question is not *can we train a model* but *can we run it without external permission*.

This reorientation has implications for procurement decisions, procurement security requirements, and the appropriate role of efficiency-focused open-weight research in national AI strategies. The actors best positioned to enable genuine sovereignty — Mistral, DeepSeek, the llama.cpp ecosystem — are in several cases not the actors receiving the most prominent policy attention.

### 8.2 Limitations

Several limitations should be noted. The `sociotechnical.db` database is constructed from public sources; private equity structures, undisclosed funding relationships, and internal organizational dynamics are not fully captured. The financial forecast is probabilistic and rests on estimated revenue figures. The correction timeline is a structured scenario, not a point prediction — the triggers identified are real but their timing is uncertain. The sovereignty framework proposed in Section 7 is normative; different institutional actors may weight the four criteria differently. The hardware sovereignty analysis focuses on the training and inference compute layer and does not address data infrastructure, networking, or operating system dependencies in full. Future work should extend the relational database to include regulatory actors (EU AI Act institutions, US NIST), policy interventions, and the emerging RISC-V AI hardware ecosystem.

---

## 9. Conclusion

The concept of "sovereign AI" as currently deployed in national policy discourse is structurally incomplete. Every major sovereign AI initiative analyzed in this paper is captured at one or more chokepoints — in the hardware supply chain, in the capital formation layer, in the talent pipeline, or in the distribution infrastructure — that the claiming nation or institution does not control and cannot replace on policy-relevant timescales. The five-hop dependency chain from a ChatGPT query to an ASML export license is documented; its structure applies equally to every other AI system of significance.

The AI sector's financial structure contains a forecast correction, driven by training efficiency convergence initiated by resource-constrained actors (Mistral, DeepSeek) as an unintended consequence of the export control regime. That correction will produce a landscape in which local-first, open-weight AI deployment is economically competitive with API-dependent alternatives for the large majority of institutional use cases.

The framework proposed here — open weights, owned hardware, controlled runtime, no revocable dependency — provides an operational definition of AI sovereignty against which existing initiatives can be evaluated. By this definition, the actors currently doing the most to enable genuine AI sovereignty are not national governments. They are the laboratories and communities producing efficient, openly licensed, locally deployable models, and the developers building the inference infrastructure to run them.

---

## References

Aleph Alpha. (2023). *Aleph Alpha raises €500 million in Series B funding*. Aleph Alpha Press Release.

Alphabet Inc. (2025). *Fourth quarter 2024 results* [Earnings release]. Alphabet Investor Relations.

Amazon.com, Inc. (2025). *Fourth quarter 2024 results* [Earnings release]. Amazon Investor Relations.

Anthropic. (2021). *Anthropic raises $124 million to build AI systems that are safe, beneficial, and understandable* [Press release].

ASML Holding N.V. (2024). *Annual report 2023*. ASML.

Bureau of Industry and Security, U.S. Department of Commerce. (2022). *Implementation of additional export controls: Certain advanced computing and semiconductor manufacturing items; Supercomputer and semiconductor end use* [Final rule]. 87 FR 62186.

Bureau of Industry and Security, U.S. Department of Commerce. (2023). *Expansion of export controls on advanced computing semiconductors, semiconductor manufacturing equipment, and supercomputing items to China* [Interim final rule].

DeepSeek. (2024). *DeepSeek-V3 technical report*. arXiv:2412.19437.

DeepSeek. (2025). *DeepSeek-R1: Incentivizing reasoning capability in LLMs via reinforcement learning*. arXiv:2501.12948.

Epoch AI. (2025). *Training compute of frontier AI models, 2024–2025* [Dataset]. Epoch AI Research.

Gerganov, G. (2023). *llama.cpp* [Software]. GitHub. https://github.com/ggerganov/llama.cpp

Goldman Sachs. (2025). *AI investment: Framing the spend* [Research report]. Goldman Sachs Global Investment Research.

Hugging Face. (2023). *Hugging Face raises $235 million Series D at $4.5 billion valuation* [Press release].

Jiang, A. Q., Sablayrolles, A., Mensch, A., Bamford, C., Chaplot, D. S., de las Casas, D., Bressand, F., Lengyel, G., Lample, G., Saulnier, L., Lavaud, L. R., Lachaux, M.-A., Stock, P., Le Scao, T., Lavril, T., Wang, T., Lacroix, T., & El Sayed, W. (2023). *Mistral 7B*. arXiv:2310.06825.

Meta AI. (2023). *Introducing LLaMA: A foundational, 65-billion-parameter language model* [Blog post]. Meta AI Research.

Microsoft Corporation. (2025). *Second quarter fiscal year 2025 results* [Earnings release]. Microsoft Investor Relations.

Ministry of Electronics and Information Technology, Government of India. (2024). *IndiaAI mission: Cabinet approval and programme overview* [Press release].

Mistral AI. (2023). *Mistral 7B* [Model release]. Mistral AI.

Moonshot AI. (2023). *Moonshot AI company overview* [Corporate communication].

NVIDIA Corporation. (2022). *Annual report 2022: Fiscal year financial summary*. NVIDIA Investor Relations.

Ollama. (2024). *Ollama: Get up and running with large language models* [Software]. GitHub. https://github.com/ollama/ollama

Open Philanthropy. (2023). *Anthropic (general support, second grant)* [Grant announcement].

Open Philanthropy. (2024a). *Anthropic (general support, third grant)* [Grant announcement].

Open Philanthropy. (2024b). *Model Evaluation and Threat Research (METR)* [Grant announcement].

RISC-V International. (2024). *RISC-V technical specifications and governance* [Technical overview]. RISC-V International.

Roberts, H. (2024). China's AI ecosystem: DeepSeek, Qwen, and the efficiency turn. *MIT Technology Review*.

Saudi Press Agency. (2025). *HUMAIN: Kingdom of Saudi Arabia launches AI national initiative* [Press release].

Sequoia Capital. (2024). *Generative AI: The year the rule of 40 meets AI* [Research note]. Sequoia Capital.

SSI. (2023). *Safe Superintelligence Inc.* [Company announcement].

Stokel-Walker, C. (2023). Germany's Aleph Alpha wants to keep European data in Europe. *Wired*.

The Machine Learning Institute. (2024). *TML founding announcement* [Press release].

The Verge. (2025). OpenAI, Anthropic, Google slash API prices following DeepSeek release. *The Verge*.

Vinocur, J., & Cerulus, L. (2023). France bets on Mistral to keep AI in European hands. *Politico*.

White House, Office of the Press Secretary. (2025). *Stargate: The AI infrastructure initiative for America* [Fact sheet].
