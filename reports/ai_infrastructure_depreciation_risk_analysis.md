# AI Infrastructure Depreciation: Real Risks vs. Overstated Risks

## Sourced Analysis — March 2026

---

# PART I: REAL RISKS

---

## 1. Depreciation Mismatch Risk

### The Core Problem

Hyperscalers depreciate GPU/server assets over 5-6 years, while NVIDIA releases major new GPU architectures annually (Hopper -> Blackwell -> Rubin -> Rubin Ultra). If the *economic* useful life of GPUs is closer to 2-3 years due to rapid obsolescence, companies are systematically understating depreciation expense and overstating earnings.

### Company-by-Company Depreciation History

| Company    | 2020 Useful Life | Current Useful Life | Direction of Change |
|------------|-----------------|--------------------|--------------------|
| **Microsoft** | 4 years | 6 years | Extended |
| **Amazon**    | 3 years | 5 years (shortened from 6 in Feb 2025) | Extended then partially reversed |
| **Alphabet**  | 3 years | 6 years | Extended |
| **Meta**      | 3 years | 5.5 years | Extended |
| **Oracle**    | 5 years | 6 years | Extended |

**Sources:** [CNBC — The question everyone in AI is asking: How long before a GPU depreciates?](https://www.cnbc.com/2025/11/14/ai-gpu-depreciation-coreweave-nvidia-michael-burry.html); [SiliconANGLE — Resetting GPU depreciation](https://siliconangle.com/2025/11/22/resetting-gpu-depreciation-ai-factories-bend-dont-break-useful-life-assumptions/)

### Quantifying the Gap

**Michael Burry's estimate (November 2025):** If a 2.5-year depreciation cycle is more appropriate than 5-6 years, the industry will **understate depreciation by ~$176 billion between 2026-2028**, inflating reported operating income at:
- **Oracle:** 26.9-62% earnings overstatement by 2028
- **Meta:** 20.8% earnings overstatement by 2028
- **Microsoft:** >20% earnings overstatement
- **Alphabet:** >20% earnings overstatement

**Source:** [CNBC — Michael Burry accuses AI hyperscalers of artificially boosting earnings](https://www.cnbc.com/2025/11/11/big-short-investor-michael-burry-accuses-ai-hyperscalers-of-artificially-boosting-earnings.html); [Yahoo Finance — Michael Burry warns of $176B depreciation understatement](https://finance.yahoo.com/news/michael-burry-warns-176-billion-173613512.html)

### The Amazon Signal

Amazon's February 2025 decision to **shorten** the useful life of certain servers from 6 back to 5 years is arguably the most important data point. Amazon explicitly cited "the increased pace of technology development, particularly in the area of artificial intelligence and machine learning." This resulted in:
- **$700 million reduction** in 2025 operating income
- **$920 million accelerated depreciation charge** in Q4 2024 for early-retired equipment

This is significant because Amazon moved in the **opposite direction** from Meta (which extended to 5.5 years in the same quarter). The divergence — under identical technological conditions — confirms that useful life is a subjective management estimate.

**Source:** [Deep Quarry — Amazon revises server lifespan amid AI shift](https://deepquarry.substack.com/p/amazon-revises-server-lifespan-amid)

### Impact on Reported Financials

Microsoft's overall depreciation rate as a percentage of net PP&E declined from ~30-34% during FY2014-2020 to just ~15% in FY2024, largely attributable to extended useful life assumptions. At Meta, the January 2025 extension booked a **$2.9 billion depreciation reduction** in the same quarter.

**Source:** [MBI Deep Dives — Big Tech's Deteriorating Earnings Quality](https://www.mbi-deepdives.com/big-tech-earnings-quality/)

---

## 2. Stranded Asset Risk

### What Would Trigger Stranding?

GPU infrastructure becomes economically stranded when the cost of operating existing hardware exceeds the cost of deploying newer, more efficient alternatives — not when it physically stops working.

**Key triggers:**

1. **Rapid architectural leaps:** NVIDIA's GPU roadmap shows Blackwell Ultra at ~1,400W per GPU (2025) and Vera Rubin at ~1,800W projected (2026). Each generation delivers 2-5x inference performance improvements, making older GPUs economically uncompetitive for high-margin workloads faster than depreciation schedules assume.

2. **Power infrastructure mismatch:** Facilities designed for 2024-2025 thermal envelopes risk becoming inadequate for 2027-2028 GPU generations. A 1 GW campus has 30-year civil works, but GPU generations refresh every 18-24 months.

3. **Customer concentration for GPU-as-a-service providers:** CoreWeave derives 62% of revenue from Microsoft. If Microsoft shifts workloads to its own Azure infrastructure, CoreWeave's specialized facilities become stranded.

4. **Demand shift without revenue:** AI-related services are expected to deliver only about $25 billion in revenue in 2025, roughly 10% of what hyperscalers are spending on infrastructure. If this ratio doesn't improve materially, write-downs become likely.

**Sources:** [Tony Grayson — Year 6 Survival Model: AI Data Center Investment Risk](https://www.tonygrayson.ai/post/ai-data-center-investment-risk); [Development Corporate — The AI Infrastructure Bubble](https://developmentcorporate.com/saas/the-ai-infrastructure-bubble-4-surprising-reasons-the-90-billion-data-center-boom-could-end-in-a-bust/)

### The Telecom Parallel

The most instructive historical analogy is not dot-com but **telecom infrastructure**. Global Crossing and others laid >80 million miles of fiber optic cable in the late 1990s. Four years after the bust, 85-95% remained unused ("dark fiber"). The demand wasn't wrong — it just arrived on a longer timeline than the financing assumed. AI data centers face the same pattern: demand may persist while the specific assets built to serve it become stranded.

**Source:** [Fortune — AI dot-com bubble parallels](https://fortune.com/2025/09/28/ai-dot-com-bubble-parallels-history-explained-companies-revenue-infrastructure/)

### Financial Architecture Risk

Creditors funding GPU infrastructure projects (banks, insurers, pension funds, private credit) underwrite based on 7-15 year useful life assumptions, with stable cash flows and recoverable collateral values. But economic depreciation is front-loaded at 30-40% in year one as next-gen hardware arrives. GPU-backed debt instruments from BlackRock, JPMorgan, and Carlyle Group are particularly exposed.

**Source:** [Ponderwall — GPU Depreciation Exposed](https://ponderwall.com/index.php/2025/11/23/gpu-depreciation-ai-economics/)

---

## 3. Cash Flow vs. Earnings Divergence

### The Mechanism

Extending depreciation from 3 years to 6 years cuts annual depreciation expense roughly in half for each asset, directly boosting operating income and net income. But **cash outflows are identical** — the company paid the same amount for the GPU regardless of how it's depreciated. The result is a widening gap between reported earnings (which look increasingly good) and free cash flow (which reflects the real cash burden).

### Specific Examples

**Alphabet (Google):**
- Operating cash flow: 17.7% CAGR since late 2022 AI boom, reaching $151B trailing
- Free cash flow: Only 5.6% CAGR because CapEx has exploded at 37% CAGR
- FCF margin has shrunk from 22% to 19%
- On an earnings basis (benefiting from extended depreciation): trades at ~30x P/E
- On a free cash flow basis (reflecting full CapEx burden): implied multiple in the **low-50s**

**Meta:**
- FCF projected to decline from **$54B in 2024 to ~$20B in 2025** despite strong reported earnings
- This is a 63% decline in free cash flow while reported earnings remain robust
- The extended depreciation (to 5.5 years) masks $2.9B/quarter in reduced depreciation charges

**The Industry Pattern:**
- Hyperscalers now spend 45-57% of revenue on CapEx — ratios more typical of industrial/utility companies than tech
- Aggregate CapEx, after buybacks and dividends, now **exceeds projected cash flows**, necessitating external debt funding
- Annual depreciation expense could climb from $150B to $400B over the next five years as CapEx flows through

**Sources:** [MBI Deep Dives — Big Tech's Deteriorating Earnings Quality](https://www.mbi-deepdives.com/big-tech-earnings-quality/); [Sparkline Capital — Surviving the AI Capex Boom](https://www.sparklinecapital.com/post/surviving-the-ai-capex-boom); [GWK Invest — When Will AI Investments Start Paying Off?](https://www.gwkinvest.com/insight/macro/when-will-ai-investments-start-paying-off/)

### What Investors Should Watch

The key KPI shift: operating cash flow and free cash flow are becoming far more important than GAAP or non-GAAP net income. Watch for:
- Declining FCF despite growing reported earnings
- Rising debt levels to fund CapEx
- Circular financing arrangements (suppliers funding their own clients)
- Aggressive useful life assumptions that mask true depreciation costs
- CapEx growing faster than revenue

---

## 4. NVIDIA Customer Concentration Risk

### The Numbers

NVIDIA does not name its top customers in SEC filings. However, the concentration is severe and worsening:

| Period | Concentration |
|--------|--------------|
| FY Q2 2025 (Jul 2024) | 4 customers = **46%** of total revenue |
| FY Q3 2025 (Oct 2024) | 3 customers = **36%** of revenue (4th at 12% over 9 months) |
| FY Q2 2026 (Jul 2025) | 2 customers = **39%** of revenue |
| Late 2025 | 4 customers = **61%** of revenue |

**UBS analyst Timothy Arcuri** estimated that Microsoft alone accounted for **19% of NVIDIA's total revenue** in fiscal year 2024.

88% of NVIDIA's revenue comes from AI chips for data centers, and NVIDIA disclosed that half of this came from large technology companies and cloud providers (Microsoft, Amazon, Google, Meta, Oracle).

**Sources:** [Tech Startups — 61% of NVIDIA's revenue from four mystery customers](https://techstartups.com/2025/11/21/61-of-nvidias-revenue-comes-from-just-four-mystery-customers-is-this-a-warning-sign-for-ai/); [TechCrunch — Two mystery customers at 39% of Q2 revenue](https://techcrunch.com/2025/08/30/nvidia-says-two-mystery-customers-accounted-for-39-of-q2-revenue/); [Yahoo Finance — 36% from 3 mystery customers](https://finance.yahoo.com/news/36-nvidias-35-billion-q3-095700452.html)

### What Happens If One Pulls Back

All four major customers (Microsoft, Amazon, Google, Meta) are designing custom AI chips:
- **Google:** TPUs (now in 6th generation)
- **Amazon:** Trainium and Inferentia chips
- **Microsoft:** Maia AI accelerator
- **Meta:** MTIA (Meta Training and Inference Accelerator)

AllianceBernstein estimates NVIDIA captures **30% of total AI data center spending as profit**. If even one major customer successfully shifts 30-50% of workloads to custom silicon, the revenue impact could be $15-25B annually. The custom chip threat is not theoretical — it's actively in deployment.

However, mitigating this risk: NVIDIA has a "lengthy head start" in software ecosystem (CUDA), and it could take years before custom chips achieve comparable breadth. The 2025-2026 CapEx plans from all four companies include massive NVIDIA purchases.

**Source:** [Motley Fool — 46% of Nvidia's revenue from 4 mystery customers](https://www.fool.com/investing/2024/10/30/46-nvidia-revenue-came-from-4-mystery-customers/)

---

## 5. The "CapEx Trap"

### The Scale

| Company | 2024 CapEx | 2025 CapEx | 2026 CapEx (Projected) |
|---------|-----------|-----------|----------------------|
| **Microsoft** | ~$56B | $64.6B | >$140B (+59% from FY2025 $88B) |
| **Amazon** | ~$75B | $128B | $200B |
| **Alphabet** | ~$50B+ | $91B | $175-185B |
| **Meta** | ~$40B | $72B | $115-135B |
| **Oracle** | - | - | $50B |
| **Combined** | ~$221B+ | ~$356B | **~$660-690B** |

Goldman Sachs projects total hyperscaler CapEx 2025-2027 will reach **$1.15 trillion** — more than double the $477B spent 2022-2024.

**Sources:** [Goldman Sachs — Why AI companies may invest more than $500B in 2026](https://www.goldmansachs.com/insights/articles/why-ai-companies-may-invest-more-than-500-billion-in-2026); [Futurum — AI Capex 2026: The $690B Infrastructure Sprint](https://futurumgroup.com/insights/ai-capex-2026-the-690b-infrastructure-sprint/)

### The Trap Dynamics

**The competitive imperative:** No hyperscaler can afford to slow spending without risking being left behind. As one analysis put it: "Hyperscalers can't slow spending without losing the AI war." This creates a prisoner's dilemma where rational individual behavior leads to collective overinvestment.

**The ROI gap:** AI-related services generated only ~$25B in revenue in 2025, roughly 10% of what hyperscalers spent on infrastructure that year. Only 25% of AI initiatives have delivered expected ROI, and fewer than 20% have been scaled enterprise-wide. The estimated useful life on this infrastructure is 3-5 years, meaning hyperscalers need significant returns before 2030.

**The capital intensity shift:** Hyperscalers now spend 45-57% of revenue on CapEx, ratios previously unthinkable for technology companies and more typical of utilities or industrial firms.

**The financing strain:** Aggregate CapEx, after buybacks and dividends, now exceeds projected cash flows. Companies are increasingly leaning on debt markets, fundamentally changing their capital structure.

**Sources:** [TradingView/Invezz — Why hyperscalers can't slow spending](https://www.tradingview.com/news/invezz:751717ae0094b:0-looking-ahead-to-2026-why-hyperscalers-can-t-slow-spending-without-losing-the-ai-war/); [Guinness Global Investors — Are we in an AI bubble?](https://www.guinnessgi.com/insights/are-we-in-an-ai-bubble); [CNBC — Can hyperscalers justify their huge AI capex?](https://www.cnbc.com/2026/02/13/tech-download-newsletter-ai-capex-hyperscalers.html)

### The Bull Case Counter

- All hyperscalers report being **supply-constrained**, not demand-constrained
- Much capacity is **pre-sold** before data centers are built
- Alphabet's cloud backlog surged 55% sequentially to >$240B
- AI CapEx at ~0.8% of GDP remains below peak levels of previous tech booms (1.5%+ of GDP)
- Alphabet reported reducing Gemini serving costs by 78% over 2025 through model optimization

---

# PART II: OVERSTATED / MISUNDERSTOOD RISKS

---

## 1. "GPUs Become Worthless Overnight" — Why This Is Wrong

### Evidence of Continued Use

**NVIDIA's A100 (launched 2020) is still virtually impossible to find in 2026.** About one-third of NVIDIA's $62.3B quarterly data center revenue — effectively over **$20 billion** — is still driven by Ampere (A100) and previous-generation Hopper (H100) chips.

Azure only retired its original NC-series VMs (powered by Nvidia K80, P100, and P40 GPUs, launched 2014-2016) in August/September 2023. This implies a **useful service life of 7-9 years** for those architectures.

**Source:** [Trefis — Why Is Nvidia's 6 Year Old GPU Still Sold Out?](https://www.trefis.com/stock/nvda/articles/591667/why-is-nvidias-6-year-old-gpu-still-sold-out/2026-02-26); [MBI Deep Dives — Why I don't worry (as much) about big tech's depreciation schedule](https://www.mbi-deepdives.com/why-i-dont-worry-as-much-about-big-techs-depreciation-schedule/)

### Secondary Market Pricing Holds Up

| GPU | Age | Secondary Market Price | % of Original |
|-----|-----|----------------------|--------------|
| A100 40GB | ~5 years | $8,000-$12,000 | ~60-80% of original |
| A100 80GB | ~5 years | $12,000-$18,000 | ~50-70% of original |
| H100 (1-2 years used) | 2-3 years | 70-85% of new pricing | - |
| H100 (2-3 years used) | 3+ years | 50-70% of new pricing | - |

CoreWeave's H100 GPUs from 2022 contract expirations immediately **rebooked at 95% of original pricing.**

**Source:** [Introl — Secondary GPU Markets](https://introl.com/blog/secondary-gpu-markets-buying-selling-used-hardware-guide-2025); [Silicon Data — H100 GPU Market Value Trends](https://www.silicondata.com/use-cases/h100-gpu-market-value-trends/)

### The "Value Cascade" Framework

GPUs don't become worthless — they move down the value chain:
- **Years 1-2:** Frontier model training (highest margin)
- **Years 3-4:** Inference workloads (still high value)
- **Years 5-6:** Batch processing, fine-tuning, cost-optimized inference

An A100 purchased in 2021 for frontier training can be repurposed in 2024 for premium inference, then shifted again in 2026 to bulk throughput-oriented inference. This deployment model extends the useful economic life from the oft-cited 2 years to a potentially **6-7 year** window.

**Source:** [Stanley Laman — Why GPU Useful Life Is the Most Misunderstood Variable in AI Economics](https://www.stanleylaman.com/signals-and-noise/gpus-how-long-do-they-really-last)

### Why Older GPUs Retain Demand

A100s remain booked because **inference workloads don't require cutting-edge silicon.** Organizations training frontier models need B200s, but organizations serving production inference often don't. A100s are more affordable and available than backlogged Blackwell systems, making them the default starting point for AI startups and university labs. These developers write, test, and optimize code using NVIDIA's CUDA platform, creating ecosystem lock-in.

---

## 2. "It's Exactly Like Dot-Com" — Key Structural Differences

### The Fundamental Distinction

The dot-com bubble was built on companies with little to no revenue, weak business models, and no financial discipline. Over 85% of pure-play dot-com firms went bust.

**Today's AI leaders are fundamentally different:**

| Metric | Dot-Com Era (2000) | AI Era (2025) |
|--------|-------------------|---------------|
| Profitability | Most companies had zero profits | NVIDIA: 53.4% net margin; MSFT, GOOG, META all highly profitable |
| Company maturity | Juvenescent startups | Decades-old firms with established businesses |
| Revenue | Often negligible | Combined revenue in hundreds of billions |
| Cash reserves | Often near-zero | Hundreds of billions in cash on hand |
| CapEx source | Speculative venture capital | Reinvested free cash flow from profitable operations |

Federal Reserve Chair Jerome Powell (2024): *"This is different in the sense that these companies, the companies that are so highly valued, actually have earnings and stuff like that."*

**Source:** [VanEck — Is AI a Bubble?](https://www.vaneck.com/us/en/blogs/thematic-investing/is-ai-a-bubble-the-dot-com-bubble-vs-todays-ai-revolution/); [iShares — Are AI Stocks in a Bubble?](https://www.ishares.com/us/insights/ai-stocks-bubble-2025-valuation-outlook)

### Valuations Are Elevated but Not Extreme

The S&P 500 trades at ~28x P/E. Excluding the Magnificent Seven, ~24x — slightly above the long-term average of 21x since 1990, but not the 60-100x multiples common in 2000. Today's valuations are backed by real earnings, strong FCF, and measurable productivity gains.

**Source:** [Warren Street Wealth Advisors — Decoding the AI Hype](https://warrenstreetwealth.com/decoding-the-ai-hype-how-todays-market-compares-to-the-dot-com-bubble/)

### Where the Comparison Has Some Merit

The parallel that **does** hold is infrastructure overinvestment. Telecom companies laid >80 million miles of fiber in the 1990s; 85-95% remained dark four years after the bust. The demand eventually arrived (streaming, cloud, mobile), but on a much longer timeline than financing assumed. The same risk exists for AI data centers: demand may be real but slower than CapEx timelines require.

The circular revenue concern also has merit: some of the "booming" AI revenue may reflect internal recycling of investment capital rather than organic external demand. Suppliers funding their own clients, circular contracts counted twice as revenue — these are "classic symptoms of late-cycle exuberance."

**Sources:** [Fortune — AI dot-com parallels](https://fortune.com/2025/09/28/ai-dot-com-bubble-parallels-history-explained-companies-revenue-infrastructure/); [World Economic Forum — What we mean when we talk about an AI bubble](https://www.weforum.org/stories/2025/10/artificial-intelligence-bubble-dot-com-tulip-mania/)

---

## 3. "Depreciation Extension Is Fraud" — Why This Overstates the Case

### What GAAP Actually Requires

Under GAAP (ASC 360-10-35-4), depreciation is "a process of allocation, not of valuation." A change in estimated useful life is a **change in accounting estimate** under ASC 250-10 and is accounted for prospectively. This is an explicitly permitted accounting treatment — not a loophole.

Companies are **required** to periodically reassess useful lives and adjust when evidence supports a change. Both extending and shortening useful lives are legitimate if backed by:
- Engineering studies and maintenance records
- Industry benchmarks
- Actual observed asset performance
- Technology roadmap analysis

**Source:** [PwC Viewpoint — Determining the useful life and salvage value](https://viewpoint.pwc.com/dt/us/en/pwc/accounting_guides/property_plant_equip/property_plant_equip_US/chapter_4_depreciati_US/32_determining_the_u_US.html); [CPA Journal — Depreciable Asset Lives](https://www.cpajournal.com/2016/09/08/depreciable-asset-lives/)

### Why Burry's "Fraud" Framing Is Too Strong

Michael Burry called extending depreciation "one of the more common frauds of the modern era." But:

1. **Auditors review these estimates.** All Big 4 auditing firms have signed off on these useful life assumptions. While auditors can miss things, calling it "fraud" implies deliberate deception, which is a higher bar than a potentially aggressive estimate.

2. **There IS evidence supporting longer useful lives.** Azure ran K80/P100/P40 GPUs for 7-9 years. A100s remain in high demand after 5+ years. CoreWeave rebooks H100s at 95% of original pricing after initial contracts expire.

3. **Amazon's shortening validates the estimate process.** When Amazon shortened its useful life estimate in February 2025, it demonstrated that the system works — management reassessed and revised downward when evidence supported it.

4. **New transparency is coming.** ASU 2024-03, effective for fiscal years beginning after December 15, 2025, will require disaggregated disclosure of depreciation expenses, making aggressive assumptions more visible.

**Source:** [ICAEW — What to remember when auditing depreciation](https://www.icaew.com/insights/viewpoints-on-the-news/2022/feb-2022/what-to-remember-when-auditing-depreciation); [EY — FRDBB technical guidance](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-us/technical/accountinglink/documents/ey-frdbb1499-08-25-2025.pdf)

### Where the Criticism Does Have Teeth

That said, the criticism is not baseless:
- The **divergence** between Meta (extending to 5.5 years) and Amazon (shortening to 5 years) in the same quarter under the same technological conditions reveals the subjectivity involved
- The **pattern** of repeated extensions (Meta: 3 -> 4 -> 4.5 -> 5 -> 5.5 years) always in the direction of higher earnings is suspicious
- The fact that these policies were originally set for **CPU-dominated server fleets** and then applied wholesale to GPU-heavy configurations deserves scrutiny
- The aggregate impact ($176B+ in reduced depreciation through 2028) is material enough to warrant skepticism

---

## 4. "All CapEx Is Wasted" — Evidence That AI Is Generating Real Value

### Coding Assistants (Strongest Evidence)

- Coding tools led all AI spending at **$4 billion in 2025**, representing 55% of departmental AI spend
- 62% of development teams report at least **25% productivity gains** from AI tools (2025 State of Engineering Management report)
- Developers save **30-60% of time** on routine coding tasks
- DX CEO Abi Noda reports **2-3 hours per week of time savings** per developer using AI code assistants
- Anthropic's research: more than **25% of AI-assisted work** consisted of tasks that simply wouldn't have been done otherwise (scaling projects, internal tools, exploratory work)
- GitHub estimates improved developer productivity through AI could add **$1.5 trillion to global GDP**

**Source:** [Index.dev — AI Coding Assistant ROI: Real Productivity Data 2025](https://www.index.dev/blog/ai-coding-assistants-roi-productivity)

### Customer Service (Strong Evidence)

- Companies see average returns of **$3.50 for every $1 invested** in AI customer service, with leaders achieving up to 8x ROI
- In retail companies using Freddy AI Agent: **53% of all incoming queries** resolved by AI agents
- **60% of customer service teams** using AI copilots report significantly improved agent productivity
- **42.7% improvement** in First Response Time in software/internet companies
- Positive ROI typically materializes within **8-14 months**

**Source:** [Freshworks — How AI is unlocking ROI in customer service](https://www.freshworks.com/How-AI-is-unlocking-ROI-in-customer-service/); [Google Cloud — ROI of AI: Agents are delivering for business now](https://cloud.google.com/transform/roi-of-ai-how-agents-help-business)

### Broader Enterprise AI

- **52% of executives** report deploying AI agents in production (Google 2025 ROI Report)
- **74% of executives** report achieving ROI within the first year
- Among those reporting productivity gains, **39% have seen productivity at least double**
- Average reported ROI of **171%**

### Important Caveats

- Only **25% of AI initiatives** have delivered expected ROI to date
- Fewer than **20%** have been scaled enterprise-wide
- **14%** have yet to see any benefit; **19%** say it's too early to measure
- A **MIT study** found 95% of AI pilot projects fail to yield meaningful results
- When asked about scaling barriers, **49%** cited the high cost of inference as the top limitation

The picture is nuanced: AI is generating genuine value in specific, well-defined use cases (coding, customer service, search), but broader enterprise transformation remains early-stage and uncertain.

**Source:** [VentureBeat — AI Agents are delivering real ROI](https://venturebeat.com/orchestration/ai-agents-are-delivering-real-roi-heres-what-1-100-developers-and-ctos)

---

## 5. "Power Consumption Makes Old GPUs Useless" — More Nuanced Than It Appears

### The Counterintuitive Truth: Older GPUs Draw LESS Power

| GPU | Architecture | TDP (Watts) |
|-----|-------------|-------------|
| P100 | Pascal (2016) | 250W |
| V100 | Volta (2017) | 300W |
| A100 | Ampere (2020) | 400W |
| H100 | Hopper (2022) | 700W |
| B200 | Blackwell (2024) | 1,000-1,200W |
| Vera Rubin | Vera Rubin (2026 projected) | ~1,800W |

Absolute power consumption has roughly **tripled** from A100 to B200. This means:

1. **Older GPUs are easier to cool and deploy** in existing facilities not designed for the extreme thermal loads of next-gen chips
2. **Power-constrained facilities** can actually run MORE A100s in the same power envelope than B200s (e.g., a 1MW allocation supports ~2,500 A100s vs. ~1,000 B200s)
3. **Inference workloads are often memory-bound**, meaning the GPU isn't running at full power — actual draw is well below TDP for many production inference scenarios

**Source:** [TRG Datacenters — NVIDIA H100 Power Consumption Guide](https://www.trgdatacenters.com/resource/nvidia-h100-power-consumption/); [Clarifai — NVIDIA B200 vs H100](https://www.clarifai.com/blog/nvidia-b200-vs-h100)

### Performance Per Watt IS Improving Dramatically

The nuance: while older GPUs draw less absolute power, newer GPUs deliver far more **work per watt**:

- H100 achieves **20 TFLOPS/W** at FP16 vs. A100's 10 TFLOPS/W (2x improvement)
- B200 achieves ~8.3 TFLOPS/W at FP8 vs. H100's ~5.7 TFLOPS/W (45% improvement)
- B200 uses **0.53 joules per token (FP8)** vs. H100's 2.46 joules — a **4.6x improvement** in energy per token for LLM training

**Source:** [Lightly.ai — NVIDIA Blackwell B200 vs H100 Real-World Benchmarks](https://www.lightly.ai/blog/nvidia-b200-vs-h100); [AceCloud — B200 vs H200 vs H100 vs A100 Complete Guide](https://acecloud.ai/blog/nvidia-b200-vs-h200-h100-a100/)

### The Balanced View

The "old GPUs are useless because of power costs" argument fails because:

1. **Total cost matters, not just power cost.** An A100 at $10K + higher power costs may still be cheaper than a B200 at $30-40K + lower per-token power costs for many workloads, especially at smaller scale.

2. **Not all workloads need maximum efficiency.** Batch processing, fine-tuning, academic research, and cost-optimized inference can tolerate lower performance-per-watt ratios.

3. **Infrastructure compatibility.** Many existing data centers were designed for 10-15kW per rack. A100s at 400W are far more compatible with this infrastructure than B200s requiring 40kW+ liquid-cooled racks.

Where the argument **does** hold: for frontier training and high-throughput inference at hyperscaler scale, the performance-per-watt advantage of newer GPUs makes older generations economically uncompetitive. A company running millions of inference queries per second will save dramatically on power by upgrading, even accounting for the hardware cost.

---

# SUMMARY: RISK MATRIX

| Risk | Severity | Likelihood | Timeframe | Notes |
|------|----------|-----------|-----------|-------|
| **Depreciation mismatch** | HIGH | HIGH | 2026-2028 | $176B+ gap if 2.5-year life is correct |
| **Stranded assets** | MEDIUM-HIGH | MEDIUM | 2027-2030 | Depends on pace of architectural change |
| **Cash flow vs earnings divergence** | HIGH | NEAR-CERTAIN | Already happening | Meta FCF: $54B -> $20B while earnings hold |
| **NVIDIA concentration** | MEDIUM | MEDIUM | 2026-2028 | Custom chips are real but years away from parity |
| **CapEx trap** | HIGH | HIGH | Now-2028 | $660B+ committed for 2026; no one can stop |
| **"GPUs worthless overnight"** | OVERSTATED | LOW | N/A | Value cascade; A100s still booked after 5 years |
| **"Exactly like dot-com"** | OVERSTATED | LOW-MEDIUM | N/A | Real profits, real companies, but infra parallel valid |
| **"Depreciation is fraud"** | OVERSTATED | LOW | N/A | Legitimate under GAAP, but pattern is aggressive |
| **"All CapEx is wasted"** | OVERSTATED | LOW | N/A | Coding, customer service showing real ROI |
| **"Power makes old GPUs useless"** | OVERSTATED | LOW | N/A | Less absolute power; viable for many workloads |
