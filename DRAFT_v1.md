@markdownai v1.0

# The Illusion of Sovereign AI

*A structural argument about chokepoints, capital, and what "sovereignty" actually requires*

---

Every government has a sovereign AI story right now.

France built Mistral. "European AI that doesn't bow to Washington." Germany backed Aleph Alpha. "GDPR-safe, on-premises, built for regulated industry." Saudi Arabia announced HUMAIN with $100 billion in committed capital and a direct partnership with NVIDIA. India launched its national AI mission with 10,000 GPUs and a bet on the IIT diaspora. China has DeepSeek, Qwen, and Baidu. "We don't need American models." The United States has OpenAI, Anthropic, SSI, TML, and Stargate — half a trillion dollars in announced infrastructure. "We will not be caught."

They are all, to varying degrees, describing the wrong thing.

"Sovereign AI" as currently used means *we trained the model.* It says almost nothing about who designed the chips the model runs on, who fabricates those chips, who built the machines that make fabrication possible, or whose capital funded the whole enterprise. The phrase conflates having a model with controlling the means of producing it. These are not the same thing. Not even close.

This piece traces the actual dependency chains — not the press releases. It follows the money, the hardware, the talent, and the distribution layer that sits above all of it. Then it makes a prediction: the AI bubble will correct, probably between 2027 and 2028, and when it does, it will leave behind a landscape where the ideology and the economics of local-first AI finally align. For the first time in this era, the capability you need for real sovereignty fits on a device that costs less than a month of API access.

That convergence is not an accident. It is the predictable result of structural forces that have been building since the first export control on advanced chips.

---

## The Map: Chokepoints the Sovereigns Don't Control

Let's start with the physical layer, because nothing else matters if the hardware doesn't run.

Every AI model runs on GPUs. The dominant GPU manufacturer for AI training is NVIDIA — a fabless chip designer, meaning they design the hardware but don't manufacture it. The actual fabrication is done by TSMC, Taiwan Semiconductor Manufacturing Company, which produces the H100s, A100s, and every other NVIDIA chip that runs the AI industry. TSMC requires extreme ultraviolet lithography machines to manufacture chips at the cutting edge — the kind of machines that make 5-nanometer and 3-nanometer process nodes possible. Those machines are made by ASML, a Dutch company headquartered in Eindhoven. ASML is a de facto global monopoly. There is no second supplier. The most advanced semiconductor production on earth depends on one Dutch company's machines.

That dependency chain — model → GPU → NVIDIA design → TSMC fabrication → ASML equipment — means that every "sovereign AI" story on the planet terminates at a single point in the Netherlands. Not at a government. Not at a national lab. At ASML.

The strategic implications of this became visible in 2023, when the United States pressured the Netherlands to stop selling advanced EUV machines to China. That single export control decision — one machine type, one country of origin — has done more to constrain Chinese AI capability than any amount of model-level regulation. China cannot build cutting-edge chips at scale without ASML. Without cutting-edge chips, training frontier models requires extraordinary algorithmic ingenuity. More on what happened when that constraint kicked in later.

Now check the sovereign AI claims against this map:

France's Mistral trains on NVIDIA H100s. Germany's Aleph Alpha runs on NVIDIA GPUs. India's national AI mission is purchasing GPU clusters — NVIDIA ones. Saudi HUMAIN announced a direct NVIDIA partnership as a headline feature of the deal. China's DeepSeek trained its landmark V3 and R1 models on A100s — the older generation NVIDIA chips accumulated before the export window closed in 2022.

Every flag planted on "sovereign AI" terrain rests on a foundation controlled by a company in Santa Clara and a factory in Taiwan.

### The Capital Layer

Hardware is the most legible chokepoint. The capital layer is subtler but equally structural.

Consider the January 2025 Stargate announcement — $500 billion in US AI infrastructure, presented at the White House as a national strategic achievement. The actual capital sources: SoftBank (Tokyo), Saudi PIF (Riyadh), UAE G42 (Abu Dhabi), and Oracle. The majority of the capital committing to "American AI supremacy" is foreign. SoftBank's Masayoshi Son stood next to the President at the announcement. This is not criticism — capital is capital, and the infrastructure will be built regardless of flag. The point is that the framing of national sovereignty obscures an investment structure that is thoroughly multinational.

Look east and the pattern repeats with different actors. Alibaba holds strategic positions in three Chinese AI entities simultaneously: Qwen (developed in-house), Moonshot AI (Series A lead, $300M), and Zhipu AI. From one corporate entity, Alibaba has positioned itself as a plurality shareholder across the Chinese open-weight AI ecosystem. That is not a competitive landscape. That is managed oligopoly dressed as market competition.

The most structurally peculiar example is domestic to the United States. Open Philanthropy — the effective-altruist foundation with Dustin Moskovitz's Meta billions behind it — is the largest outside funder of Anthropic, having committed approximately $580 million across multiple rounds. Open Philanthropy also funds METR, the Model Evaluation and Threat Research organization whose stated purpose is to provide independent safety evaluations of frontier AI models — including Anthropic's. The evaluator's independence is structurally compromised by the same funder who backs the company being evaluated. This is not evidence of bad intent. It is evidence that in a small, capital-intensive, ideologically cohesive field, the appearance of independent oversight can be manufactured without the substance.

The venture capital decoupling layer is visible in a different way. Sequoia Capital split its China operations from its US and global operations in 2023, under US government pressure, creating HongShan as an independent entity. The split is real at the fund level. But the LP base, the portfolio relationships, and the talent networks don't evaporate because the legal entity changed. Geopolitical pressure can restructure capital vehicles. It cannot restructure the underlying relationships those vehicles reflect.

### The Talent Pipeline

Three talent pipelines feed almost every significant AI lab.

The first is the OpenAI diaspora. Anthropic was founded in 2021 by Dario Amodei, Daniela Amodei, and seven other researchers, nearly all of whom left OpenAI. Safe Superintelligence Inc. was founded in 2023 by Ilya Sutskever — OpenAI's former chief scientist — along with Daniel Gross and Edan Ellison. The Machine Learning Institute traces similar lineage. OpenAI has become the university of the AI era: researchers train there, develop strong opinions about the field's direction, and exit to found competing entities. The entities compete on products and positioning while sharing substantial intellectual and social DNA.

The second pipeline runs through IIT — the Indian Institutes of Technology — into American tech, and now back toward India via national AI policy. Sundar Pichai (Google CEO) is IIT Kharagpur. Satya Nadella (Microsoft CEO) is not IIT but attended Manipal and went to University of Wisconsin for graduate work — the broader pattern holds. Aravind Srinivas, who founded Perplexity, is IIT Madras. The talent that built American technology empires is now the resource India's national AI mission wants to repatriate. The pipeline flows toward higher compensation for reasons that don't change because a government makes an announcement: a 10-20x salary differential between Bangalore and San Francisco is not a policy problem. It is arithmetic.

The third pipeline runs in partial reverse. Yang Zhilin, who founded Moonshot AI (Kimi) in Hangzhou, holds a PhD from Carnegie Mellon and worked at Google Brain before returning to China. This is the same arc in the opposite direction: train talent in one ecosystem's institutions, deploy it in another. The knowledge doesn't stay where the passport says it should.

None of this is surprising. Talent follows institutions, institutions follow capital, and capital follows perceived advantage. What it means for "sovereign AI" is that the human layer of every national AI initiative is entangled with training pipelines, research cultures, and professional networks that cross the geopolitical lines the initiatives are meant to preserve.

### The Distribution Layer

There is one more chokepoint, and it is the quietest.

Hugging Face is the dominant platform for distributing open-weight AI models. LLaMA (Meta), Mistral, Qwen (Alibaba), and DeepSeek-R1 are all primarily distributed through Hugging Face's model hub. If you want to download an open-weight model, you almost certainly go through Hugging Face.

In 2023, Hugging Face completed a Series D funding round at a $4.5 billion valuation. Among the investors: Google, Amazon, NVIDIA, Salesforce, and Intel.

Read that again. The four largest providers of closed, proprietary AI — the companies most threatened by open-weight models — collectively hold equity in the platform that distributes those models to the world. They own a stake in the neutral infrastructure that their competitors and critics use to reach users.

This is not neutral. This is managed neutrality. The platform appears open because the investors benefit from it appearing open. The appearance of openness serves their interests more than actual closedness would — closed-source models distributed through a platform they partially control are less useful to competitors than open models they can observe, analyze, and build moats against. Open is fine when you can see what's open.

A genuine open-weight distribution strategy — one that doesn't route through this particular infrastructure — would mirror the weights locally and use content-addressed storage with no single point of failure. Some projects do this. Most don't, because Hugging Face is convenient and the threat model isn't visible in the day-to-day download flow.

---

## The Money: Reading the Bubble

The chokepoints tell you where the structural dependencies are. The financial layer tells you when the reckoning comes.

Here is the table that matters:

| Entity | Total Raised | Latest Valuation | Revenue (est.) |
|---|---|---|---|
| OpenAI | ~$40B | $300B | ~$4B ARR |
| Anthropic | ~$13B | $61B | ~$3B ARR |
| SSI | $4B | $32B | $0 |
| TML | $2B | undisclosed | $0 |
| xAI | $12B | $50B | limited |
| Perplexity | $0.6B | $9B | limited |

The hyperscalers are spending approximately $255 billion per year on AI-related capital expenditure: Microsoft at roughly $80 billion, Amazon at $100 billion, Google at $75 billion. To justify that CapEx at a standard 5x revenue multiple, the industry needs to generate $51 billion per year in AI-specific revenue. Current estimates put AI revenue across all players — labs plus hyperscalers combined — somewhere between $20 and $30 billion and growing, but not at the pace the CapEx implies. The gap is not trivial. It is the gap that has to close for the valuation story to be true.

There are three plausible triggers for when it doesn't close fast enough.

**The efficiency cliff.** In late 2024, DeepSeek released V3, trained for approximately $6 million in compute costs, that matched the performance of GPT-4. Then R1, which matched OpenAI's o1 reasoning model. Then other labs immediately cut API prices — API pricing wars cascaded within weeks of the release. The trend line that these results point toward is sub-$1 million frontier training costs within two to three years. When training a competitive model costs $1 million instead of $100 million, the economics of the entire API-based revenue model collapse. A query that costs $30 per million tokens today approaches $0.30 in that world. Revenue projections built on premium API margins — the same projections that justify $300 billion valuations — fail.

The irony here is almost perfect. US export controls blocked China's access to H100s. That constraint forced DeepSeek's parent company, the quantitative hedge fund High-Flyer, to work with the A100s they had accumulated before the window closed. The constraint produced algorithmic optimization that brute-force compute had no incentive to pursue. The efficiency breakthrough that is now destabilizing the US AI business model was produced by the policy meant to prevent China from threatening US AI dominance. Classic unintended consequence.

**The CapEx disappointment.** The hyperscalers — Microsoft, Amazon, Google — are publicly traded companies that report quarterly. They are currently booking AI CapEx at rates that require commensurate AI-attributed revenue to appear. Three or four consecutive earnings cycles where AI CapEx grows faster than AI revenue will trigger analyst repricing. The hyperscalers don't collapse — they are profitable businesses with diverse revenue — but their AI bets get discounted. Every lab that depends on cloud partnership revenue or hyperscaler investment loses negotiating leverage. The downstream effect on smaller labs is significant.

**The recession wildcard.** AI is still a software budget line to most CFOs. Enterprise procurement freezes in recessions. Labs burning $3-5 billion per year cannot survive a six-month freeze in enterprise deal flow. The underlying AI capabilities don't go away, but the companies built around them at current valuations can.

The timeline these three triggers imply:

Through mid-2026: Peak. Last big raises. Stargate announcements still flowing. The hype hasn't met the wall yet.

Late 2026: First cracks. Mid-tier labs fail to raise follow-on rounds at 2024 valuations. Some consolidate. A few fold quietly.

2026-2027: The efficiency trigger fires. A new DeepSeek moment. API prices drop faster than revenue grows. The valuation math stops working publicly.

2027: CapEx reckoning in earnings. NVIDIA, historically, gave back 65% of its value in the 2022 correction after the previous hype cycle. A 40-60% correction from current levels is the historical base case, not an extreme scenario.

2027-2028: Sector-wide consolidation. 40-60% valuation haircut. Some entities absorb others. Several labs that have been running on anticipated future raises simply stop.

**Who survives the correction:**

NVIDIA, TSMC, and ASML don't survive — they are the infrastructure substrate. They are the physical chokepoints. They don't have a valuation problem; they have a monopoly position on necessary hardware. Mistral survives because they're lean, open-weight-hedged, and don't have VC returns to justify to anyone. DeepSeek survives because High-Flyer doesn't have outside investors to disappoint — it's a hedge fund's research division. Hugging Face survives because its cost structure is low and its strategic value to its investors is high even in a downturn. Anthropic probably survives because it has actual revenue and enterprise relationships. Cohere probably survives for the same reason — unglamorous enterprise revenue that doesn't depend on the hype cycle.

**Who doesn't:**

SSI is the most straightforward case. $32 billion valuation, $4 billion raised, $0 in revenue. In a hot market, you can raise another round at a flat or up valuation while the model is still being built. In a cold market, with no revenue and no product timeline, the follow-on doesn't come. The founders are credible and the mission is genuine. Neither matters when the capital dries up.

Scale AI faces a specific version of this problem: it is automating its own core business. The company's primary revenue source is human data labeling for AI training. The better AI gets at generating and evaluating training data, the less anyone needs Scale's core service. The business is hedging toward model evaluations and enterprise AI deployment, but the transition has to complete before the original revenue stream becomes unviable.

Several Chinese consumer-facing labs — the ones that raised on GenAI app multiples without the efficiency-research differentiation that makes DeepSeek interesting — will not survive a market that gets cold toward AI pure-plays.

---

## The Efficiency Convergence: What Constraint Produces

Two labs. Different continents. Different constraints. Same conclusion.

Mistral was founded in Paris in 2023 by Arthur Mensch, Guillaume Lample, and Timothée Lacroix — three researchers from DeepMind and Meta's FAIR. The European sovereignty framing was central from the beginning: no closed American APIs, no massive corporate backing, no access to the proprietary training infrastructure that OpenAI and Google had built. They trained Mistral 7B on commodity hardware with careful data curation. It matched LLaMA 2 13B at half the parameter count. They released the weights. The message was structural, not just technical: you can match the big labs if you're disciplined about efficiency.

DeepSeek is the AI research division of High-Flyer Capital Management, a quantitative hedge fund based in Hangzhou. High-Flyer accumulated roughly 10,000 A100 GPUs before US export controls closed the window on advanced chip sales to China in late 2022. When the H100 era arrived — offering roughly 3x the training throughput of A100s — DeepSeek couldn't buy in. They had to optimize.

The result, roughly two years later, was DeepSeek-V3: trained for approximately $6 million in reported compute costs, matching GPT-4 on standard benchmarks. Then DeepSeek-R1, using a novel reinforcement-learning-based reasoning approach, matching o1. The training efficiency came from a combination of mixture-of-experts architecture (running only a subset of parameters on any given token, reducing compute per step), more sophisticated data curation pipelines, and training stability techniques that reduced wasted runs.

The constraint produced the insight. This is not coincidence or luck.

The US frontier labs — OpenAI, Google, Anthropic — had the option of throwing compute at problems. More H100s, more runs, more experiments. That option is not always available to the researchers who actually find algorithmic efficiency. You look hard at a problem when you can't simply buy your way around it. Mistral looked hard because they had no corporate parent. DeepSeek looked hard because the hardware they needed was embargoed.

The efficiency trend is a one-way ratchet. Models get smaller, faster, and more capable per parameter. The direction does not reverse. The 7-billion-parameter model of 2024 substantially outperforms the 7-billion-parameter model of 2022. The 7-billion-parameter model of 2026 will outperform today's. Capability is decoupling from scale faster than anyone projected two years ago.

This has a specific implication for hardware. As models get more capable per parameter, the hardware required to run them at a given quality threshold shrinks. A model that ran adequately on a $10,000 server in 2023 runs better on a MacBook in 2025. A model that required a data center in 2023 runs on consumer hardware in 2025. The direction of travel is toward the device in your pocket.

---

## The Post-Bubble Landscape: When the Economics Align

When the efficiency cliff triggers the pricing collapse — when API costs drop toward near-zero — the cost argument for remote AI disappears.

Consider the decision a hospital makes about where to run its AI. Today, the calculation is: API access costs X per month, running locally requires hardware investment Y amortized over Z years, and the local model performs at Q% of the API model. For most organizations, Q is too low and X is manageable. The API wins on capability per dollar.

After the efficiency cliff: X approaches near-zero, but so does the gap between local capability and remote capability. The local model, running on hardware you paid for once, performs at 90-95% of the remote model for 80-90% of use cases. The only remaining argument for the API is convenience.

Convenience is not sovereignty.

Every institution that has a genuine reason to control its own AI deployment — and there are many — will have no financial reason not to go local. Consider the list:

*Data privacy*: queries don't leave the building, which means they don't train someone else's model, don't appear in server logs that could be subpoenaed, and don't create liability under GDPR, HIPAA, or whatever the next compliance framework is.

*Operational independence*: a local model works without internet connectivity, without a vendor relationship that can be terminated, and without an API key that can be suspended.

*Budget certainty*: no surprise pricing changes. No "we're adjusting our token pricing" email. Hardware costs are known and amortize over time.

*Jurisdictional compliance*: data doesn't leave the building, the country, or the regulatory zone.

These are not ideological preferences. They are operational requirements for a large class of serious institutions — hospitals, law firms, government agencies, financial regulators, schools. The only reason these institutions have been slow to adopt local deployment is that the capability gap was too large. That gap is closing.

The post-bubble landscape, then, is one where the AI capabilities that matter are commoditized, the infrastructure to run them locally costs less than a cloud subscription, and the entities that survive are the ones positioned to serve users who value control over convenience. That positioning — open weights, efficient models, local-first inference — is exactly the cluster that the structural sovereignty argument identifies as necessary.

---

## What Sovereignty Actually Requires

Not a national model. Not a national compute cluster. The house-on-a-floodplain problem: you can hold the title to a house and still not control the conditions that determine whether it stands.

Real sovereignty in AI has four requirements:

**1. Weights you can download and keep.** Open-weight models — not API-only access. A model you can only access through an API is not yours. The vendor can reprice it, restrict it, deprecate it, or remove it at will. You have licensed access to capability, not the capability itself. The difference matters when the license changes.

**2. Hardware you own.** Not cloud instances you rent. Cloud instances are someone else's hardware that you access via a relationship that can be terminated. Owned hardware is a fixed cost with a depreciation schedule. It does not come with a monthly bill that changes without notice.

**3. Inference software you run.** The model doesn't run itself. The inference runtime — the software that loads the model weights and processes queries — needs to be something you control. The critical open-source runtimes here are llama.cpp (the canonical C++ implementation, runs on nearly any hardware including mobile and Raspberry Pi) and Ollama (the developer-friendly wrapper built on llama.cpp). Both are MIT-licensed. Neither has a vendor that can remove your access.

**4. No dependency that can be revoked.** No license that expires. No API key that gets suspended. No vendor that can raise prices or shut down. The dependency chain that terminates at ASML is fine for ASML — they own the chokepoint. It is not sovereignty for everyone downstream.

The stack that meets all four requirements exists today, and it runs better than most people realize:

*Models*: Mistral 7B, LLaMA 3 8B, Qwen 2.5 7B, DeepSeek-R1-Distill (the distilled reasoning model, which runs on consumer hardware and produces results that would have required GPT-4 class access two years ago).

*Inference*: llama.cpp runs on Apple Silicon with surprisingly good performance — the M-series chips have unified memory that makes running large models in quantized form genuinely practical. An M3 Pro MacBook runs a 13B parameter model at speeds useful for real work.

*Hardware*: Apple M-series laptops and Mac minis are the most accessible local AI hardware for most users. NVIDIA consumer GPUs — the 3090 and 4090 — are the high-end option for users who want maximum speed. AMD RDNA is increasingly viable as ROCm support matures.

*Distribution*: Hugging Face for initial downloads, but with a critical caveat — you should mirror locally. Store the weights somewhere you control. Don't assume the download will always be available.

The gap between this stack and frontier API performance is closing every six months. By the time the bubble corrects and the pricing landscape reorganizes, a locally-run open model will be within acceptable range of GPT-5 for the large majority of everyday use cases.

**The companies actually enabling sovereignty:**

*Mistral*: small models, open weights, European legal jurisdiction, no strategic dependency on US cloud infrastructure. Their 7B and 8x7B models punched above their weight class and established the benchmark for efficient open models.

*DeepSeek*: efficiency research published openly, weights released under permissive licenses, no outside investors to force a pivot toward closed access. Their R1 model release was arguably the most consequential open-weight release since LLaMA — not because of the raw capability numbers but because of the reasoning approach it demonstrated.

*The llama.cpp ecosystem*: Georgi Gerganov's original implementation has become the inference foundation that makes local AI practical. Without it, running models on consumer hardware would require either Python with complex dependencies or paying cloud bills.

*RISC-V*: the hardware sovereignty path with the longest timeline. RISC-V is an open instruction set architecture — no company owns it, no license is required to build a chip around it. The RISC-V Foundation has significant industry backing. It will not displace ARM or x86 in the next five years, but it is the only plausible path to hardware sovereignty that doesn't terminate at ASML. Call it a 10-15 year horizon — meaningful for institutions planning infrastructure, not for users deciding what to run this year.

**The companies that claim sovereignty but don't deliver it:**

Any national AI mission that runs on NVIDIA GPUs — which is all of them, currently — is not sovereign at the hardware layer. The mission may be real, the model may be locally fine-tuned, the data may stay within the country. But the training runs terminate at TSMC via NVIDIA, and the inference hardware comes from Santa Clara. That's not a reason not to build national AI. It is a reason not to call it sovereignty.

Any "sovereign cloud" that still routes through US hyperscaler infrastructure — and many European "sovereign cloud" offerings do exactly this, running on Azure or AWS with a European legal wrapper — is jurisdictionally sovereign in the sense that contracts are governed by European law. It is not operationally sovereign in the sense that the infrastructure could be cut off.

Any open-weight model distributed only through Hugging Face, without a mirror strategy, is one Hugging Face policy change away from access interruption. This is a minor operational concern in normal times. It becomes significant in the scenario where governments start pressuring platform companies to restrict access to specific models.

---

## The Through-Line

In the late 1940s, the United States made a decision. Operation Paperclip — the classified program that recruited former Nazi rocket engineers into American government service — was a strategic bet: the technical capability these men represented exceeded the ethical cost of employing them. Wernher von Braun, who had used slave labor at Mittelwerk to build the V-2, became the most famous engineer in NASA's history. His test stands at what is now Redstone Arsenal are still in use.

The institutional lineage runs unbroken. Thiokol propulsion became ATK became Northrop Grumman Innovation Systems. Chrysler Defense became General Dynamics. The defense contractors who built the moon program became the defense contractors who build missiles today. Leidos — the company at the top of the contractor genealogy tree — holds $16.7 billion in annual revenue and 26,000 employees in Huntsville alone. The specific engineers are gone. The infrastructure they built, the institutions they filled, and the federal relationship they cultivated are not.

The AI version of this story is being written right now. The framing is different — "innovation leadership," "national security," "not letting China win" — but the structure is identical: a small number of physical or intellectual chokepoints, a capital layer flowing toward those chokepoints, a national security framing that overrides uncomfortable questions about funding sources and conflict of interest, and a future reckoning when the bets don't pay out at the implied scale.

Saudi capital is flowing into US AI infrastructure through Stargate. UAE tech deals are being conditioned on removing Chinese components from supply chains. Export controls designed to prevent Chinese AI dominance accidentally produced the efficiency breakthroughs that are now destabilizing the US AI business model.

Every layer of this story is entangled with every other layer.

The difference this time is that the technology is becoming small enough to escape the chokepoints.

A 7-billion-parameter model runs on a MacBook. A quantized reasoning model runs on a Raspberry Pi 5. The efficiency ratchet is turning in one direction. The capability that required a data center in 2022 ran in a browser in 2024 and fits on a phone in 2026. The physical chokepoints — TSMC, ASML, NVIDIA — will remain. The capital concentrations will persist. The talent networks will continue crossing borders regardless of what flags the governments wave.

But for the first time in the history of strategic AI, the capability you need for genuine sovereignty — the ability to run a model that serves your actual needs, on hardware you own, in infrastructure you control, without a dependency that can be revoked — fits inside a device that costs less than a month of API subscription fees.

That convergence is the real sovereign AI story. It just doesn't require a government announcement.

---

*The evidence base for this piece is a structured research database of 30 AI organizations, 76 people, 40 funders, and 80 relationship edges constructed from public sources: funding announcements, corporate filings, academic papers, and news coverage. Specific dependency chains (infrastructure_dependency edges), capital relationships (strategic_backer edges), and talent flows (spawned_talent edges) are documented and queryable. The claims about chokepoints, funding structures, and organizational relationships are drawn from that evidence base, not from pattern-matching on intuition.*

---

*~6,400 words*
