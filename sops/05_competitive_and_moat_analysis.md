# SOP-005: Competitive & Moat Analysis

**Version:** 1.0
**Last Updated:** 2026-02-09
**Owner:** FE-Analyst Platform
**Module:** `src/analysis/moat.py`
**Config:** `configs/ai_moat_universe.yaml`
**Status:** Active

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Key Concepts and Theoretical Foundation](#2-key-concepts-and-theoretical-foundation)
3. [The Six Moat Dimensions -- Deep Dive](#3-the-six-moat-dimensions----deep-dive)
   - 3.1 [Market Dominance (20% Weight)](#31-market-dominance-20-weight)
   - 3.2 [Switching Costs (15% Weight)](#32-switching-costs-15-weight)
   - 3.3 [Technology Lock-in (15% Weight)](#33-technology-lock-in-15-weight)
   - 3.4 [Supply Chain Criticality (20% Weight)](#34-supply-chain-criticality-20-weight)
   - 3.5 [Pricing Power (15% Weight)](#35-pricing-power-15-weight---quantitative)
   - 3.6 [Barriers to Entry (15% Weight)](#36-barriers-to-entry-15-weight)
4. [Moat Scoring Methodology](#4-moat-scoring-methodology)
5. [Porter's Five Forces Analysis](#5-porters-five-forces-analysis)
6. [Competitive Landscape Mapping](#6-competitive-landscape-mapping)
7. [Moat Durability Assessment](#7-moat-durability-assessment)
8. [AI Supply Chain-Specific Moat Patterns](#8-ai-supply-chain-specific-moat-patterns)
9. [Red Flags for Moat Erosion](#9-red-flags-for-moat-erosion)
10. [Running the Analysis](#10-running-the-analysis)
11. [Output Format and Interpretation](#11-output-format-and-interpretation)
12. [Appendix A -- Moat Dimension Scoring Rubrics](#appendix-a----moat-dimension-scoring-rubrics)
13. [Appendix B -- Universe Coverage by Category](#appendix-b----universe-coverage-by-category)
14. [Appendix C -- Data Sources and Update Cadence](#appendix-c----data-sources-and-update-cadence)

---

## 1. Purpose and Scope

### Why This Analysis Exists

Competitive moat analysis identifies companies with **durable structural advantages** that protect long-term returns against competitive erosion. In the context of the AI chip supply chain, moat analysis serves a purpose that generic financial analysis cannot: it identifies **bottleneck positions** -- companies whose products or services are so critical, so difficult to replicate, and so deeply embedded in the production process that they command pricing power, customer loyalty, and defensibility measured not in quarters but in decades.

This is the most differentiated analysis the FE-Analyst platform performs. While fundamental analysis, technical analysis, and valuation modeling are widely available, our moat scoring framework is purpose-built for the AI supply chain and provides insight that standard financial tools miss entirely.

### Scope

This SOP covers:

- **What:** A six-dimension moat scoring framework that produces a composite score (0-100) and classification (WIDE / NARROW / WEAK / NO MOAT) for each company in the AI chip supply chain universe.
- **Who:** 60+ companies across 8 supply chain categories tracked in `configs/ai_moat_universe.yaml`.
- **How:** A hybrid methodology combining five qualitative dimension scores (from domain expertise, stored in the config) with one quantitative dimension score (Pricing Power, computed from financial statements by `src/analysis/moat.py`).
- **Why:** To differentiate between companies with temporary tailwinds (riding the AI cycle) and companies with permanent structural advantages (irreplaceable links in the AI production chain).

### Relationship to Other Analyses

The moat score is a **standalone analysis module** that complements the platform's composite stock score. The composite score (`src/analysis/scoring.py`) weights five dimensions: Fundamental (30%), Valuation (25%), Technical (20%), Risk (15%), and Sentiment (10%). The moat score operates in parallel and provides a **strategic overlay** that answers a different question:

| Composite Score Answers | Moat Score Answers |
|---|---|
| "Is this stock attractively priced right now?" | "Will this company still dominate in 5-10 years?" |
| "What are the near-term signals?" | "How defensible is the business?" |
| "Buy, hold, or sell?" | "Is this a durable franchise?" |

The moat score is especially valuable when the composite score is neutral (45-55 range). A WIDE MOAT classification elevates conviction in a borderline composite score; a NO MOAT classification warrants skepticism even if the composite score looks attractive.

---

## 2. Key Concepts and Theoretical Foundation

### 2.1 What Is a Competitive Moat?

A competitive moat is a **sustainable structural advantage** that allows a company to earn returns above its cost of capital for an extended period. The term, popularized by Warren Buffett, draws an analogy to the water-filled trench surrounding a medieval castle: the wider and deeper the moat, the harder it is for competitors to attack the business.

**A moat is NOT:**
- A temporary cost advantage from a favorable contract
- Market momentum or hype-driven demand
- First-mover advantage without structural reinforcement
- A large revenue base alone (size without defensibility)
- Government subsidies without enduring structural barriers

**A moat IS:**
- A structural condition that persists even when management quality varies
- Self-reinforcing over time (the advantage compounds)
- Observable in financial outcomes over multiple cycles
- Rooted in the economics of the industry, not just the company's execution

### 2.2 Morningstar/Buffett Framework -- Adapted for AI Supply Chain

Our framework draws on Morningstar's economic moat methodology but adapts it significantly for the unique dynamics of the AI semiconductor supply chain:

| Morningstar Standard Moat Sources | Our Adaptation |
|---|---|
| Cost advantage | Captured in Pricing Power (margin analysis) |
| Intangible assets (brands, patents, licenses) | Captured in Technology Lock-in and Barriers to Entry |
| Switching costs | Dedicated dimension (Switching Costs) |
| Network effects | Limited applicability in hardware; captured where relevant (EDA ecosystem) |
| Efficient scale | Captured in Market Dominance and Barriers to Entry |
| **Not included** | **Supply Chain Criticality (our proprietary addition)** |

The critical adaptation is the addition of **Supply Chain Criticality** as the highest-weighted dimension (tied with Market Dominance at 20%). This reflects the reality that in the AI supply chain, the most important moat source is often not how large a company is, but how irreplaceable it is. A company can have modest revenue but an enormous moat if it is the sole source of a critical input.

### 2.3 Moat Durability -- The Temporal Dimension

A moat score captures the **current state** of competitive advantage. But moats are dynamic. They can widen, remain stable, or narrow over time. Our framework includes a durability assessment that tracks the trajectory:

- **WIDENING:** The company's advantages are strengthening. Margins are expanding, market share is growing, switching costs are increasing. The competitive gap is becoming harder to close. Example: ASML's moat widens with each new EUV generation because the capital and knowledge required to compete grows exponentially.

- **STABLE:** The company's advantages are holding steady. No significant competitive threats are emerging, and the company is maintaining its position. Financial metrics are consistent. Example: Shin-Etsu Chemical's silicon wafer position has been stable for decades.

- **NARROWING:** The company's advantages are eroding. Competitors are gaining ground, margins are compressing, or technology disruption is creating alternative paths. Example: A memory company facing commoditization as competitors reach comparable process nodes.

### 2.4 How Moats Translate to Financial Outcomes

The ultimate validation of a moat is in financial performance over full business cycles:

| Moat Indicator | Financial Manifestation |
|---|---|
| Strong pricing power | Gross margins >40%, stable or expanding through downturns |
| High switching costs | Revenue retention >90%, low customer churn |
| Technology leadership | R&D leverage (growing revenue faster than R&D spend) |
| Supply chain criticality | Pricing resilience during oversupply periods |
| High barriers to entry | Sustained above-average ROIC (>15%) for 10+ years |
| Market dominance | Market share stability through industry downturns |

A company with a WIDE MOAT should demonstrate:
- Gross margins that are **structurally higher** than industry average
- ROIC consistently above WACC, even in cyclical troughs
- Market share that is **flat or growing** over a 10-year period
- Pricing that is **independent of commodity cycles** (i.e., the company sets prices, not the market)

---

## 3. The Six Moat Dimensions -- Deep Dive

The moat composite score is a weighted sum of six dimensions. Five are qualitative assessments stored in the universe config (`configs/ai_moat_universe.yaml`) and assigned by domain analysts. One (Pricing Power) is computed quantitatively from financial statements by `src/analysis/moat.py`.

```
MOAT_WEIGHTS = {
    "market_dominance":         0.20,   # 20%
    "switching_costs":          0.15,   # 15%
    "technology_lockin":        0.15,   # 15%
    "supply_chain_criticality": 0.20,   # 20%
    "pricing_power":            0.15,   # 15%  (quantitative)
    "barriers_to_entry":        0.15,   # 15%
}
```

Total: 100%

### 3.1 Market Dominance (20% Weight)

#### What It Measures

Market dominance quantifies a company's share and positional strength within its relevant market. A dominant market position, when sustainable, allows a company to set industry standards, influence pricing, and benefit from scale economies that competitors cannot match.

#### Why 20% Weight

Market dominance receives the joint-highest weight because in the AI supply chain, market share concentration is extreme. Many segments are oligopolies or monopolies. In these structures, the dominant player captures outsized economics -- better margins, preferential customer relationships, and the ability to dictate technology roadmaps.

#### How to Assess Market Share and Its Sustainability

**Step 1: Define the relevant market precisely.**

Market definition is critical. ASML's market share is ~100% if you define the market as "EUV lithography systems," but approximately 25-30% if you define it as "all lithography systems" (including DUV). The correct definition for moat purposes is the **narrowest market that the company's customers cannot substitute away from**. For ASML, the relevant market is EUV lithography because customers building leading-edge chips cannot substitute DUV for EUV -- they need EUV to achieve the required transistor densities.

Guidelines for market definition:
- Use the **substitutability test:** Can the customer use a different type of product to achieve the same result? If no, the market is correctly defined.
- Consider **application-specific markets** rather than broad industry categories. "Semiconductor equipment" is too broad; "EUV mask inspection tools" is appropriately specific.
- Account for **geographic segmentation** when relevant. Some markets are truly global (EDA tools), while others have regional dynamics (certain chemical suppliers).

**Step 2: Measure concentration.**

Use standard concentration metrics:

- **Market Share (%):** The company's revenue as a percentage of total market revenue. Sources include Gartner, VLSI Research, Yole Developpement, TechInsights, and company filings.
- **Herfindahl-Hirschman Index (HHI):** Sum of squared market shares of all firms. HHI > 2,500 indicates a highly concentrated market (effectively oligopolistic). HHI > 5,000 suggests monopolistic conditions.
- **CR4 (Four-Firm Concentration Ratio):** Combined market share of the top 4 firms. CR4 > 80% indicates a tight oligopoly.

**Step 3: Assess sustainability.**

A high market share is only a moat if it is durable. Assess:

- Has the company maintained or grown share over the past 5-10 years?
- What would it take for a competitor to reach comparable scale?
- Are there **structural reasons** the market stays concentrated (e.g., astronomical R&D costs, customer lock-in, regulatory barriers)?
- Has the company ever lost share and regained it, or do share losses appear permanent?

#### Scoring Guidelines

| Score Range | Description | Characteristics |
|---|---|---|
| 90-100 | Monopoly or near-monopoly | >80% share in a well-defined market; no viable competitor within 5+ years |
| 75-89 | Dominant leader | 50-80% share; strong #1 position in duopoly or oligopoly |
| 60-74 | Strong position | 30-50% share; solid #1 or #2 position with stable dynamics |
| 45-59 | Competitive but not dominant | 15-30% share; meaningful presence but faces strong competitors |
| 30-44 | Participant | 5-15% share; one of several competitors, no dominant position |
| 0-29 | Minor player | <5% share; limited market influence |

#### AI Supply Chain Examples

- **ASML (100):** 100% monopoly in EUV lithography. No competitor exists or is under development.
- **Lasertec (100):** 100% monopoly in EUV mask inspection. Sole supplier globally.
- **Ajinomoto (100):** ~100% monopoly in ABF substrate film. Every advanced IC substrate uses it.
- **TSMC (95):** ~90% of advanced node (<7nm) foundry production. Samsung is the only alternative and trails by 1-2 process generations.
- **Synopsys (85):** ~33% of EDA market, but effectively a duopoly with Cadence controlling ~65% combined. No new EDA competitor has emerged in 30 years.
- **Murata (85):** ~40% of MLCC market. Largest and most technologically advanced ceramic capacitor maker.
- **Vertiv (70):** #1 in data center thermal management, but with meaningful competition from Schneider Electric and others.

---

### 3.2 Switching Costs (15% Weight)

#### What It Measures

Switching costs quantify the total cost -- financial, operational, temporal, and risk-related -- that a customer would incur by replacing the company's product or service with an alternative. High switching costs create "sticky" customer relationships that persist even when a competitor offers a nominally better or cheaper product.

#### Why 15% Weight

Switching costs are a powerful moat source in the AI supply chain because the cost of failure is catastrophic. When a semiconductor fab qualifies a new chemical supplier and that chemical causes contamination on a $5,000 wafer carrying 50 advanced AI chips, the loss is not just the material cost -- it is the multi-million-dollar production disruption, yield loss investigation, and months of requalification. This asymmetric risk-reward means customers almost never switch from a working supplier.

#### Types of Switching Costs in the AI Supply Chain

**1. Contractual Switching Costs**
- Long-term supply agreements (3-5 year commitments common in chemicals and materials)
- Volume purchase commitments with penalty clauses
- Technology co-development agreements that create mutual dependency
- License agreements with multi-year terms (EDA tools)

**2. Technical Integration Switching Costs**
- **Recipe-based lock-in (Semiconductor Equipment):** When a fab installs a Tokyo Electron coater/developer, engineers spend months or years optimizing process recipes -- the precise combinations of temperatures, pressures, chemical concentrations, spin speeds, and timing sequences that produce the required results. These recipes are specific to that vendor's equipment. Switching to a competitor's tool means recreating all recipes from scratch, which can take 12-24 months and millions of dollars.
- **Design flow integration (EDA):** Chip designers build their entire workflow around a specific EDA vendor's toolchain. Synopsys and Cadence tools are deeply integrated -- synthesis, place-and-route, verification, and sign-off tools form a tightly coupled pipeline. Switching requires retraining engineers, revalidating IP libraries, and often redesigning portions of the chip. A full EDA stack migration at a major design house can cost $50M+ and take 2-3 years.
- **IP library dependency (EDA/ARM):** Designs built on ARM's instruction set architecture or using a vendor's IP cores cannot be migrated to an alternative architecture without a complete redesign. This is not switching cost in the traditional sense -- it is architectural lock-in.

**3. Learning Curve Switching Costs**
- Engineers specialize in specific toolsets over their careers
- Training new engineers on alternative tools requires 6-12 months of productivity loss
- Institutional knowledge accumulates around specific vendors' products
- Process engineers at fabs develop deep expertise on specific equipment platforms

**4. Data and Process Knowledge Lock-in**
- Historical process data tied to specific equipment (decades of yield optimization data)
- Calibration and simulation models tuned to specific tools
- Quality control databases built around specific supplier specifications
- Manufacturing execution systems configured for specific equipment interfaces

**5. Certification and Qualification Costs**
- New chemical suppliers require 6-18 months of qualification at a semiconductor fab
- Material qualification involves extensive testing: purity analysis, particle contamination, process compatibility, reliability testing
- Automotive and aerospace customers require even longer qualification cycles (2-3 years)
- Regulatory re-certification costs for changing critical suppliers

#### Scoring Guidelines

| Score Range | Description | Customer Switching Behavior |
|---|---|---|
| 90-100 | Near-impossible to switch | Switching would halt production; no customer has switched in 10+ years; switching cost exceeds 10x annual spend |
| 75-89 | Extremely difficult | Switching requires 12+ months; involves production risk; very rare occurrences |
| 60-74 | Difficult and costly | Switching takes 6-12 months; requires significant investment; customers resist switching |
| 45-59 | Moderately costly | Switching takes 3-6 months; customers occasionally switch for major price or performance differences |
| 30-44 | Modest switching costs | Switching achievable in weeks to months; customers switch when meaningfully better alternatives exist |
| 0-29 | Low or no switching costs | Products are largely interchangeable; switching occurs freely based on price |

#### AI Supply Chain Examples

- **ASML (100):** Switching is literally impossible -- no alternative EUV system exists. Even if one existed, the recipe migration and requalification would take years.
- **TSMC (100):** Moving a chip design from TSMC to Samsung requires a full mask set redesign ($10M+), process re-characterization, and 12-18 months of yield ramp. Most customers never switch.
- **Synopsys/Cadence (95):** Design flow migration is a multi-year, multi-million-dollar project that no rational company undertakes without extreme provocation.
- **Shin-Etsu Chemical (90):** Silicon wafer supplier qualification at a leading-edge fab takes 12-18 months. Fabs typically maintain 2 qualified suppliers but almost never add a third.
- **JSR Corporation (90):** Photoresist qualification involves thousands of wafer tests. Once qualified, a photoresist formulation remains in use for the lifetime of that process node (3-5 years).

---

### 3.3 Technology Lock-in (15% Weight)

#### What It Measures

Technology lock-in assesses the depth and durability of a company's proprietary technology advantages. This includes patents, trade secrets, proprietary manufacturing processes, accumulated know-how, and the pace of ongoing innovation that keeps competitors from catching up.

#### Why 15% Weight

In the AI supply chain, technology is often the **origin of all other moat dimensions**. ASML's market dominance, switching costs, and supply chain criticality all stem from its technology leadership in EUV lithography. Technology lock-in is therefore a leading indicator -- when technology advantage erodes, other moat dimensions typically follow within a few years.

#### Assessment Framework

**1. Patent Portfolio Analysis**
- Total patent count in relevant technology domains
- Patent citation frequency (highly cited patents indicate foundational technology)
- Geographic coverage (patents filed in US, EU, Japan, Korea, Taiwan, China)
- Patent expiration timeline (are key patents expiring soon?)
- Defensive vs. offensive patent positioning
- Cross-licensing agreements (may indicate mutual dependency)

**2. Trade Secrets and Proprietary Know-How**
- Manufacturing process knowledge that cannot be patented (e.g., exact photoresist formulations)
- Yield optimization data accumulated over decades
- Equipment calibration techniques developed through long engineering cycles
- Customer-specific customizations and process recipes
- Quality control methodologies

**3. R&D Spending as a Moat Indicator**
- R&D as % of revenue: indicates ongoing innovation investment
  - >15%: Heavy investment, typical for technology leaders
  - 10-15%: Solid investment
  - 5-10%: Moderate
  - <5%: Potentially underinvesting; technology position may be at risk
- R&D efficiency: revenue growth per R&D dollar (measures whether R&D translates to competitive advantage)
- Consistency of R&D spending through downturns (companies that cut R&D during recessions may lose technology leadership)

**4. Technology Generation Leadership**
- Is the company the first to market with each new technology generation?
- How long does it take competitors to match each generation?
- Is the gap between leader and follower widening or narrowing?
- Examples:
  - ASML: EUV (2017) --> High-NA EUV (2025) -- competitors are not even attempting to match
  - Tokyo Electron: Each new etch process generation maintains 2-3 year lead
  - TSMC: N3 --> N2 --> A14 roadmap maintains 1-2 year lead over Samsung

**5. Standards Influence and Ecosystem Control**
- Does the company define or influence industry standards?
- ARM: The ARM instruction set architecture is the de facto standard for mobile and increasingly for AI inference processors. Ecosystem of 15M+ developers creates technology lock-in.
- Synopsys/Cadence: Their EDA tool formats (Liberty, LEF/DEF, Verilog/SystemVerilog) are de facto industry standards.
- Standards influence creates a compounding moat: as more companies build on the standard, switching away becomes progressively more costly.

#### Scoring Guidelines

| Score Range | Description | Technology Position |
|---|---|---|
| 90-100 | Defines the state of the art | Sole possessor of critical technology; competitors 5+ years behind; continuous innovation widening the gap |
| 75-89 | Clear technology leader | Leading-edge technology with 2-4 year lead; strong patent portfolio; high R&D investment |
| 60-74 | Technology advantage | Meaningful technology differentiation; 1-2 year lead; solid but not insurmountable |
| 45-59 | Technology parity with nuances | Comparable technology to competitors with some differentiated features |
| 30-44 | Follower position | Using licensed or commodity technology; limited proprietary advantage |
| 0-29 | Technology laggard | Outdated technology; dependent on others' IP; declining innovation |

---

### 3.4 Supply Chain Criticality (20% Weight)

#### What It Measures

Supply chain criticality assesses how essential a company is to the functioning of the AI chip production chain. It answers the question: **"What happens if this company disappears tomorrow?"** The more severe and irreversible the disruption, the higher the score.

#### Why 20% Weight -- The Highest Weight

This is our most distinctive moat dimension and reflects the unique nature of AI supply chain analysis. Traditional moat frameworks focus on customer-facing competitive dynamics. In the AI supply chain, however, the most important competitive advantages often exist **between suppliers** -- in the invisible dependencies, bottleneck positions, and sole-source relationships that determine whether AI chips can be produced at all.

Supply chain criticality receives the joint-highest weight (tied with Market Dominance at 20%) because:

1. **Bottleneck positions create inelastic demand.** When a company is the sole source of a critical input, customers will pay almost any price to maintain supply. This is a moat source that traditional frameworks undervalue.
2. **Supply chain position is extremely durable.** Qualifying a new supplier in semiconductor manufacturing takes years. Building a new factory takes 3-5 years. Developing the underlying technology takes decades. A sole-source position in the semiconductor supply chain is among the most durable competitive advantages in any industry.
3. **AI demand amplifies existing bottlenecks.** The explosion of AI chip demand has exposed supply chain constraints that were previously manageable. Companies sitting at bottleneck positions have seen their pricing power increase dramatically.

#### Bottleneck Identification Methodology

**Step 1: Map the Production Chain**

For each AI chip that reaches a customer, trace every input backward:

```
AI GPU (e.g., NVIDIA H100)
  |-- Design: EDA tools (Synopsys, Cadence) + CPU IP (ARM)
  |-- Fabrication: Foundry (TSMC)
  |     |-- Lithography: Scanner (ASML) + Photoresist (JSR/TOK/Shin-Etsu)
  |     |-- Etch: Etch tools (TEL, Lam Research)
  |     |-- Deposition: CVD/PVD tools (TEL, Applied Materials)
  |     |-- Inspection: Mask inspection (Lasertec), Wafer inspection (KLA)
  |     |-- Testing: ATE (Advantest)
  |     |-- Materials: Silicon wafers (Shin-Etsu, SUMCO), Gases (Linde)
  |     |-- Chemicals: CMP slurries (Entegris), cleaning chemicals
  |-- Packaging: CoWoS (TSMC) using ABF substrate (Ajinomoto film, Ibiden/Shinko substrate)
  |-- Memory: HBM (SK Hynix, Samsung, Micron) stacked with TSVs
  |-- PCB/Substrate: IC substrates (Ibiden, Unimicron)
  |-- Assembly: Server integration with networking (Broadcom, Arista), power (Vertiv, MPWR)
  |-- Connectors: High-speed interconnect (Amphenol)
  |-- Cooling: Thermal management (Vertiv, Nidec)
```

**Step 2: Identify Single/Sole Source Positions**

For each node in the supply chain:
- How many qualified suppliers exist?
- If only 1-2 suppliers: **Critical bottleneck** (score 85-100)
- If 3-4 suppliers: **Important but manageable** (score 60-84)
- If 5+ suppliers: **Commoditized supply** (score below 60)

| Supplier Count | Criticality Level | Supply Risk |
|---|---|---|
| 1 (monopoly) | Critical -- sole source | Production stops if supplier fails |
| 2 (duopoly) | High -- limited alternatives | Severe disruption if one supplier fails |
| 3-4 (oligopoly) | Moderate -- constrained supply | Manageable disruption with lead time |
| 5+ | Low -- competitive supply | Minimal disruption from any single failure |

**Step 3: Apply the Irreplaceability Test**

For each company, ask: "If this company ceased operations today, what would happen?"

- **Immediate halt to AI chip production (Score 95-100):** ASML, Lasertec, Ajinomoto (ABF film). No alternative exists. Production cannot continue.
- **Severe multi-year disruption (Score 85-94):** TSMC, Shin-Etsu, JSR. Alternatives exist but would take years to scale to required quality and volume.
- **Significant disruption requiring months (Score 70-84):** Tokyo Electron, Advantest, Ibiden. Competitors exist but customers would face serious production gaps.
- **Moderate disruption with workarounds (Score 50-69):** Companies where alternatives exist and can be qualified within a reasonable timeframe.
- **Minimal disruption (Score below 50):** Multiple qualified alternatives readily available.

**Step 4: Assess Capacity Constraints**

Capacity constraints reinforce supply chain criticality:
- Is the company operating at or near full capacity?
- How long does it take to add new capacity (months vs. years)?
- Are customers willing to commit to long-term purchase agreements (indicating scarcity)?
- Has the company been able to raise prices without losing volume (indicating inelastic demand)?

#### Critical Path Analysis for AI Chip Production

The **critical path** identifies the sequence of production steps with the longest lead times and fewest alternative suppliers. Any delay on the critical path delays the entire output. The critical path for leading-edge AI chips runs through:

1. **EUV lithography systems** (ASML) -- 18-24 month lead time for new tools
2. **EUV photomasks** (inspection by Lasertec) -- must be defect-free
3. **Advanced node fabrication** (TSMC) -- 3-4 month wafer cycle time
4. **ABF substrates for packaging** (Ajinomoto film, manufactured by Ibiden/Shinko) -- 6-12 month capacity expansion cycle
5. **HBM memory** (SK Hynix/Samsung/Micron) -- constrained by advanced DRAM process capacity
6. **Advanced packaging** (TSMC CoWoS) -- limited capacity, 12+ month expansion lead time

Companies on the critical path receive the highest supply chain criticality scores because delays at their nodes directly gate AI chip output for the entire industry.

#### Scoring Guidelines

| Score Range | Description | Irreplaceability |
|---|---|---|
| 95-100 | Absolute sole source | No alternative exists anywhere in the world; loss would halt AI chip production |
| 85-94 | Near-irreplaceable | Theoretical alternatives exist but would take 3-5+ years to develop |
| 75-84 | Critical with limited alternatives | 1-2 alternatives exist but with inferior capability or insufficient capacity |
| 60-74 | Important supply chain position | Multiple alternatives exist but switching causes meaningful disruption |
| 40-59 | Meaningful but replaceable | Alternatives can be qualified within 6-12 months |
| 0-39 | Commoditized supply position | Many qualified alternatives; substitution is straightforward |

---

### 3.5 Pricing Power (15% Weight) -- Quantitative

#### What It Measures

Pricing power quantifies a company's ability to command premium pricing and maintain or expand margins over time. Unlike the other five dimensions which rely on qualitative assessment, **Pricing Power is computed quantitatively** from financial statements by the `MoatAnalyzer._score_pricing_power()` method in `src/analysis/moat.py`.

#### Why 15% Weight

Pricing power is the **financial manifestation** of all other moat dimensions. A company with strong market dominance, high switching costs, and critical supply chain position should demonstrate that advantage in its margins. If a company scores high on qualitative dimensions but has weak margins, it may indicate that the qualitative assessment is overly optimistic -- or that the moat is not translating into economic returns.

#### Quantitative Scoring Methodology

The pricing power score starts at a base of **50 points** and adds or subtracts based on financial metrics:

```python
score = 50.0  # base score

# Gross Margin Level (primary indicator)
if gross_margin > 40%:   score += 25    # Strong pricing power
elif gross_margin > 25%: score += 15    # Moderate pricing power
elif gross_margin > 15%: score += 5     # Some pricing power

# Operating Margin Level (confirms sustainable pricing power after OpEx)
if operating_margin > 30%:  score += 15   # Very strong
elif operating_margin > 20%: score += 10  # Strong
elif operating_margin > 10%: score += 5   # Moderate

# Margin Trend (directional indicator)
if margin_expansion > 3% (over reporting period): score += 10  # Growing power
if margin_contraction > 3%:                       score -= 10  # Declining power

# Final score clamped to [0, 100]
```

**Maximum possible score:** 50 (base) + 25 (gross margin) + 15 (operating margin) + 10 (trend) = **100**
**Minimum realistic score for a viable company:** ~50 (neutral) -- base score with no significant margin characteristics.

#### Interpretation of Scoring Components

**Gross Margin >40% (+25 points):**
A gross margin exceeding 40% indicates the company is selling products or services where the value to the customer substantially exceeds the cost of production. In the semiconductor supply chain, companies with >40% gross margins typically possess genuine pricing power rooted in technology differentiation or sole-source positions. Examples: ASML (~52%), Synopsys (~80%), Cadence (~89%), KLA (~60%).

**Operating Margin >30% (+15 points):**
An operating margin exceeding 30% confirms that pricing power is not being consumed by excessive operating costs. It indicates the company can maintain premium pricing while running efficient operations. This threshold separates companies with genuine moats from companies with high gross margins but bloated cost structures.

**Margin Expansion Trend >3% (+10 points):**
Expanding margins indicate **growing** pricing power. This is the most bullish moat signal because it means the company is strengthening its competitive position over time. The 3% threshold filters out normal fluctuation. Consistent margin expansion through a full business cycle (3-5 years) is the strongest indicator.

**Margin Contraction Trend >3% (-10 points):**
Contracting margins are a warning signal. If a company's qualitative moat scores are high but margins are declining, it may indicate that competitive dynamics are shifting, pricing pressure is emerging, or costs are rising faster than the company can pass them through.

#### Complementary Qualitative Assessment

While the quantitative score is computed automatically, analysts should also consider:

- **Price increase history vs. volume growth:** Can the company raise prices without losing volume? This is the purest test of pricing power. Companies like ASML regularly raise equipment prices with each new generation and face zero customer defection.
- **Customer willingness-to-pay analysis:** How much would customers pay if prices increased further? For sole-source suppliers, customers have essentially unlimited willingness to pay relative to the value of their production output.
- **Cost pass-through ability during inflation:** When input costs rise, can the company pass them to customers? Companies with strong moats pass through cost increases fully and promptly. Companies with weak moats absorb cost increases, compressing margins.
- **Pricing consistency through downturns:** The true test of pricing power is during an industry downturn. Companies with WIDE MOATs maintain pricing; companies with weaker moats must discount.

---

### 3.6 Barriers to Entry (15% Weight)

#### What It Measures

Barriers to entry quantify how difficult it would be for a new competitor to enter the market and achieve comparable scale, technology, and customer relationships. Higher barriers mean the incumbents' positions are safer from new competitive threats.

#### Why 15% Weight

Barriers to entry are the **forward-looking guarantee** that today's moat will persist. A company can have strong current metrics across all other dimensions, but if barriers to entry are low, those advantages can be competed away. Conversely, extremely high barriers to entry mean that even if a company's current execution is imperfect, its position is unlikely to be challenged.

#### Types of Barriers in the AI Supply Chain

**1. Capital Requirements**

The financial cost of entering a market. In the AI supply chain, capital barriers range from significant to astronomical:

| Market Segment | Estimated Entry Cost | Timeline to Competitive Scale |
|---|---|---|
| EUV lithography (ASML equivalent) | $50B+ over 20+ years | Not achievable; no one has succeeded |
| Leading-edge foundry (TSMC equivalent) | $20B+ per fab | 5-10 years; Intel and Samsung still trail |
| Semiconductor equipment (major player) | $5-15B including R&D | 10-15 years minimum |
| EDA tools (Synopsys/Cadence equivalent) | $5-10B in R&D | 15-20 years; no one has succeeded in 30 years |
| Specialty chemicals (major supplier) | $1-5B | 5-10 years including qualification |
| IC substrate manufacturing | $2-5B per factory | 3-5 years |
| Data center infrastructure | $0.5-2B | 2-3 years (lowest barriers in our universe) |

**2. Regulatory Barriers**

- **Export controls:** US/Dutch/Japanese export restrictions on advanced semiconductor equipment create regulatory barriers that prevent Chinese competitors from accessing critical technologies and limit the addressable market to allied nations. These controls effectively create a regulated oligopoly.
- **Environmental permits:** Chemical and materials companies face stringent environmental regulations. Building a new photoresist manufacturing facility requires years of environmental review.
- **Quality certifications:** ISO 9001, IATF 16949 (automotive), AS9100 (aerospace), and industry-specific certifications take years to obtain and maintain.

**3. Talent Barriers**

- Specialized semiconductor engineering talent is scarce globally
- Deep domain expertise in areas like EUV lithography, photoresist chemistry, or ATE design requires decades to develop
- Key talent is concentrated in specific geographic clusters (Hsinchu for foundry, Veldhoven for lithography, Kanagawa for chemicals)
- Non-compete agreements and trade secret protections limit talent mobility

**4. Network Effects**

Network effects are limited in hardware supply chains but strong in specific segments:
- **EDA ecosystem:** Synopsys and Cadence benefit from strong ecosystem effects. Third-party IP providers validate against their tools, foundries characterize process design kits (PDKs) for their flows, and universities train students on their platforms. A new EDA entrant would need to recreate this entire ecosystem.
- **ARM ecosystem:** The ARM architecture benefits from a massive developer ecosystem (15M+ developers), extensive software library compatibility, and thousands of validated IP cores. A new instruction set architecture would require rebuilding this ecosystem from scratch.
- **Foundry ecosystem:** TSMC's ecosystem of IP partners, design services firms, and validated design flows creates network effects that reinforce customer lock-in.

**5. Scale Economies and Learning Curves**

- Semiconductor manufacturing has steep learning curves. Each new process node requires trillions of transistors of cumulative production to optimize yields. Late entrants must climb these learning curves while incumbents are already profitable.
- Equipment companies benefit from installed base scale: more deployed systems mean more process data, better field support infrastructure, and more efficient spare parts logistics.
- Chemical companies benefit from volume scale: larger production volumes enable finer quality control and lower per-unit costs.

**6. Brand and Reputation Barriers**

- In the semiconductor supply chain, "brand" means qualification status. Being an approved supplier at TSMC, Samsung, or Intel is a brand of quality that took years to earn.
- Reputation for reliability is critical: semiconductor manufacturers are extremely risk-averse in their supply chain decisions.
- Track record through multiple technology generations and business cycles creates a trust barrier that new entrants cannot shortcut.

#### Scoring Guidelines

| Score Range | Description | New Entrant Viability |
|---|---|---|
| 90-100 | Impenetrable | No new entrant has succeeded in 20+ years; requires $10B+ and decades of development |
| 75-89 | Extremely high barriers | New entry theoretically possible but would require $5B+ and 10+ years |
| 60-74 | High barriers | Established competitors could enter with $1-5B over 5-10 years |
| 45-59 | Moderate barriers | New entrants possible with significant investment and 2-5 year timeline |
| 30-44 | Low-moderate barriers | Barriers exist but well-funded startups can overcome them in 1-3 years |
| 0-29 | Low barriers | Market is accessible with limited capital; frequent new entrants |

---

## 4. Moat Scoring Methodology

### 4.1 Score Assignment Process

Each company in the universe is scored on all six dimensions:

**Qualitative Dimensions (5 of 6):**
Scores for `market_dominance`, `switching_costs`, `technology_lockin`, `supply_chain_criticality`, and `barriers_to_entry` are assigned by domain analysts and stored in `configs/ai_moat_universe.yaml`. These scores should be reviewed and updated at least quarterly, or whenever a material event occurs (e.g., a new competitor emerges, a company announces a technology breakthrough, or regulatory changes alter the landscape).

**Quantitative Dimension (1 of 6):**
The `pricing_power` score is computed automatically by `MoatAnalyzer._score_pricing_power()` from financial statements (gross margin, operating margin, margin trend). This score updates whenever new financial data becomes available.

### 4.2 Weighted Composite Calculation

The composite moat score is computed as:

```
Composite = (market_dominance     x 0.20)
          + (switching_costs      x 0.15)
          + (technology_lockin    x 0.15)
          + (supply_chain_crit    x 0.20)
          + (pricing_power        x 0.15)
          + (barriers_to_entry    x 0.15)
```

All dimension scores are on a 0-100 scale. The composite is therefore also on a 0-100 scale.

### 4.3 Classification Thresholds

| Composite Score | Classification | Meaning | Investment Implication |
|---|---|---|---|
| **80-100** | **WIDE MOAT** | Durable, multi-dimensional competitive advantage that is extremely difficult to erode | High conviction for long-term positions; willing to pay premium valuation; hold through downturns |
| **60-79** | **NARROW MOAT** | Meaningful competitive advantage in at least 2-3 dimensions; defensible but with some vulnerability | Solid long-term holdings; valuation discipline important; monitor for moat erosion signals |
| **40-59** | **WEAK MOAT** | Some competitive advantages but significant vulnerability in multiple dimensions | Shorter-term holding period; stricter valuation requirements; active monitoring for deterioration |
| **0-39** | **NO MOAT** | No meaningful sustainable competitive advantage | Trade on cycle timing and valuation only; avoid as long-term core holdings |

### 4.4 Classification Distribution in Our Universe

Given that our universe is specifically curated to include companies with critical positions in the AI supply chain, the distribution skews heavily toward higher moat classifications:

- **WIDE MOAT:** Expected for companies like ASML, TSMC, Lasertec, Ajinomoto, Synopsys, Cadence, Shin-Etsu
- **NARROW MOAT:** Expected for most other semiconductor equipment, specialty chemical, and packaging companies
- **WEAK MOAT:** Expected for some electronic component and power/cooling companies where competitive dynamics are more fragmented
- **NO MOAT:** Rare in our curated universe; would indicate a company added for AI exposure tracking rather than competitive advantage

### 4.5 Integration with Composite Stock Score

The moat score does not directly feed into the platform's composite stock score (which covers Fundamental, Valuation, Technical, Risk, and Sentiment). Instead, it serves as a **strategic filter and conviction modifier**:

- **WIDE MOAT + high composite score:** Highest conviction position. Both near-term attractiveness and long-term defensibility.
- **WIDE MOAT + low composite score:** Potential opportunity. Strong business temporarily out of favor. Investigate whether the low score reflects cyclical headwinds (buying opportunity) or structural problems (possible moat erosion).
- **NO/WEAK MOAT + high composite score:** Caution warranted. The stock may be attractive now but lacks defensibility for long-term holding.
- **NO/WEAK MOAT + low composite score:** Avoid. No near-term catalyst and no long-term competitive advantage.

---

## 5. Porter's Five Forces Analysis

Porter's Five Forces is a complementary framework that assesses the overall competitive intensity and profit potential of an industry segment. While our moat scoring focuses on individual company advantages, Five Forces analysis examines the **industry structure** that either supports or undermines those advantages.

### 5.1 Framework Overview

For each of the 8 supply chain categories in our universe, conduct a Five Forces assessment:

### 5.2 Force 1: Threat of New Entrants

**Key Questions:**
- What is the minimum capital investment required to enter this segment?
- How long would it take a new entrant to achieve competitive scale?
- Are there regulatory barriers to entry (export controls, environmental permits)?
- Do incumbents have learning curve advantages that new entrants cannot quickly replicate?
- Is there access to distribution channels and customer relationships?

**Application by Segment:**

| Segment | Threat Level | Rationale |
|---|---|---|
| Semiconductor Equipment | Very Low | $5-50B entry cost; 10-20 year development; no successful new entrant in decades |
| Specialty Chemicals | Low | Qualification barriers; 5-10 year timeline; specialized manufacturing |
| Advanced Packaging | Low-Medium | $2-5B per factory; capacity takes 3-5 years; but new capacity is being built |
| Electronic Components | Medium | Mature technology; capital-intensive but scalable; Chinese competitors emerging |
| EDA/IP | Very Low | No new EDA company has reached meaningful scale in 30 years; ecosystem lock-in |
| Networking | Medium | Fast-moving technology; well-funded incumbents; but startups do emerge |
| Power/Cooling | Medium-High | Lower capital barriers; established industrial competition; innovation cycle shorter |
| Foundry/Memory | Very Low | $20B+ per leading-edge fab; 5-10 year yield learning curve; enormous scale required |

### 5.3 Force 2: Bargaining Power of Suppliers

**Key Questions:**
- How concentrated is the supply base for critical inputs?
- Are there substitute inputs available?
- How important is the supplier's product to the company's output?
- Can the company backward-integrate (make the input itself)?

**AI Supply Chain Nuance:** In the AI supply chain, many of the companies in our universe ARE the powerful suppliers. This creates a recursive dynamic: ASML is a powerful supplier to TSMC, which is a powerful supplier to NVIDIA. Understanding where each company sits in the power hierarchy is essential.

### 5.4 Force 3: Bargaining Power of Buyers

**Key Questions:**
- How concentrated are the buyers?
- How critical is the product to the buyer's operations?
- Can buyers backward-integrate?
- Are buyers price-sensitive or performance-sensitive?

**AI Supply Chain Nuance:** Buyer concentration is extreme. TSMC, Samsung, and Intel collectively account for the vast majority of semiconductor equipment and materials purchases. This concentration gives buyers some leverage, but this is offset by the buyers' extreme dependence on specific suppliers. TSMC cannot credibly threaten to stop buying from ASML.

### 5.5 Force 4: Threat of Substitutes

**Key Questions:**
- Are there alternative technologies that could replace this company's products?
- What is the price-performance trajectory of potential substitutes?
- What are the switching costs to a substitute technology?
- Are customers investing in or exploring substitutes?

**Application by Segment:**

| Segment | Substitution Threat | Example Substitutes |
|---|---|---|
| EUV Lithography | Very Low | No alternative to EUV for <7nm; nanoimprint lithography only for specific applications |
| Silicon Wafers | Very Low | No alternative substrate for mainstream logic/memory |
| Photoresists | Very Low | Each resist is formulated for specific wavelengths; no generic substitute |
| ABF Substrates | Low | Glass substrates are emerging but are 5-10 years from mainstream |
| MLCCs | Low | Some shift to silicon capacitors at extreme performance levels |
| EDA Tools | Very Low | Open-source EDA exists but is not competitive for leading-edge design |
| HBM Memory | Low | Processing-in-memory and alternative memory architectures are very early stage |
| Data Center Cooling | Medium | Liquid cooling is replacing air cooling (structural shift, not substitution threat) |

### 5.6 Force 5: Competitive Rivalry Intensity

**Key Questions:**
- How many competitors operate in this segment?
- Is the industry growing or stagnating?
- Are competitors roughly equal in size, or is there a clear hierarchy?
- Is competition based on price or on performance/technology?
- How high are exit barriers?

**AI Supply Chain Nuance:** Competitive rivalry is paradoxically low in many AI supply chain segments despite high profitability. This is because the segments are either monopolies (ASML, Lasertec, Ajinomoto), duopolies (Synopsys/Cadence, Shin-Etsu/SUMCO), or tight oligopolies (semiconductor equipment, specialty chemicals). The combination of high barriers to entry and few competitors results in structured, technology-driven competition rather than destructive price wars.

---

## 6. Competitive Landscape Mapping

### 6.1 Industry Structure Analysis by Segment

For each of the 8 categories in our universe, maintain a structured competitive landscape map:

```
Segment: [Category Name]
Market Size: $[X]B (YYYY estimate)
Growth Rate: [X]% CAGR (YYYY-YYYY forecast)
Structure: Monopoly / Duopoly / Oligopoly / Fragmented

Key Players (ranked by market share):
  1. [Company A] - [X]% share - [strengths/weaknesses]
  2. [Company B] - [X]% share - [strengths/weaknesses]
  3. [Company C] - [X]% share - [strengths/weaknesses]

Emerging Competitors:
  - [Company D] - [country] - [technology approach] - [timeline to relevance]

Consolidation Events (recent):
  - [YYYY]: [Acquirer] acquired [Target] for $[X]B

Technology Roadmap:
  - Current generation: [Description]
  - Next generation: [Description] - [expected timeline]
  - Generation after: [Description] - [expected timeline]
```

### 6.2 Competitor Identification and Positioning

For each company in our universe, identify:

1. **Direct competitors** -- companies offering the same product category to the same customers
2. **Indirect competitors** -- companies offering alternative technologies or approaches
3. **Potential competitors** -- companies that could enter the market based on adjacent capabilities
4. **Government-backed competitors** -- state-subsidized efforts to replicate capabilities (especially relevant for Chinese semiconductor industry development)

### 6.3 Market Share Tracking Methodology

**Data Sources:**
- Industry research firms: Gartner, VLSI Research, Yole Developpement, TechInsights, TrendForce, Omdia
- Company annual reports and investor presentations (self-reported market share)
- Trade association data (SEMI, SIA)
- Government trade data for import/export analysis

**Update Frequency:**
- Annual comprehensive update from industry research
- Quarterly review based on company earnings reports
- Ad-hoc updates on material events (M&A, plant closures, major contract wins/losses)

### 6.4 Consolidation Trend Analysis

The AI supply chain has seen significant consolidation over the past decade. Track:

- Recent and pending M&A transactions
- Antitrust review outcomes (especially relevant for Synopsys/Ansys type combinations)
- Vertical integration moves (companies expanding up or down the supply chain)
- Private equity activity (buyouts, carve-outs, re-IPOs)
- Impact of consolidation on competitive dynamics (does the acquisition strengthen the acquirer's moat?)

### 6.5 Emerging Competitor Monitoring

Maintain a watch list of potential disruptors:

- **Chinese semiconductor equipment makers:** NAURA Technology, Advanced Micro-Fabrication Equipment (AMEC), Shanghai Micro Electronics Equipment (SMEE). Monitor technology progress and government funding.
- **Open-source EDA:** Monitor CHIPS Alliance, OpenROAD, and other open-source EDA projects. Assess whether they can become viable for production-quality chip design.
- **Alternative memory technologies:** Monitor MRAM, ReRAM, and other non-volatile memory technologies that could eventually compete with DRAM/HBM.
- **Alternative packaging technologies:** Monitor glass substrates, chiplet standards (UCIe), and other approaches that could alter the advanced packaging landscape.
- **Startup activity:** Track semiconductor-focused startups and their funding rounds as early indicators of potential competitive threats.

---

## 7. Moat Durability Assessment

### 7.1 Assessment Categories

Every moat score should be accompanied by a durability assessment:

| Assessment | Code | Description |
|---|---|---|
| **Widening** | WIDENING | Competitive advantages are strengthening over time |
| **Stable** | STABLE | Competitive advantages are holding steady |
| **Narrowing** | NARROWING | Competitive advantages are eroding |

### 7.2 Widening Moat Indicators

A moat is widening when multiple of the following signals are present:

- **Financial signals:**
  - Gross margins expanding over trailing 3-year period
  - Operating margins expanding over trailing 3-year period
  - ROIC consistently above WACC and trending upward
  - Revenue per employee increasing (operating leverage)
  - Price increases exceeding inflation consistently

- **Market signals:**
  - Market share increasing or holding in a growing market
  - Customer concentration decreasing (diversifying customer base while retaining pricing)
  - Average contract length increasing
  - Backlog or order book growing faster than revenue
  - New customer acquisition accelerating

- **Technology signals:**
  - R&D output (patents, new products) increasing
  - Technology gap vs. closest competitor widening
  - Customers adopting newest generation products faster
  - Competitive product launches failing to gain traction

- **Structural signals:**
  - Industry consolidation reducing competitor count
  - Regulatory changes favoring incumbents (e.g., export controls)
  - Capacity expansion outpacing competitors
  - Supply agreements lengthening (customers locking in access)

### 7.3 Narrowing Moat Indicators

A moat is narrowing when multiple of the following signals are present:

- **Financial signals:**
  - Gross margin compression over trailing 3-year period
  - Pricing pressure (volume up but revenue/unit down)
  - R&D spending increasing as % of revenue without corresponding revenue growth (running harder to stay in place)
  - Customer concentration increasing (losing smaller customers)

- **Market signals:**
  - Market share declining over 3+ years
  - Competitor gaining share with inferior but cheaper products
  - Customers publicly evaluating or qualifying alternative suppliers
  - Average selling prices declining faster than cost reductions

- **Technology signals:**
  - Competitor achieving technology parity on latest generation
  - Open-source alternatives gaining traction in the ecosystem
  - Customer-designed alternatives emerging (vertical integration)
  - Standards shifting away from the company's proprietary approach

- **Structural signals:**
  - Government subsidies enabling competitors (e.g., China semiconductor subsidies)
  - Regulatory changes undermining the moat (forced licensing, antitrust action)
  - New entrants receiving significant funding and making progress
  - Geopolitical forces creating alternative supply chains

### 7.4 Technology Disruption Risk by Segment

| Segment | Disruption Risk | Primary Disruption Vectors |
|---|---|---|
| Semiconductor Equipment | Very Low (10yr) | Fundamentally new manufacturing paradigms (molecular assembly, etc.) -- theoretical |
| Specialty Chemicals | Low | Alternative chemistries; but qualification barriers slow disruption |
| Advanced Packaging | Medium | Glass substrates, chiplet standardization, new bonding technologies |
| Electronic Components | Medium | Silicon capacitors, integrated passives, printed electronics |
| EDA/IP | Low | Open-source EDA, AI-assisted chip design, no-code chip design platforms |
| Networking | Medium-High | Optical interconnects, silicon photonics, new protocols |
| Power/Cooling | Medium | Immersion cooling, novel thermal materials, on-chip power delivery |
| Foundry/Memory | Low | Alternative computing paradigms (quantum, neuromorphic) -- distant |

### 7.5 Regulatory Risk to Moats

**Antitrust Risk:**
- EDA duopoly (Synopsys/Cadence) could face regulatory scrutiny, especially with Synopsys's pending acquisitions expanding its scope
- Equipment monopolies (ASML, Lasertec) could theoretically face forced licensing demands from governments
- Foundry concentration (TSMC) is a geopolitical concern driving government-mandated diversification

**Export Control Risk:**
- US/Dutch/Japanese export controls on semiconductor equipment create a regulatory moat for allied-nation companies but could be relaxed if geopolitical tensions ease
- Export controls also limit the addressable market for equipment companies (cannot sell to Chinese fabs above certain technology thresholds)
- Companies dependent on Chinese revenue face particular regulatory risk

**Forced Localization Risk:**
- Government programs (CHIPS Act, EU Chips Act, China Big Fund) are subsidizing domestic alternatives to foreign-dominated supply chain segments
- Success of these programs could narrow moats for currently dominant foreign suppliers
- Timeline for localization to become competitively meaningful varies: 5-10 years for chemicals, 10-20+ years for equipment

### 7.6 Geopolitical Moat Risk

- **Taiwan concentration risk:** TSMC's dominance creates a geopolitical risk for the entire AI supply chain. A disruption to Taiwan-based production would be catastrophic. This is both a moat (no alternative exists) and a risk (the single point of failure is in a geopolitically sensitive location).
- **Japan concentration risk:** Many critical bottleneck positions (Tokyo Electron, Shin-Etsu, JSR, Lasertec, Advantest, Ajinomoto, Ibiden, Murata) are held by Japanese companies. A natural disaster, policy change, or other disruption to Japan's industrial base would severely impact AI chip production.
- **Technology sovereignty drives:** Multiple governments are investing to reduce dependency on concentrated supply chains. While this will not eliminate moats in the near term, it creates a long-term narrowing pressure.

---

## 8. AI Supply Chain-Specific Moat Patterns

Each segment of the AI supply chain exhibits characteristic moat patterns. Understanding these patterns helps analysts quickly assess new companies and identify whether a moat is structural or temporary.

### 8.1 Semiconductor Equipment: Extreme Specialization Creates Natural Monopolies

**Pattern:** Each critical process step in semiconductor manufacturing (lithography, etch, deposition, inspection, testing, cleaning, dicing) requires such specialized technology that only 1-3 companies worldwide can build the required tools. The R&D cost to develop a new generation of equipment is $1-10B, making competition economically irrational in small markets.

**Moat Archetype:** Technology lock-in + Capital barriers = Natural monopoly
**Typical Scores:** Market Dominance 80-100, Switching Costs 80-100, Barriers to Entry 85-100
**Durability:** Very high. No new semiconductor equipment company has reached significant scale in 20+ years.
**Key Risk:** Government-subsidized competitors (primarily Chinese) could eventually match current-generation technology for domestic use.

### 8.2 Specialty Chemicals and Materials: Qualification Barriers Create Sticky Relationships

**Pattern:** Semiconductor chemicals (photoresists, CMP slurries, gases, silicon wafers) must meet purity specifications measured in parts per billion or parts per trillion. Qualifying a new chemical supplier at a leading-edge fab requires extensive testing over 6-18 months, during which the fab risks contamination and yield loss. Once qualified, suppliers remain in place for the lifetime of the process node (3-5 years). The relationship is further cemented by co-development agreements where the supplier optimizes their formulation for the specific customer's process.

**Moat Archetype:** Switching costs + Quality barriers = Sticky customer relationships
**Typical Scores:** Switching Costs 80-95, Supply Chain Criticality 75-95, Barriers to Entry 75-90
**Durability:** High for established suppliers. New entrants face a "chicken and egg" problem: they cannot prove quality without customer adoption, but customers will not adopt without proven quality.
**Key Risk:** Government pressure for supply chain diversification could force customers to qualify alternative suppliers.

### 8.3 Advanced Packaging: Capacity Constraints Create Temporary Pricing Power

**Pattern:** Advanced packaging technologies (CoWoS, InFO, HBM stacking) require specialized substrates (ABF film from Ajinomoto, built into substrates by Ibiden/Shinko) and limited manufacturing capacity. The explosion of AI chip demand has created severe capacity shortages, giving packaging companies pricing power. However, this is partly a demand-driven moat rather than a structural one -- as capacity expands, pricing power may moderate.

**Moat Archetype:** Capacity scarcity + Material monopoly (ABF) = Near-term pricing power
**Typical Scores:** Supply Chain Criticality 80-100 (for ABF), Market Dominance 75-100
**Durability:** Medium-high for ABF substrate materials (structural monopoly); Medium for packaging capacity (capacity is being expanded). Glass substrate alternatives are emerging as a potential long-term disruption vector.
**Key Risk:** Capacity expansion reduces scarcity premium; glass substrates could reduce ABF dependency in 5-10 years.

### 8.4 EDA and Design IP: Ecosystem Lock-in and Network Effects

**Pattern:** EDA tools (Synopsys, Cadence) and design IP (ARM) benefit from the strongest network effects in the hardware supply chain. The EDA ecosystem includes not just the core tools but thousands of IP blocks, process design kits (PDKs) from foundries, verification methodologies, and a trained workforce. Switching EDA vendors is so disruptive that it is almost never done for strategic reasons -- only acquisition (one company buying its competitor's customers) meaningfully shifts share.

**Moat Archetype:** Ecosystem lock-in + Network effects + Training lock-in = Duopoly fortress
**Typical Scores:** Switching Costs 90-95, Technology Lock-in 90-95, Barriers to Entry 90-95
**Durability:** Extremely high. The Synopsys/Cadence duopoly has been stable for 25+ years. ARM's architecture dominance is similarly entrenched.
**Key Risk:** AI-assisted chip design tools could theoretically reduce design complexity and lower barriers to EDA competition. RISC-V is a long-term architectural alternative to ARM but has not yet achieved comparable ecosystem breadth.

### 8.5 Foundry: Astronomical CapEx as the Ultimate Barrier

**Pattern:** Building a leading-edge semiconductor fab costs $20B+ and takes 3-5 years. Achieving competitive yields requires trillions of transistors of cumulative production experience. Only three companies worldwide can fabricate at the leading edge (TSMC, Samsung, Intel), and TSMC leads by 1-2 process generations. The CapEx barrier is so extreme that even Intel -- with $50B+ in investment -- has struggled to close the gap.

**Moat Archetype:** CapEx barrier + Yield learning curve + Technology lead = Near-monopoly
**Typical Scores:** Market Dominance 90-95, Switching Costs 95-100, Barriers to Entry 95-100
**Durability:** Very high for the leading-edge position. TSMC's cumulative advantage in yield learning, customer ecosystem, and technology roadmap execution creates a compounding moat.
**Key Risk:** Geopolitical risk (Taiwan). TSMC is building fabs in Arizona, Japan, and Germany to mitigate this risk, but the leading-edge capacity will remain concentrated in Taiwan for the foreseeable future.

### 8.6 Memory (HBM): Scale Economies and Technology Roadmap Execution

**Pattern:** HBM (High Bandwidth Memory) manufacturing requires advanced DRAM process technology combined with TSV (Through-Silicon Via) stacking. Only three companies produce DRAM at competitive scale (Samsung, SK Hynix, Micron), and SK Hynix has led in HBM execution. The moat comes from the combination of process technology expertise, manufacturing scale, and the tight co-development relationship with GPU designers (especially NVIDIA).

**Moat Archetype:** Scale economies + Technology execution + Customer co-design = Oligopoly with differentiated positions
**Typical Scores:** Market Dominance 70-85, Barriers to Entry 85-90, Supply Chain Criticality 75-90
**Durability:** High for the DRAM oligopoly; Medium for HBM leadership within the oligopoly (SK Hynix leads today, but Samsung and Micron are investing heavily to catch up).
**Key Risk:** HBM leadership position within the oligopoly can shift between generations. Alternative memory technologies (e.g., processing-in-memory) could reduce HBM demand long-term, though no viable alternative is near commercial scale.

### 8.7 Networking and Interconnect: Protocol Standards and Performance Leadership

**Pattern:** AI data center networking requires ultra-high-bandwidth, low-latency connectivity. Companies like Broadcom (switching ASICs), Arista (network operating systems), and Amphenol (connectors/cables) benefit from performance leadership and customer integration. Moats here are narrower than in equipment or materials because technology cycles are faster and competition is more dynamic.

**Moat Archetype:** Performance leadership + Customer integration = Technology-driven competitive advantage
**Typical Scores:** Market Dominance 65-80, Technology Lock-in 65-85, Switching Costs 65-85
**Durability:** Medium. Networking technology evolves rapidly, and new protocols or architectures can shift competitive dynamics within a few years. However, the customer integration and software ecosystem create meaningful switching costs.
**Key Risk:** Silicon photonics, new networking protocols, and hyperscaler custom silicon (Google, Amazon, Meta designing their own networking chips) could disrupt incumbents.

### 8.8 Power and Cooling: Infrastructure Bottleneck with Lower Barriers

**Pattern:** AI data centers consume enormous power and generate enormous heat. Power delivery (Vertiv, Monolithic Power) and thermal management (Vertiv, Nidec) companies benefit from the AI infrastructure buildout. However, barriers to entry are lower than in other segments, competition is more fragmented, and technology differentiation is less extreme.

**Moat Archetype:** Scale + Customer relationships + Growing market = Competitive advantage driven by execution
**Typical Scores:** Market Dominance 65-75, Switching Costs 65-75, Barriers to Entry 65-75
**Durability:** Medium. These companies benefit from the AI buildout but face more competition than companies in other supply chain segments. Liquid cooling and immersion cooling represent both a growth opportunity and a competitive dynamic shift.
**Key Risk:** Lower barriers to entry mean new competitors can emerge more quickly. Hyperscaler vertical integration (designing their own power delivery or cooling solutions) is a risk.

---

## 9. Red Flags for Moat Erosion

Monitor the following signals continuously. Multiple red flags occurring simultaneously warrant a downgrade of the moat score and durability assessment.

### 9.1 Financial Red Flags

| Signal | Severity | What It Indicates |
|---|---|---|
| Market share declining for 3+ consecutive years | High | Competitive advantage is failing to retain customers |
| Gross margin compressing despite revenue growth | High | Pricing power is eroding; company is buying revenue with lower prices |
| R&D spending increasing as % of revenue without revenue acceleration | Medium | Company is running harder to stay in place; competitors are closing the gap |
| Customer concentration increasing | Medium | Losing smaller customers who have more alternatives; dependency risk rising |
| Backlog declining while industry grows | High | Customers are choosing alternatives or deferring purchases |

### 9.2 Competitive Red Flags

| Signal | Severity | What It Indicates |
|---|---|---|
| Customer publicly qualifying an alternative supplier | High | Direct signal that the moat is being tested |
| Government subsidies enabling a new competitor | Medium | Long-term threat; government-backed competitors can sustain losses |
| Open-source alternatives gaining real production adoption | High | Technology moat is being commoditized |
| Adjacent company entering via acquisition | Medium | A well-funded competitor is acquiring capabilities to compete |
| Former employees founding a competitor | Low-Medium | Knowledge transfer; but execution is uncertain |

### 9.3 Technology Red Flags

| Signal | Severity | What It Indicates |
|---|---|---|
| Competitor achieving technology parity on latest generation | High | Technology lock-in is failing |
| Technology standard shifting away from company's approach | High | Ecosystem moat being undermined |
| Customer investing in in-house alternative technology | Medium | Vertical integration threat; customer attempting to bypass supplier |
| Academic breakthrough enabling radically different approach | Low | Disruptive potential, but commercialization timeline is typically 10+ years |

### 9.4 Structural Red Flags

| Signal | Severity | What It Indicates |
|---|---|---|
| Regulatory change undermining a key moat source | High | Government action can rapidly alter competitive dynamics |
| Forced licensing or IP sharing mandates | High | Technology moat being forcibly diluted |
| Export control relaxation allowing new competitors access | Medium | Regulatory moat being narrowed |
| Industry standard becoming open where it was proprietary | High | Ecosystem lock-in being dissolved |
| Customer consortium forming to develop alternative | High | Collective action to reduce dependency on the company |

---

## 10. Running the Analysis

### 10.1 Using the MoatAnalyzer Class

The moat scoring engine is implemented in `src/analysis/moat.py` as the `MoatAnalyzer` class.

**Score a single company:**

```python
from src.analysis.moat import MoatAnalyzer

analyzer = MoatAnalyzer()

# Score with qualitative overrides from the universe config
result = analyzer.score_moat(
    ticker="8035.T",
    moat_overrides={
        "market_dominance": 85,
        "switching_costs": 90,
        "technology_lockin": 85,
        "supply_chain_criticality": 90,
        "barriers_to_entry": 90,
    }
)

print(result)
# {
#   "ticker": "8035.T",
#   "composite_moat_score": 87.3,
#   "moat_classification": "WIDE MOAT",
#   "dimension_scores": {
#       "market_dominance": 85.0,
#       "switching_costs": 90.0,
#       "technology_lockin": 85.0,
#       "supply_chain_criticality": 90.0,
#       "pricing_power": 82.5,
#       "barriers_to_entry": 90.0
#   },
#   "weights": {...}
# }
```

**Compare multiple companies:**

```python
companies = [
    {"ticker": "ASML", "market_dominance": 100, "switching_costs": 100,
     "technology_lockin": 100, "supply_chain_criticality": 100, "barriers_to_entry": 100},
    {"ticker": "8035.T", "market_dominance": 85, "switching_costs": 90,
     "technology_lockin": 85, "supply_chain_criticality": 90, "barriers_to_entry": 90},
    {"ticker": "LRCX", "market_dominance": 80, "switching_costs": 85,
     "technology_lockin": 80, "supply_chain_criticality": 85, "barriers_to_entry": 85},
]

df = analyzer.compare_moats(companies)
print(df)
```

### 10.2 Using the AI Universe Scanner

The universe scanner (`scripts/ai_universe_scanner.py`) can scan all companies in the config and produce a ranked overview:

```bash
# Scan all companies
python scripts/ai_universe_scanner.py

# Scan a specific category
python scripts/ai_universe_scanner.py --category semiconductor_equipment

# Show top N companies by moat score
python scripts/ai_universe_scanner.py --top 20
```

### 10.3 Updating Qualitative Scores

When updating qualitative scores in `configs/ai_moat_universe.yaml`:

1. Document the rationale for each score change
2. Review all six dimensions for internal consistency (a company should not have 95 switching costs but 40 market dominance -- the switching costs score implies meaningful market position)
3. Compare scores against peer companies in the same category for relative reasonableness
4. Update the moat description text to reflect current assessment
5. Record the date of the update

### 10.4 Review Cadence

| Review Type | Frequency | Scope |
|---|---|---|
| Full universe review | Quarterly | All companies, all dimensions, all scores |
| Category deep dive | Monthly (rotating) | One category per month, full Five Forces and landscape analysis |
| Event-driven review | As needed | Triggered by earnings surprises, M&A, regulatory changes, technology breakthroughs |
| Moat durability assessment | Semi-annually | All companies, durability trajectory assessment |

---

## 11. Output Format and Interpretation

### 11.1 Standard Output Format

Every moat analysis should produce the following structured output:

```
=================================================================
MOAT ANALYSIS: [Company Name] ([Ticker])
=================================================================

1. COMPOSITE MOAT SCORE: [XX.X] / 100
2. CLASSIFICATION: [WIDE MOAT / NARROW MOAT / WEAK MOAT / NO MOAT]

3. DIMENSION SCORES:
   Market Dominance (20%):         [XX] / 100  |  [Brief justification]
   Switching Costs (15%):          [XX] / 100  |  [Brief justification]
   Technology Lock-in (15%):       [XX] / 100  |  [Brief justification]
   Supply Chain Criticality (20%): [XX] / 100  |  [Brief justification]
   Pricing Power (15%):            [XX] / 100  |  [Quantitative: GM=XX%, OM=XX%]
   Barriers to Entry (15%):        [XX] / 100  |  [Brief justification]

4. MOAT DURABILITY: [WIDENING / STABLE / NARROWING]
   Rationale: [2-3 sentences explaining the trajectory]

5. KEY COMPETITIVE ADVANTAGES (ranked by importance):
   1. [Advantage #1]
   2. [Advantage #2]
   3. [Advantage #3]

6. KEY COMPETITIVE RISKS (ranked by probability x impact):
   1. [Risk #1]
   2. [Risk #2]
   3. [Risk #3]

7. MOAT TREND: [IMPROVING / STABLE / DECLINING]
   [1-2 sentences on direction over trailing 12 months]
=================================================================
```

### 11.2 Interpretation Guide

**Composite Moat Score:**
- This is the primary summary metric. It answers: "How strong is this company's competitive moat right now?"
- Range: 0-100. Higher is stronger.
- Compare within categories (semiconductor equipment companies against each other) rather than across categories (equipment vs. chemicals).

**Classification:**
- This is the categorical label derived from the composite score.
- WIDE MOAT (80+): Suitable for long-term core holdings with high conviction.
- NARROW MOAT (60-79): Suitable for holdings with moderate conviction and active monitoring.
- WEAK MOAT (40-59): Requires strong valuation discipline; shorter holding period.
- NO MOAT (<40): Not suitable for long-term strategic positions.

**Dimension Scores:**
- Use these to understand WHERE the moat comes from. A company with a WIDE MOAT driven primarily by Supply Chain Criticality has a different risk profile than one driven by Technology Lock-in.
- Look for consistency across dimensions. Large discrepancies (e.g., 95 market dominance but 40 pricing power) warrant investigation.

**Moat Durability:**
- This answers: "Is the moat getting stronger or weaker over time?"
- WIDENING: Increases conviction; the investment thesis is strengthening.
- STABLE: Maintains conviction; monitor for changes.
- NARROWING: Decreases conviction; investigate causes and consider position sizing reduction.

**Key Competitive Advantages and Risks:**
- These provide the qualitative context behind the numerical scores.
- Advantages should be specific and verifiable (not generic statements like "strong technology").
- Risks should include both probability and potential impact assessments.

**Moat Trend:**
- This is the short-term directional indicator. While Moat Durability assesses the structural trajectory, Moat Trend captures recent momentum.
- IMPROVING: Recent events or data points suggest the moat is strengthening.
- STABLE: No material change in recent period.
- DECLINING: Recent events or data points suggest the moat is weakening.

---

## Appendix A -- Moat Dimension Scoring Rubrics

### Quick Reference Scoring Table

| Score | Market Dominance | Switching Costs | Technology Lock-in | Supply Chain Criticality | Pricing Power | Barriers to Entry |
|---|---|---|---|---|---|---|
| **90-100** | Monopoly (>80% share) | Switching nearly impossible | Sole possessor of critical tech | Sole source; no alternative exists | GM>40% + OM>30% + expansion | $10B+ and 20yr to replicate |
| **75-89** | Dominant leader (50-80%) | Switching takes 12+ months | 2-4 year technology lead | Near-irreplaceable; 3-5yr alternative | GM>40% + OM>20% | $5B+ and 10yr to replicate |
| **60-74** | Strong #1 or #2 (30-50%) | Switching takes 6-12 months | Meaningful differentiation | Limited alternatives; significant disruption | GM>25% + OM>20% | $1-5B and 5-10yr |
| **45-59** | Competitive (15-30%) | Switching takes 3-6 months | Technology parity with nuances | Multiple alternatives; moderate disruption | GM>25% + OM>10% | $0.5-1B and 2-5yr |
| **30-44** | Participant (5-15%) | Switching in weeks-months | Follower position | Readily replaceable | GM<25% or OM<10% | Well-funded startups can enter |
| **0-29** | Minor player (<5%) | Low or no switching costs | Technology laggard | Commoditized supply | Weak margins, declining | Low capital, frequent entrants |

---

## Appendix B -- Universe Coverage by Category

The AI moat universe config (`configs/ai_moat_universe.yaml`) tracks companies across 8 categories:

| Category | Description | Companies Tracked | Key Bottleneck Players |
|---|---|---|---|
| `semiconductor_equipment` | Machines that fabricate AI chips | 9 | ASML, Tokyo Electron, Lasertec, Advantest, KLA |
| `chemicals_materials` | Essential chemicals and materials | 8 | Shin-Etsu, JSR, SUMCO, Entegris |
| `packaging_substrates` | Advanced packaging components | 4 | Ajinomoto (ABF film), Ibiden, Shinko Electric |
| `electronic_components` | AI server components | 4 | Murata, TDK, Hamamatsu Photonics |
| `eda_design` | Chip design software and IP | 3 | Synopsys, Cadence, ARM |
| `networking` | Data center connectivity | 3 | Broadcom, Arista, Amphenol |
| `power_cooling` | Data center power and thermal | 2 | Vertiv, Monolithic Power |
| `foundry_memory` | Chip fabrication and memory | 3 | TSMC, SK Hynix, Micron |

**Total: 36+ companies currently tracked** (universe is growing as new bottleneck positions are identified).

Each company entry in the config includes:
- `ticker`: Primary exchange ticker
- `adr`: US ADR ticker (if available)
- `country`: Country of domicile
- `moat`: Text description of the competitive moat
- `ai_exposure_pct`: Estimated percentage of revenue linked to AI
- `market_dominance`: Qualitative score (0-100)
- `switching_costs`: Qualitative score (0-100)
- `technology_lockin`: Qualitative score (0-100)
- `supply_chain_criticality`: Qualitative score (0-100)
- `barriers_to_entry`: Qualitative score (0-100)

---

## Appendix C -- Data Sources and Update Cadence

### Qualitative Score Data Sources

| Data Need | Primary Sources | Secondary Sources |
|---|---|---|
| Market share data | Gartner, VLSI Research, TrendForce, Yole | Company filings, SEMI reports |
| Competitive landscape | Company 10-K/20-F filings, investor presentations | Industry conferences (SEMICON), trade press |
| Technology assessment | Patent databases (USPTO, EPO, WIPO), technical papers | R&D spending analysis, product roadmaps |
| Supply chain mapping | Company filings (customer/supplier disclosures), industry analysis | Trade data, customs records |
| Regulatory environment | Government publications, legal filings | Industry association (SIA, SEMI) reports |
| Switching cost assessment | Customer interviews (where available), industry expert consultations | Case studies of supplier changes, qualification timelines |

### Quantitative Score Data Sources

| Metric | Source in Platform | Update Frequency |
|---|---|---|
| Gross margin | `FundamentalsClient.get_key_ratios()` via yfinance/SimFin | Quarterly (after earnings) |
| Operating margin | `FundamentalsClient.get_key_ratios()` via yfinance/SimFin | Quarterly (after earnings) |
| Margin trend | `FundamentalsClient.get_income_statement()` (multi-year comparison) | Quarterly |
| Revenue growth | `FundamentalsClient` via yfinance/SimFin | Quarterly |

### Update Cadence Summary

| Item | Frequency | Responsible |
|---|---|---|
| Pricing Power scores (quantitative) | Automatic on each run | `MoatAnalyzer._score_pricing_power()` |
| Qualitative dimension scores | Quarterly review | Domain analyst |
| Universe company additions/removals | As needed | Domain analyst |
| Full SOP review | Annually | Team lead |
| Moat durability assessments | Semi-annually | Domain analyst |
| Competitive landscape maps | Monthly (rotating category) | Domain analyst |

---

## Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-02-09 | FE-Analyst Team | Initial version |
