# SOP-002: Financial Statement Analysis

**Version:** 1.0
**Last Updated:** 2026-02-09
**Owner:** FE-Analyst Platform
**Status:** Active

---

## 1. Purpose

Financial statements are the foundation of fundamental analysis. This SOP codifies how expert analysts systematically dissect income statements, balance sheets, and cash flow statements to produce the quantitative inputs that feed the FE-Analyst composite scoring system (0-100). Every ratio, threshold, and scoring decision documented here maps directly to the platform's `FundamentalAnalyzer` class and its three sub-scores: **Financial Health (0-6)**, **Growth Profile (0-4)**, and **Valuation (0-6)**.

This SOP serves as the authoritative reference for both human analysts and AI agents performing financial statement analysis on the platform.

---

## 2. Scope

This SOP covers the analysis of:
- **Income Statements** (annual and quarterly)
- **Balance Sheets** (annual and quarterly)
- **Cash Flow Statements** (annual and quarterly)
- **Supplementary disclosures** (footnotes, MD&A, segment data)
- **Ratio calculation and interpretation**
- **Multi-year trend analysis**
- **Peer benchmarking**
- **Red flag detection**
- **Industry-specific adjustments** (with emphasis on the AI supply chain universe tracked in `configs/ai_moat_universe.yaml`)

This SOP does NOT cover technical analysis (see SOP-003), sentiment analysis (see SOP-004), or DCF/intrinsic value modeling (see SOP-005). However, the financial statement outputs documented here are direct inputs to those processes.

---

## 3. Data Sources and Retrieval

### 3.1 Primary Data Sources

The platform retrieves financial statements through the `FundamentalsClient` class (`src/data_sources/fundamentals.py`) and `SECFilingsClient` class (`src/data_sources/sec_filings.py`):

| Source | Data Type | Python Interface | Cache TTL |
|--------|-----------|------------------|-----------|
| **yfinance** | Income statement, balance sheet, cash flow, key ratios, company profile | `yf.Ticker(ticker).income_stmt`, `.balance_sheet`, `.cashflow`, `.info` | 168 hours (1 week) |
| **SEC EDGAR** | 10-K, 10-Q, 8-K filings, XBRL structured data | `edgartools` via `SECFilingsClient` | 720 hours (30 days) |
| **SimFin** | Bulk quarterly/annual financial statements | `simfin` package | 168 hours (1 week) |
| **Finnhub** | Company peers, reported financials, revenue breakdown | `finnhub-python` via API key | 168 hours (1 week) |

### 3.2 Data Retrieval Methods

```python
# Annual financial statements
client = FundamentalsClient()
income_stmt = client.get_income_statement(ticker, quarterly=False)
balance_sheet = client.get_balance_sheet(ticker, quarterly=False)
cash_flow = client.get_cash_flow(ticker, quarterly=False)
ratios = client.get_key_ratios(ticker)
profile = client.get_company_profile(ticker)

# Quarterly financial statements
income_q = client.get_income_statement(ticker, quarterly=True)
balance_q = client.get_balance_sheet(ticker, quarterly=True)
cash_flow_q = client.get_cash_flow(ticker, quarterly=True)

# SEC filings (10-K for annual, 10-Q for quarterly)
sec = SECFilingsClient()
filings = sec.get_recent_filings(ticker, form_type="10-K", count=5)
xbrl_data = sec.get_financials_xbrl(ticker)
```

### 3.3 Data Quality Hierarchy

When data conflicts exist between sources, use this priority order:
1. **SEC EDGAR XBRL** -- authoritative, as-reported, audited
2. **SimFin** -- standardized from SEC filings, high quality
3. **Finnhub reported financials** -- sourced from SEC filings
4. **yfinance** -- convenient but occasionally incomplete or inconsistent

Always cross-validate critical ratios (ROE, D/E, current ratio) against at least two sources before scoring.

---

## 4. Pre-Analysis Checklist

Before beginning any financial statement analysis, complete every item below. Skipping this checklist leads to incorrect comparisons, misscored ratios, and flawed conclusions.

- [ ] **Identify reporting currency** -- USD, JPY, EUR, TWD, KRW. For Japanese companies in the AI universe (e.g., 8035.T Tokyo Electron, 6920.T Lasertec), statements are in JPY. Convert to USD only for peer comparison, never for standalone analysis.
- [ ] **Confirm fiscal year-end** -- Most Japanese companies end March 31; most US companies end December 31 or have irregular FYEs (e.g., Apple ends September). This affects YoY comparisons.
- [ ] **Check for restatements or accounting changes** -- Search 8-K filings for restatement disclosures. Look for "restated" or "revised" in footnotes. If found, use restated figures and note the restatement in the analysis.
- [ ] **Identify reporting standard** -- US GAAP vs IFRS. Critical differences:
  - IFRS allows revaluation of PP&E (US GAAP does not)
  - R&D capitalization rules differ (IFRS capitalizes development costs meeting criteria; US GAAP expenses all R&D except software)
  - Inventory: LIFO is permitted under US GAAP but prohibited under IFRS
  - Lease classification differs under IFRS 16 vs ASC 842
  - Revenue recognition: IFRS 15 vs ASC 606 (largely converged but differences in application)
- [ ] **Note material acquisitions/divestitures** -- Any M&A in the analysis period makes YoY comparisons unreliable. Decompose organic vs inorganic growth. Check 8-K filings for acquisition disclosures.
- [ ] **Determine peer group** -- Use `FundamentalsClient.get_peers(ticker)` via Finnhub as a starting point, then refine. Peers must match on:
  - Same industry segment (not just sector)
  - Similar market cap range (within 0.5x-2x)
  - Similar geographic exposure
  - Similar stage of business lifecycle
- [ ] **Verify data freshness** -- Check the filing date of the most recent 10-K/10-Q. If the most recent annual filing is more than 14 months old, flag the analysis as stale and supplement with quarterly data.
- [ ] **Check auditor opinion** -- Look for qualified opinions, emphasis-of-matter paragraphs, or going-concern opinions. An auditor change within the past 2 years is a yellow flag.

---

## 5. Income Statement Analysis

### 5.1 Revenue Analysis

Revenue is the top line and the starting point for all analysis. Analyze in this order:

**5.1.1 Revenue Recognition Policies**
- Review the revenue recognition footnote in the 10-K (ASC 606 for US GAAP, IFRS 15 for IFRS)
- Identify the five-step model application: (1) identify contract, (2) identify performance obligations, (3) determine transaction price, (4) allocate to obligations, (5) recognize when satisfied
- For semiconductor equipment companies (Tokyo Electron, ASML, Lam Research): revenue is typically recognized upon customer acceptance/installation, which can create lumpy quarterly patterns
- For software/SaaS companies: distinguish between point-in-time recognition and over-time recognition
- Flag any changes in revenue recognition policy as a red flag

**5.1.2 Organic vs Inorganic Growth**
- Separate revenue growth attributable to acquisitions from core business growth
- Formula: `Organic Growth = Total Revenue Growth - Acquired Revenue Contribution`
- Inorganic growth above 50% of total growth in any year warrants deeper investigation into integration risk
- For serial acquirers, track organic growth rate over 3+ years to assess true business momentum

**5.1.3 Revenue Concentration Risk**
- Extract top customer data from 10-K Item 1A (Risk Factors) or segment disclosures
- Flag if any single customer represents >10% of revenue
- Flag if top 5 customers represent >50% of revenue
- For AI supply chain: TSMC derives significant revenue from Apple and NVIDIA; semiconductor equipment companies depend on a small number of foundries and memory fabs

**5.1.4 Segment-Level Revenue Breakdown**
- Analyze revenue by business segment (available in 10-K segment footnote)
- Calculate growth rates per segment to identify accelerating vs decelerating businesses
- For diversified companies, compute what percentage of total revenue comes from high-growth segments

**5.1.5 Geographic Revenue Mix**
- Extract geographic revenue breakdown from segment disclosures
- Critical for AI supply chain analysis -- key geographies: Japan, Taiwan, US, Netherlands, South Korea
- Assess FX exposure: if >30% of revenue is in a foreign currency, FX movements materially impact reported results
- Note: Japanese companies reporting in JPY with significant USD/EUR revenue face translation effects that can obscure operational trends

**5.1.6 Recurring vs One-Time Revenue**
- Separate recurring revenue (subscriptions, service contracts, maintenance) from one-time revenue (product sales, licensing)
- Higher recurring revenue percentage = more predictable business = higher quality revenue
- For semiconductor equipment companies: service/maintenance revenue (typically 20-35% of total) carries higher margins and provides stability through cyclical downturns

**5.1.7 Backlog and Book-to-Bill**
- For equipment and capital goods companies, extract backlog data from MD&A or earnings calls
- Book-to-Bill Ratio = New Orders / Revenue in the period
- B/B > 1.0 indicates growing demand pipeline
- B/B < 0.9 sustained for 2+ quarters signals potential revenue decline
- Critical leading indicator for semiconductor equipment companies (Tokyo Electron, ASML, Applied Materials)

### 5.2 Margin Analysis

Margins reveal pricing power, operational efficiency, and competitive position. Analyze all margin levels.

**5.2.1 Gross Margin**
```
Gross Margin = (Revenue - COGS) / Revenue
```
- Track 3-5 year trajectory; direction matters more than absolute level
- Compare vs peers (use `ValuationAnalyzer.comparable_valuation()` for peer data)
- Industry benchmarks:
  - Semiconductor equipment: 45-55% (high-end toolmakers)
  - Specialty chemicals: 30-45%
  - Software/EDA: 75-90%
  - Foundries (TSMC): 50-55%
  - Memory (cyclical): 20-50% depending on cycle
- Gross margin expanding while revenue grows = pricing power (strong moat signal)
- Gross margin declining while revenue grows = volume-driven growth at lower prices (weaker position)

**5.2.2 Operating Margin (EBIT Margin)**
```
Operating Margin = Operating Income / Revenue
= (Gross Profit - SGA - R&D - D&A) / Revenue
```
- Decompose changes into components:
  - R&D as % of revenue: increasing = investing in future; decreasing = milking current products
  - SGA as % of revenue: should decline with scale (operating leverage)
  - D&A as % of revenue: reflects capital intensity
- Scoring thresholds for moat assessment (used in `MoatAnalyzer._score_pricing_power()`):
  - Operating margin > 30%: strong pricing power (+15 to moat score)
  - Operating margin 20-30%: moderate pricing power (+10)
  - Operating margin 10-20%: adequate (+5)
  - Operating margin < 10%: weak pricing power

**5.2.3 EBITDA Margin**
```
EBITDA Margin = (Operating Income + D&A) / Revenue
```
- Use EBITDA margin for capital-intensive businesses (foundries, memory, equipment)
- Strips out the effect of different depreciation policies across peers
- More comparable across companies with different asset ages
- EBITDA margin > operating margin gap reveals capital intensity

**5.2.4 Net Margin**
```
Net Margin = Net Income / Revenue
```
- After-tax profitability including financing effects
- Compare net margin to operating margin to assess tax efficiency and leverage impact
- Available directly via `ratios.get("profit_margin")` from yfinance

**5.2.5 Margin Expansion/Compression Drivers**
For every margin that changed >200bps YoY, identify the root cause:
- Input cost changes (raw materials, energy)
- Product mix shift (higher/lower margin products)
- Pricing actions (ASP changes)
- Operating leverage (fixed cost absorption on higher volume)
- Currency effects (FX translation gains/losses)
- One-time items (restructuring charges, impairments)

### 5.3 Earnings Quality Assessment

Not all earnings are created equal. Assess quality before trusting reported numbers.

**5.3.1 Cash Earnings vs Accrual Earnings**
```
Earnings Quality Ratio = Operating Cash Flow / Net Income
```
- Target: > 1.0 (cash earnings exceed accrual earnings)
- Ratio consistently below 0.8 = earnings quality concern
- Ratio above 1.3 = very high quality (company generates more cash than it reports as income)
- This is the single most important earnings quality metric

**5.3.2 Non-Recurring Items Identification**
Scan the income statement and footnotes for:
- Restructuring charges (should be truly one-time; recurring "restructuring" is a red flag)
- Asset impairments (goodwill, intangibles, PP&E)
- Legal settlements (positive or negative)
- Gain/loss on asset sales
- Insurance recoveries
- Discontinued operations
- Calculate adjusted earnings by removing genuinely non-recurring items
- If "non-recurring" charges appear in 3+ consecutive years, they are recurring costs disguised as one-time items

**5.3.3 Stock-Based Compensation (SBC) Impact**
- SBC is a real economic cost even though it is a non-cash charge
- Calculate SBC as % of operating income: if >20%, earnings are materially inflated vs cash reality
- Calculate SBC as % of revenue: track the trend
- Adjust EPS by adding back the dilution effect to assess true per-share earnings
- Especially relevant for tech companies with heavy SBC (EDA companies like Synopsys, Cadence)

**5.3.4 Tax Rate Sustainability**
- Compare effective tax rate (ETR) to statutory rate
- ETR significantly below statutory rate may indicate:
  - Tax credits (R&D credits, foreign tax credits) -- sustainable
  - Tax loss carryforwards -- temporary, will normalize
  - Aggressive tax structures -- regulatory risk
  - One-time tax benefits -- not sustainable
- For Japanese companies: statutory corporate tax rate ~30%; check for special deductions
- For Irish/Dutch-domiciled companies (e.g., ASML via Netherlands): potentially lower ETR

**5.3.5 Deferred Revenue Changes**
- Increasing deferred revenue = customers paying in advance = leading indicator of future revenue
- Decreasing deferred revenue = recognizing previously collected cash = revenue may decelerate
- Particularly important for subscription/service businesses
- For semiconductor equipment: deferred revenue often relates to installation obligations

---

## 6. Balance Sheet Analysis

### 6.1 Liquidity Assessment

Liquidity determines whether a company can meet its short-term obligations and fund operations.

**6.1.1 Current Ratio**
```
Current Ratio = Current Assets / Current Liabilities
```
- This is a direct input to the Financial Health score in `FundamentalAnalyzer._assess_financial_health()`
- **Scoring thresholds (from `src/analysis/fundamental.py`):**

| Current Ratio | Health Score Points | Assessment |
|---------------|-------------------|------------|
| > 1.5 | +2 | Strong liquidity |
| 1.0 - 1.5 | +1 | Adequate liquidity |
| < 1.0 | 0 | Weak liquidity -- potential distress signal |

- Available via `ratios.get("current_ratio")` from `FundamentalsClient.get_key_ratios()`
- Context matters: some industries operate successfully with low current ratios (e.g., subscription businesses with deferred revenue in current liabilities)

**6.1.2 Quick Ratio (Acid Test)**
```
Quick Ratio = (Current Assets - Inventory) / Current Liabilities
```
- More conservative than current ratio; excludes inventory which may not be easily liquidated
- Available via `ratios.get("quick_ratio")` from yfinance
- Target: > 1.0
- Critical for companies with large inventory positions (semiconductor companies, chemical companies)
- If quick ratio is significantly lower than current ratio, investigate inventory quality

**6.1.3 Cash and Equivalents Trend**
- Absolute cash position matters less than the trajectory
- Declining cash over 3+ quarters with no corresponding investment = cash burn concern
- For Japanese companies: traditionally hold large cash positions (may appear inefficient but reflects cultural conservatism)

**6.1.4 Working Capital Metrics**

| Metric | Formula | What It Tells You |
|--------|---------|-------------------|
| **DSO** (Days Sales Outstanding) | (Accounts Receivable / Revenue) x 365 | Cash collection efficiency. Rising DSO = slowing collections or deteriorating customer quality |
| **DIO** (Days Inventory Outstanding) | (Inventory / COGS) x 365 | Inventory management. Rising DIO = potential overstock or demand slowdown |
| **DPO** (Days Payable Outstanding) | (Accounts Payable / COGS) x 365 | Supplier payment terms. Rising DPO = better terms or stretching payments |
| **Cash Conversion Cycle** | DSO + DIO - DPO | Full cycle from cash outflow to cash inflow. Lower = more efficient |

- Compare CCC to peers; a company with a shorter CCC has a structural working capital advantage
- For semiconductor equipment: DIO can be very high (12-18 months) due to long manufacturing cycles
- DSO increasing faster than revenue growth is a major red flag (potential revenue quality issues)

### 6.2 Leverage Analysis

Leverage determines financial risk and the company's ability to survive downturns.

**6.2.1 Debt-to-Equity Ratio**
```
D/E = Total Debt / Total Shareholders' Equity
```
- This is a direct input to the Financial Health score in `FundamentalAnalyzer._assess_financial_health()`
- **Scoring thresholds (from `src/analysis/fundamental.py`):**

| D/E Ratio | Health Score Points | Assessment |
|-----------|-------------------|------------|
| < 50 (i.e., < 0.5x) | +2 | Low leverage, strong balance sheet |
| 50 - 100 (0.5x - 1.0x) | +1 | Moderate leverage |
| > 100 (> 1.0x) | 0 | High leverage -- increased financial risk |

- **IMPORTANT**: The code uses `ratios.get("debt_to_equity")` from yfinance, which returns the ratio as a percentage (e.g., 50 means 0.5x). The scoring thresholds in `fundamental.py` use these percentage values.
- Available via `ratios.get("debt_to_equity")` from `FundamentalsClient.get_key_ratios()`
- Industry-specific context:
  - Tech companies: D/E < 30% is common (low capital needs)
  - Semiconductor fabs (TSMC): D/E 30-50% is normal (heavy CapEx)
  - Utilities and REITs: D/E > 100% is standard and appropriate

**6.2.2 Net Debt Position**
```
Net Debt = Total Debt - Cash and Equivalents
```
- Negative net debt (more cash than debt) = extremely strong position
- Many Japanese companies in the AI supply chain have negative net debt (net cash positions)
- ASML, for example, maintains significant net cash
- Net cash positions provide flexibility for R&D investment and opportunistic M&A

**6.2.3 Interest Coverage Ratio**
```
Interest Coverage = EBIT / Interest Expense
```
- Measures ability to service debt
- Thresholds:
  - > 8x: very comfortable
  - 4-8x: adequate
  - 2-4x: tight, watch carefully
  - < 2x: distress territory
- For companies with minimal debt, this ratio may be extremely high or undefined (which is fine)

**6.2.4 Debt Maturity Schedule**
- Extract from the debt footnote in the 10-K or 20-F
- Identify near-term maturities (next 12-24 months) vs long-term
- Near-term maturities > available cash + undrawn credit facilities = refinancing risk
- In rising rate environments, track what percentage of debt is floating rate

**6.2.5 Off-Balance Sheet Obligations**
- Operating lease obligations (post-ASC 842/IFRS 16, most are now on-balance sheet, but check transition)
- Purchase commitments (especially for semiconductor equipment: long-lead-time purchase obligations)
- Guarantees and contingent liabilities
- Variable Interest Entities (VIEs) -- particularly relevant for Chinese companies
- Calculate total adjusted debt including off-balance sheet items for a complete leverage picture

### 6.3 Asset Quality

**6.3.1 Goodwill and Intangibles**
```
Intangible Intensity = (Goodwill + Intangibles) / Total Assets
```
- Intangible intensity > 40% = significant acquisition risk / write-down risk
- Goodwill approaching total equity level = severe risk (an impairment could wipe out equity)
- Check the annual goodwill impairment test disclosures -- if the "fair value" of reporting units is only marginally above carrying value, impairment is likely in a downturn
- For EDA companies (Synopsys, Cadence): high intangible levels are typical due to IP-driven acquisitions

**6.3.2 PP&E Age and Adequacy**
```
Asset Age Ratio = Accumulated Depreciation / Gross PP&E
```
- Ratio > 0.7 = aging asset base, may need significant CapEx refresh
- Ratio < 0.3 = recently invested, modern asset base
- For capital-intensive businesses (foundries, equipment manufacturers), this signals future CapEx needs
- Compare CapEx as % of depreciation: ratio < 1.0 sustained = underinvestment

**6.3.3 Inventory Composition**
- Break down inventory into: raw materials, work-in-progress (WIP), finished goods
- Rising finished goods inventory relative to revenue = potential demand weakness
- Rising WIP for equipment companies may indicate production ramp (positive signal)
- Check for inventory write-downs in the footnotes -- frequency and magnitude matter
- For semiconductor companies: inventory can become obsolete rapidly with technology transitions

**6.3.4 Accounts Receivable Quality**
- AR aging information (if available in footnotes)
- Allowance for doubtful accounts as % of gross AR: increasing = deteriorating customer credit
- Concentration: if disclosed, check whether AR is concentrated in a few large customers
- Compare AR growth to revenue growth: AR growing faster = potential revenue recognition issue

### 6.4 Equity Analysis

**6.4.1 Share Count Trends**
- Track diluted share count over 3-5 years
- Sources of dilution: stock-based compensation, convertible debt, warrants, secondary offerings
- Sources of reduction: share buyback programs, retirement of treasury stock
- Net dilution > 2% per year sustained = meaningful value erosion for shareholders
- Net buyback reducing shares > 2% per year = returning value to shareholders (if purchased at reasonable prices)

**6.4.2 Treasury Stock Activity**
- Large treasury stock balance = accumulated buybacks (positive signal if bought below intrinsic value)
- Companies buying back stock at premium valuations destroy value
- Check buyback execution: compare average purchase price to current trading range

**6.4.3 Retained Earnings Trajectory**
- Consistently growing retained earnings = profitable operations funding growth internally
- Declining retained earnings = paying out more than earning, or sustained losses
- Negative retained earnings = accumulated deficit, typically for early-stage or turnaround situations

**6.4.4 Accumulated Other Comprehensive Income (AOCI)**
- AOCI captures unrealized gains/losses from:
  - Foreign currency translation adjustments (critical for Japanese companies with global operations)
  - Unrealized gains/losses on available-for-sale securities
  - Pension adjustments
  - Cash flow hedge adjustments
- Large negative AOCI from FX translation can significantly impact book value for international companies
- For Japanese companies: yen weakening creates large positive FX translation adjustments when foreign subsidiary results are converted back to JPY

---

## 7. Cash Flow Statement Analysis

The cash flow statement is the most important financial statement for assessing business quality. Earnings can be manipulated; cash flow is much harder to fake.

### 7.1 Operating Cash Flow (OCF)

**7.1.1 OCF vs Net Income Reconciliation**
```
Earnings Quality Ratio = OCF / Net Income
```
- This is the primary quality of earnings check
- Target ratio: > 1.0 consistently
- If OCF / NI < 0.8 for 2+ consecutive years, investigate deeply
- The reconciliation section (indirect method) reveals exactly where cash and accruals diverge:
  - Large depreciation add-back = capital-intensive business (normal)
  - Large working capital consumption = growth-related (acceptable) or operational issue (concerning)
  - Large stock-based compensation add-back = significant non-cash earnings component

**7.1.2 Working Capital Changes**
- Positive working capital contribution = cash generation (releasing cash from operations)
- Negative working capital contribution = cash consumption (investing cash into operations)
- For growing companies, moderate working capital consumption is normal
- Sudden, large working capital swings warrant investigation:
  - Large AR increase = possible aggressive revenue recognition
  - Large inventory build = possible demand miss or production ramp
  - Large AP decrease = possible supplier tightening terms (credit risk signal)

**7.1.3 Depreciation and Amortization Add-Backs**
- D&A should be roughly aligned with maintenance CapEx over time
- If D&A significantly exceeds CapEx for multiple years, the company may be underinvesting
- If CapEx significantly exceeds D&A, the company is expanding its asset base (growth investing)

**7.1.4 Deferred Revenue Changes**
- Increasing deferred revenue contributes positively to OCF and signals future revenue
- Decreasing deferred revenue = recognizing prior-period cash = OCF may decline going forward
- Critical for subscription/SaaS business models
- For semiconductor equipment: advance payments on orders show up as deferred revenue

**7.1.5 Tax Payment Timing**
- Compare income tax paid (cash flow statement) to income tax expense (income statement)
- Significant divergence may indicate tax deferrals, credits, or one-time tax events
- Declining cash taxes while income tax expense rises = building deferred tax liabilities (future cash tax burden)

### 7.2 Investing Cash Flow

**7.2.1 Capital Expenditure Analysis**
```
CapEx Intensity = Capital Expenditure / Revenue
```
- Track CapEx intensity over 3-5 years to assess investment cycle
- Industry benchmarks:
  - Semiconductor foundries (TSMC): 30-50% of revenue
  - Semiconductor equipment: 3-8% of revenue (asset-light)
  - EDA/software: 2-5% of revenue
  - Specialty chemicals: 8-15% of revenue

**7.2.2 Maintenance CapEx vs Growth CapEx**
- This distinction is rarely disclosed directly; estimate it:
  - Maintenance CapEx approximation: D&A expense (minimum to maintain existing capacity)
  - Growth CapEx = Total CapEx - Maintenance CapEx
- Growth CapEx is value-creating if ROIC > WACC
- Companies spending primarily on maintenance CapEx are in harvest mode

**7.2.3 Free Cash Flow Calculation**
```
Free Cash Flow (FCF) = Operating Cash Flow - Capital Expenditure
```
- FCF is the primary input to the DCF valuation model in `ValuationAnalyzer.dcf_valuation()`
- The platform retrieves FCF from yfinance: `cf.loc["Free Cash Flow"]`
- FCF should be positive and growing for a healthy, mature business
- Negative FCF is acceptable for high-growth companies investing heavily (e.g., TSMC expanding capacity), but must be funded sustainably

**7.2.4 Acquisition Spending**
- Track total cash spent on acquisitions over the past 5 years
- Compare acquisition spending to organic CapEx: companies that grow primarily through acquisition face integration risk
- Check whether acquired companies are delivering the expected synergies (compare post-acquisition segment performance)
- For serial acquirers, calculate return on invested capital including goodwill

**7.2.5 R&D Capitalization**
- Under US GAAP, most R&D is expensed (except certain software development costs)
- Under IFRS, development costs meeting specific criteria are capitalized
- Capitalized R&D on the balance sheet must be amortized, creating a non-cash charge
- Compare total R&D spend (expensed + capitalized) to revenue for a complete picture of innovation investment

### 7.3 Financing Cash Flow

**7.3.1 Dividend Sustainability**
```
Dividend Payout Ratio = Dividends Paid / Net Income
FCF Payout Ratio = Dividends Paid / Free Cash Flow
```
- Payout ratio > 100% = paying dividends from debt or reserves (unsustainable)
- FCF coverage of dividends > 2x = very safe
- Available via `ratios.get("payout_ratio")` and `ratios.get("dividend_yield")` from yfinance
- For Japanese companies: historically low payout ratios (30-40%) but trending upward due to governance reforms

**7.3.2 Share Repurchase Assessment**
- Compare buyback amount to FCF: if buybacks are funded by debt, they may be value-destructive
- Compare average buyback price to intrinsic value estimate:
  - Buying below intrinsic value = accretive to remaining shareholders
  - Buying above intrinsic value = value destruction
- Net shareholder yield = (Dividends + Net Buybacks) / Market Cap

**7.3.3 Debt Activity**
- Net debt issuance = new borrowings - debt repayments
- Positive net issuance = increasing leverage
- Negative net issuance = deleveraging
- Compare debt issuance to use of proceeds: debt for CapEx/growth is acceptable; debt for buybacks at high valuations is concerning

---

## 8. Ratio Analysis Framework

### 8.1 Profitability Ratios

These ratios feed directly into the scoring system via `FundamentalAnalyzer._assess_financial_health()`.

| Ratio | Formula | Strong | Adequate | Weak | Score Points |
|-------|---------|--------|----------|------|-------------|
| **ROE** | Net Income / Shareholders' Equity | > 15% | 8-15% | < 8% | +2 / +1 / 0 |
| **ROA** | Net Income / Total Assets | > 10% | 5-10% | < 5% | Supplementary |
| **ROIC** | NOPAT / Invested Capital | > WACC+5% | > WACC | < WACC | Supplementary |
| **Gross Margin** | Gross Profit / Revenue | > 40% | 20-40% | < 20% | Moat indicator |
| **Operating Margin** | Operating Income / Revenue | > 30% | 15-30% | < 15% | Moat indicator |
| **Net Margin** | Net Income / Revenue | > 15% | 5-15% | < 5% | Supplementary |

**ROE Scoring (from `src/analysis/fundamental.py` lines 63-72):**
- ROE > 15%: +2 points to health score, assessment = "Strong ROE"
- ROE 8-15%: +1 point, assessment = "Adequate ROE"
- ROE < 8%: 0 points, assessment = "Weak ROE"
- ROE is retrieved via `ratios.get("roe")` from yfinance (returned as decimal, e.g., 0.15 = 15%)

### 8.2 Efficiency Ratios

| Ratio | Formula | Interpretation |
|-------|---------|----------------|
| **Asset Turnover** | Revenue / Total Assets | Higher = more efficient asset utilization. Compare within industry only |
| **Inventory Turnover** | COGS / Average Inventory | Higher = stronger demand, better supply management. Declining = potential oversupply |
| **Receivables Turnover** | Revenue / Average Accounts Receivable | Higher = faster collection. Compare to industry credit terms |
| **Fixed Asset Turnover** | Revenue / Net PP&E | Higher = better capacity utilization. Critical for capital-intensive businesses |
| **Working Capital Turnover** | Revenue / Working Capital | Higher = more efficient working capital management |

### 8.3 Leverage Ratios

| Ratio | Formula | Strong | Adequate | Weak | Score Points |
|-------|---------|--------|----------|------|-------------|
| **D/E** | Total Debt / Equity | < 0.5x (<50) | 0.5-1.0x (50-100) | > 1.0x (>100) | +2 / +1 / 0 |
| **Interest Coverage** | EBIT / Interest Expense | > 8x | 4-8x | < 4x | Supplementary |
| **Net Debt/EBITDA** | (Debt - Cash) / EBITDA | < 1.0x | 1.0-3.0x | > 3.0x | Supplementary |
| **Debt/Assets** | Total Debt / Total Assets | < 25% | 25-50% | > 50% | Supplementary |

**D/E Scoring (from `src/analysis/fundamental.py` lines 52-61):**
- D/E < 50 (0.5x): +2 points to health score, assessment = "Low debt/equity"
- D/E 50-100 (0.5x-1.0x): +1 point, assessment = "Moderate debt/equity"
- D/E > 100 (1.0x): 0 points, assessment = "High debt/equity"

### 8.4 Growth Ratios

These feed directly into `FundamentalAnalyzer._assess_growth()`.

| Ratio | Formula | Strong | Adequate | Weak | Score Points |
|-------|---------|--------|----------|------|-------------|
| **Revenue Growth** | (Rev_current - Rev_prior) / Rev_prior | > 15% | 5-15% | < 5% | +2 / +1 / 0 |
| **Earnings Growth** | (EPS_current - EPS_prior) / EPS_prior | > 15% | 5-15% | < 5% | +2 / +1 / 0 |
| **FCF Growth** | (FCF_current - FCF_prior) / FCF_prior | > 10% | 0-10% | Negative | Supplementary |
| **Book Value Growth** | YoY Change in BV per Share | > 10% | 0-10% | Negative | Supplementary |

**Revenue Growth Scoring (from `src/analysis/fundamental.py` lines 81-90):**
- Revenue growth > 15%: +2 points to growth score, assessment = "Strong revenue growth"
- Revenue growth 5-15%: +1 point, assessment = "Moderate revenue growth"
- Revenue growth < 5%: 0 points, assessment = "Low revenue growth"
- Retrieved via `ratios.get("revenue_growth")` from yfinance (decimal, e.g., 0.15 = 15%)

**Earnings Growth Scoring (from `src/analysis/fundamental.py` lines 92-100):**
- Earnings growth > 15%: +2 points to growth score, assessment = "Strong earnings growth"
- Earnings growth 5-15%: +1 point
- Earnings growth < 5%: 0 points, assessment = "Low earnings growth"
- Retrieved via `ratios.get("earnings_growth")` from yfinance

### 8.5 Valuation Ratios

These feed into `FundamentalAnalyzer._assess_valuation()` (max 4 points) and `ValuationAnalyzer.comparable_valuation()`.

| Ratio | Formula | Cheap | Fair | Expensive | Score Points |
|-------|---------|-------|------|-----------|-------------|
| **Forward P/E** | Price / Forward EPS | < 15 | 15-25 | > 25 | +2 / +1 / 0 |
| **PEG** | P/E / Earnings Growth Rate | 0-1.0 | 1.0-2.0 | > 2.0 or negative | +2 / +1 / 0 |
| **P/B** | Price / Book Value per Share | < 1.5 | 1.5-3.0 | > 3.0 | Used in comparables |
| **EV/EBITDA** | Enterprise Value / EBITDA | < 10 | 10-15 | > 15 | Used in comparables |
| **P/S** | Price / Sales per Share | < 2 | 2-5 | > 5 | Used in comparables |

**Forward P/E Scoring (from `src/analysis/fundamental.py` lines 109-118):**
- Forward P/E < 15: +2 points, assessment = "Low forward P/E"
- Forward P/E 15-25: +1 point, assessment = "Moderate forward P/E"
- Forward P/E > 25: 0 points, assessment = "High forward P/E"
- Retrieved via `ratios.get("pe_forward")` from yfinance

**PEG Ratio Scoring (from `src/analysis/fundamental.py` lines 120-129):**
- PEG > 0 and < 1.0: +2 points, assessment = "Undervalued PEG"
- PEG 1.0-2.0: +1 point, assessment = "Fair PEG"
- PEG > 2.0 or negative: 0 points, assessment = "Expensive PEG"
- Retrieved via `ratios.get("peg_ratio")` from yfinance

---

## 9. DuPont Analysis

Decompose ROE into its three fundamental drivers to understand WHAT is generating returns:

```
ROE = Net Profit Margin  x  Asset Turnover  x  Equity Multiplier
    = (Net Income / Revenue) x (Revenue / Total Assets) x (Total Assets / Shareholders' Equity)
```

### 9.1 Interpretation

| Driver | Meaning | Sustainability |
|--------|---------|----------------|
| **High Net Margin** | Operational efficiency, pricing power | Most sustainable -- reflects competitive advantage |
| **High Asset Turnover** | Efficient use of assets, lean operations | Sustainable -- reflects operational excellence |
| **High Equity Multiplier** | Financial leverage | Least sustainable -- amplifies both gains and losses, increases risk |

### 9.2 Analysis Protocol

1. Calculate all three components for the current year and prior 4 years
2. Identify which component drives the most ROE change period-over-period
3. Compare the DuPont decomposition to peers:
   - Company A: 20% ROE from 10% margin x 0.8 turnover x 2.5 leverage
   - Company B: 20% ROE from 20% margin x 1.0 turnover x 1.0 leverage
   - Company B has far superior quality ROE despite identical headline numbers
4. Flag any company where the equity multiplier is the primary ROE driver -- this indicates leverage-dependent returns that are vulnerable in downturns

### 9.3 Extended DuPont (5-Factor)

For deeper analysis, use the 5-factor decomposition:

```
ROE = (EBIT/Revenue) x (Revenue/Assets) x (Assets/Equity) x (EBT/EBIT) x (NI/EBT)
    = Operating Margin x Asset Turnover x Equity Multiplier x Interest Burden x Tax Burden
```

This separates the tax and interest effects from operational performance.

---

## 10. Multi-Year Trend Analysis

### 10.1 Minimum Analysis Period

- **Always analyze minimum 3 years** of financial data, as specified in `configs/settings.yaml` (`analysis.fundamental.min_years: 3`)
- **Prefer 5 years** for a complete view of cyclical dynamics
- **Use 7-10 years** for cyclical industries (semiconductor memory, semiconductor equipment) to capture a full cycle

### 10.2 Trend Analysis Protocol

For each key metric, track the 5-year trajectory and compute:
1. **Compound Annual Growth Rate (CAGR)**: `(End/Start)^(1/years) - 1`
2. **Coefficient of Variation**: `Standard Deviation / Mean` -- measures consistency
3. **Direction**: consistently improving, deteriorating, or volatile
4. **Inflection points**: any year where a metric changed >20% YoY warrants root-cause investigation

### 10.3 Key Metrics to Track Over Time

| Category | Metrics | What Trend Reveals |
|----------|---------|-------------------|
| Revenue | Total revenue, organic growth, segment mix | Business momentum, diversification |
| Margins | Gross, operating, net | Pricing power, operational leverage, cost discipline |
| Returns | ROE, ROA, ROIC | Value creation sustainability |
| Cash | OCF, FCF, FCF margin | Cash generation ability |
| Balance Sheet | Net debt, current ratio, D/E | Financial risk trajectory |
| Per Share | EPS, BV/share, FCF/share, dividends/share | Shareholder value creation |
| Efficiency | DSO, DIO, DPO, CCC | Operational effectiveness |

### 10.4 Cyclical Adjustment

For cyclical industries (semiconductor equipment, memory, chemicals):
- Do NOT rely on a single year's ratios -- they may represent a peak or trough
- Calculate **normalized earnings** by averaging across a full cycle (typically 4-5 years)
- Use normalized P/E (price / average 5-year EPS) instead of trailing P/E
- Compare current margins to mid-cycle margins, not peak margins
- Book-to-bill ratio is the best leading indicator of where in the cycle a semiconductor equipment company sits

---

## 11. Industry-Specific Considerations for the AI Supply Chain

The FE-Analyst platform tracks a specific universe of AI supply chain companies defined in `configs/ai_moat_universe.yaml`. Each industry segment requires tailored analysis adjustments.

### 11.1 Semiconductor Equipment (Tokyo Electron, ASML, Lam Research, Applied Materials, Lasertec, Advantest, Disco, Screen, KLA)

- **Cyclicality**: Revenue can swing 20-40% peak-to-trough. Always normalize financials over a full cycle.
- **Book-to-Bill**: The single most important leading indicator. B/B > 1.1 = strong outlook; B/B < 0.9 for 2+ quarters = downturn ahead.
- **Service Revenue**: Typically 20-35% of total. Higher-margin and recurring. Growing service mix improves business quality.
- **Customer Concentration**: TSMC, Samsung, Intel, SK Hynix, and Micron are the major buyers. Concentration risk is structural and unavoidable.
- **Technology Nodes**: Companies leveraged to leading-edge nodes (EUV-related) have stronger moats and pricing power.
- **Backlog Duration**: Long backlogs (6-18 months) provide revenue visibility but can unwind rapidly in downturns.
- **WFE (Wafer Fab Equipment) Spending Cycles**: Correlated with semiconductor capex cycles. Track WFE forecasts from industry analysts.

### 11.2 Specialty Chemicals and Materials (Shin-Etsu, SUMCO, JSR, TOK, Resonac, Entegris, Linde)

- **Pricing Power**: Analyze ability to pass through raw material cost increases to customers. Gross margin stability through commodity cycles indicates pricing power.
- **Qualification Cycles**: Changing chemical suppliers in semiconductor fabs takes 12-24 months. This creates enormous switching costs that protect incumbents.
- **Volume vs Price**: Decompose revenue growth into volume and price components. Price-driven growth indicates pricing power; volume-only growth may indicate commodity dynamics.
- **Environmental Regulations**: Chemical companies face increasing ESG-related costs. Check environmental liability disclosures.
- **Product Purity Requirements**: Advanced node chemistry requires extreme purity levels, which creates barriers to entry.

### 11.3 Japanese Companies (8035.T, 6920.T, 6857.T, 6146.T, 7735.T, 4063.T, 3436.T, 6981.T, etc.)

- **Fiscal Year**: Most end March 31. When comparing to US peers with December FYE, be aware of the timing mismatch.
- **Reporting Currency**: JPY. For peer comparisons, convert financials to USD using the average exchange rate for the income statement and the period-end rate for the balance sheet.
- **Cross-Shareholdings**: Japanese companies often hold equity stakes in partners/suppliers. These appear in the investment portfolio and AOCI. These holdings can inflate book value but may not represent productive assets.
- **Conservative Accounting**: Japanese companies tend to be conservative in revenue recognition and provisioning, which often means reported earnings are high quality.
- **Shareholder Returns**: Historically low dividends and buybacks, but corporate governance reforms are driving increasing shareholder returns. Track payout ratio trajectory.
- **AOCI and FX**: Large FX translation adjustments in AOCI due to global operations denominated in USD, EUR, and other currencies.
- **R&D Disclosure**: Some Japanese companies provide limited segment detail. Use supplementary investor presentations for granular data.

### 11.4 Foundries (TSMC - 2330.TW / TSM)

- **Utilization Rates**: The key profitability driver. Margins expand dramatically at high utilization (>85%) and compress rapidly below 70%.
- **Technology Node Mix**: Revenue split by node (3nm, 5nm, 7nm, etc.). Leading-edge nodes carry premium ASPs and margins.
- **Customer Concentration**: Track percentage of revenue from top customers (Apple, NVIDIA, AMD, Qualcomm).
- **CapEx Intensity**: 30-50% of revenue invested in new capacity. Assess whether CapEx is backed by customer commitments.
- **HPC (High Performance Computing) Revenue**: The AI-relevant segment. Track HPC as % of revenue -- growing HPC mix is the key AI exposure metric.

### 11.5 Memory (SK Hynix - 000660.KS, Micron - MU)

- **Extreme Cyclicality**: Memory is the most cyclical semiconductor segment. Revenue and margins can swing violently.
- **Bit Growth vs ASP Trends**: Revenue = Bit Shipments x Average Selling Price. In downturns, ASPs collapse even as bit shipments grow.
- **HBM (High Bandwidth Memory)**: The critical AI growth driver. Track HBM revenue as % of total DRAM revenue and HBM market share.
- **Inventory Levels (Industry-Wide)**: Memory industry inventory levels (measured in weeks of supply) are the best cycle indicator. Low inventory = pricing recovery ahead.
- **Cost Per Bit Reduction**: The ability to reduce cost per bit through technology migration drives long-term profitability.
- **Normalize ALL Valuation Metrics**: Never use peak-cycle earnings for valuation. Use mid-cycle or trough-to-trough average earnings.

### 11.6 EDA and Design IP (Synopsys - SNPS, Cadence - CDNS, ARM)

- **Subscription/Recurring Revenue**: Typically 85-90% recurring. This makes these businesses highly predictable.
- **SBC Impact**: Very high SBC as % of operating income (can exceed 25%). Always analyze both GAAP and non-GAAP metrics.
- **R&D Intensity**: R&D spending 30-40% of revenue is normal and necessary to maintain technology leadership.
- **Customer Stickiness**: Switching EDA tools is prohibitively expensive and risky. This creates near-permanent customer relationships.
- **Bookings/RPO**: Remaining Performance Obligations provide 2-3 years of revenue visibility.

---

## 12. Red Flags Checklist

Review every item below for every company analyzed. Any confirmed red flag should be highlighted in the analysis output and may warrant a score penalty.

### 12.1 Revenue Quality Red Flags
- [ ] Revenue growing but operating cash flow declining (2+ consecutive quarters)
- [ ] Accounts receivable growing faster than revenue (DSO expansion)
- [ ] Significant channel stuffing indicators (spike in shipments at quarter-end)
- [ ] Revenue recognition policy change without clear business rationale
- [ ] Growing gap between reported revenue and cash collected from customers
- [ ] Deferred revenue declining while reported revenue grows (pulling forward recognition)

### 12.2 Earnings Quality Red Flags
- [ ] Frequent "non-recurring" charges that recur annually
- [ ] Declining gross margins masked by SGA cost cuts (unsustainable margin maintenance)
- [ ] Heavy reliance on non-GAAP adjustments (non-GAAP earnings >30% higher than GAAP)
- [ ] Operating cash flow / net income ratio consistently < 0.8
- [ ] Stock-based compensation > 20% of operating income
- [ ] Effective tax rate significantly below statutory rate without clear explanation

### 12.3 Balance Sheet Red Flags
- [ ] Inventory growing faster than COGS (potential obsolescence risk)
- [ ] Goodwill approaching or exceeding total shareholders' equity
- [ ] Debt growing while free cash flow declines
- [ ] Current ratio declining below 1.0
- [ ] Off-balance sheet obligations material relative to on-balance sheet debt
- [ ] Related party transactions of material size
- [ ] Contingent liabilities growing or poorly disclosed

### 12.4 Cash Flow Red Flags
- [ ] Dividend payments exceeding free cash flow for 2+ years
- [ ] Share buybacks funded entirely by debt issuance at high valuations
- [ ] CapEx significantly below depreciation for 3+ years (underinvestment)
- [ ] Operating cash flow consistently below net income (earnings quality issue)
- [ ] Large, unexplained changes in working capital components

### 12.5 Governance and Disclosure Red Flags
- [ ] Auditor change within the past 2 years
- [ ] Going-concern opinion from auditor
- [ ] Qualified audit opinion
- [ ] Frequent accounting policy changes
- [ ] CFO departure (especially sudden/unexplained)
- [ ] Delayed filing of 10-K or 10-Q
- [ ] Material weakness in internal controls (SOX 302/404 disclosures)
- [ ] Related party transactions with entities controlled by management or board

---

## 13. Scoring Integration

### 13.1 How Financial Statement Analysis Maps to the Composite Score

The financial statement analysis directly produces three sub-scores within the Fundamental dimension:

```
Fundamental Score = (Health x 0.4) + (Growth x 0.3) + (Valuation x 0.3)
                  = Normalized to 0-100 scale
                  = Weighted 30% in Composite Score (0-100)
```

**Financial Health Sub-Score (0-6 points):**

| Ratio | Threshold | Points | Code Reference |
|-------|-----------|--------|---------------|
| Current Ratio | > 1.5 | +2 | `fundamental.py` L43 |
| Current Ratio | 1.0 - 1.5 | +1 | `fundamental.py` L46 |
| Current Ratio | < 1.0 | 0 | `fundamental.py` L49 |
| D/E | < 50 | +2 | `fundamental.py` L54 |
| D/E | 50 - 100 | +1 | `fundamental.py` L57 |
| D/E | > 100 | 0 | `fundamental.py` L60 |
| ROE | > 15% (0.15) | +2 | `fundamental.py` L65 |
| ROE | 8-15% (0.08-0.15) | +1 | `fundamental.py` L68 |
| ROE | < 8% (0.08) | 0 | `fundamental.py` L71 |

Maximum health score: 6/6

**Growth Profile Sub-Score (0-4 points):**

| Ratio | Threshold | Points | Code Reference |
|-------|-----------|--------|---------------|
| Revenue Growth | > 15% (0.15) | +2 | `fundamental.py` L83 |
| Revenue Growth | 5-15% (0.05-0.15) | +1 | `fundamental.py` L86 |
| Revenue Growth | < 5% (0.05) | 0 | `fundamental.py` L89 |
| Earnings Growth | > 15% (0.15) | +2 | `fundamental.py` L93 |
| Earnings Growth | 5-15% (0.05-0.15) | +1 | `fundamental.py` L96 |
| Earnings Growth | < 5% (0.05) | 0 | `fundamental.py` L99 |

Maximum growth score: 4/4

**Valuation Sub-Score (0-4 points):**

| Ratio | Threshold | Points | Code Reference |
|-------|-----------|--------|---------------|
| Forward P/E | < 15 | +2 | `fundamental.py` L111 |
| Forward P/E | 15 - 25 | +1 | `fundamental.py` L114 |
| Forward P/E | > 25 | 0 | `fundamental.py` L117 |
| PEG Ratio | > 0 and < 1.0 | +2 | `fundamental.py` L122 |
| PEG Ratio | 1.0 - 2.0 | +1 | `fundamental.py` L125 |
| PEG Ratio | > 2.0 or negative | 0 | `fundamental.py` L128 |

Maximum valuation score: 4/4

### 13.2 Normalization to Composite Score

The `StockScorer.score()` method in `src/analysis/scoring.py` normalizes each sub-score:

```python
health = fund_result["health"]["score"] / fund_result["health"]["max_score"]     # 0-6 -> 0-1
growth = fund_result["growth"]["score"] / fund_result["growth"]["max_score"]     # 0-4 -> 0-1
val_score = fund_result["valuation"]["score"] / fund_result["valuation"]["max_score"]  # 0-4 -> 0-1
scores["fundamental"] = (health * 0.4 + growth * 0.3 + val_score * 0.3) * 100   # -> 0-100
```

The fundamental score (0-100) is then weighted at 30% in the composite:
```python
WEIGHTS = {
    "fundamental": 0.30,
    "valuation": 0.25,    # DCF-based
    "technical": 0.20,
    "sentiment": 0.10,
    "risk": 0.15,
}
```

### 13.3 Composite Score Recommendation Mapping

| Composite Score | Recommendation |
|-----------------|---------------|
| >= 75 | STRONG BUY |
| 60 - 74 | BUY |
| 45 - 59 | HOLD |
| 30 - 44 | SELL |
| < 30 | STRONG SELL |

---

## 14. Output Format

Every financial statement analysis must produce the following structured output:

### 14.1 Required Outputs

1. **Financial Health Score** (0-6): Based on current ratio, D/E ratio, and ROE with specific thresholds documented in Section 13.1
2. **Growth Profile Score** (0-4): Based on revenue growth and earnings growth with thresholds in Section 13.1
3. **Valuation Score** (0-4): Based on forward P/E and PEG ratio with thresholds in Section 13.1
4. **Key Ratio Summary Table**: All ratios from Section 8 with current values, 3-year trend direction, and peer comparison
5. **Red Flags Identified**: Any items from the Section 12 checklist that were confirmed
6. **3-Year Financial Trend Summary**: Key metrics with CAGR and trajectory assessment
7. **Peer Comparison**: Company vs peer median on profitability, leverage, growth, and valuation ratios
8. **Earnings Quality Assessment**: OCF/NI ratio and any quality concerns
9. **DuPont Decomposition**: ROE broken into margin, turnover, and leverage components

### 14.2 Example Output Structure

```json
{
  "ticker": "8035.T",
  "company": "Tokyo Electron",
  "sector": "Technology",
  "analysis_date": "2026-02-09",
  "health": {
    "score": 5,
    "max_score": 6,
    "reasons": [
      "Strong current ratio: 2.85",
      "Low debt/equity: 12.3",
      "Adequate ROE: 14.2%"
    ]
  },
  "growth": {
    "score": 3,
    "max_score": 4,
    "reasons": [
      "Strong revenue growth: 18.5%",
      "Moderate earnings growth: 12.1%"
    ]
  },
  "valuation": {
    "score": 1,
    "max_score": 4,
    "reasons": [
      "High forward P/E: 32.5",
      "Fair PEG: 1.76"
    ]
  },
  "red_flags": [],
  "earnings_quality": {
    "ocf_to_ni_ratio": 1.15,
    "assessment": "High quality - cash earnings exceed accrual earnings"
  },
  "dupont": {
    "net_margin": 0.18,
    "asset_turnover": 0.72,
    "equity_multiplier": 1.12,
    "roe": 0.145,
    "driver": "Net margin (operational efficiency)"
  },
  "trend_3yr": {
    "revenue_cagr": 0.14,
    "eps_cagr": 0.11,
    "fcf_cagr": 0.09,
    "margin_direction": "expanding",
    "leverage_direction": "stable"
  },
  "peer_comparison": {
    "peers": ["ASML", "LRCX", "AMAT", "KLAC"],
    "vs_median": {
      "roe": "below",
      "gross_margin": "inline",
      "de_ratio": "better",
      "revenue_growth": "above"
    }
  }
}
```

---

## 15. Step-by-Step Analysis Workflow

### Phase 1: Data Collection (Automated)
1. Retrieve company profile via `FundamentalsClient.get_company_profile(ticker)`
2. Retrieve 5 years of annual financial statements (income, balance sheet, cash flow)
3. Retrieve most recent quarterly statements for recency
4. Retrieve key ratios via `FundamentalsClient.get_key_ratios(ticker)`
5. Retrieve peer list via `FundamentalsClient.get_peers(ticker)`
6. Retrieve recent 10-K filing via `SECFilingsClient.get_recent_filings(ticker)`

### Phase 2: Pre-Analysis Validation
7. Complete the Pre-Analysis Checklist (Section 4)
8. Verify data completeness -- flag any missing critical ratios
9. Cross-validate key metrics between yfinance and SEC XBRL data

### Phase 3: Income Statement Analysis
10. Perform Revenue Analysis (Section 5.1)
11. Perform Margin Analysis (Section 5.2)
12. Perform Earnings Quality Assessment (Section 5.3)

### Phase 4: Balance Sheet Analysis
13. Perform Liquidity Assessment (Section 6.1)
14. Perform Leverage Analysis (Section 6.2)
15. Perform Asset Quality Review (Section 6.3)
16. Perform Equity Analysis (Section 6.4)

### Phase 5: Cash Flow Analysis
17. Analyze Operating Cash Flow and quality of earnings (Section 7.1)
18. Analyze Investing Cash Flow and CapEx intensity (Section 7.2)
19. Analyze Financing Cash Flow and dividend sustainability (Section 7.3)
20. Calculate Free Cash Flow

### Phase 6: Ratio Analysis and Scoring
21. Calculate all ratios from Section 8
22. Perform DuPont analysis (Section 9)
23. Perform multi-year trend analysis (Section 10)
24. Apply industry-specific adjustments (Section 11)
25. Score Financial Health (0-6)
26. Score Growth Profile (0-4)
27. Score Valuation (0-4)

### Phase 7: Quality Checks
28. Run Red Flags Checklist (Section 12) -- every item
29. Perform peer comparison on key metrics
30. Validate scores for reasonableness (cross-check against qualitative assessment)

### Phase 8: Output
31. Produce structured output per Section 14
32. Generate narrative summary with key findings
33. Highlight any red flags or concerns requiring further investigation

---

## 16. Common Pitfalls and How to Avoid Them

| Pitfall | Description | Mitigation |
|---------|-------------|------------|
| **Single-year analysis** | Drawing conclusions from one year's ratios | Always use minimum 3 years; 5 preferred |
| **Ignoring cyclicality** | Applying growth thresholds to cyclical peaks | Normalize ratios over a full cycle for cyclical companies |
| **Currency mismatches** | Comparing JPY-denominated ratios to USD ratios | Convert to common currency for peer comparison only |
| **D/E percentage confusion** | yfinance returns D/E as percentage (e.g., 50 = 0.5x) | The scoring code thresholds use percentage form: <50, 50-100, >100 |
| **Non-GAAP reliance** | Using adjusted earnings without checking GAAP | Always start from GAAP; use non-GAAP as supplementary |
| **Ignoring SBC** | Treating stock-based compensation as truly "non-cash" | SBC is a real cost via dilution; always note SBC impact on EPS |
| **Peak margin extrapolation** | Assuming current margins persist | Check where in the cycle the company sits; use mid-cycle margins for valuation |
| **Goodwill blindness** | Ignoring goodwill as "just an asset" | Large goodwill = acquisition risk; potential impairment in downturn |
| **Cash flow timing** | Comparing Q4 cash flows to Q1 (seasonality) | Use annual totals or TTM for cash flow analysis |
| **Peer mismatch** | Comparing a specialty equipment company to a diversified conglomerate | Ensure peers match on industry segment, size, and geography |

---

## 17. Appendix: Data Field Reference

### 17.1 Fields Available from `FundamentalsClient.get_key_ratios()`

These are the ratio fields returned by the platform and their yfinance source keys:

| Platform Key | yfinance Key | Type | Description |
|-------------|-------------|------|-------------|
| `pe_trailing` | `trailingPE` | float | Trailing 12-month P/E |
| `pe_forward` | `forwardPE` | float | Forward P/E (consensus estimates) |
| `peg_ratio` | `pegRatio` | float | Price/Earnings to Growth |
| `pb_ratio` | `priceToBook` | float | Price to Book Value |
| `ps_ratio` | `priceToSalesTrailing12Months` | float | Price to Sales (TTM) |
| `ev_ebitda` | `enterpriseToEbitda` | float | EV/EBITDA |
| `profit_margin` | `profitMargins` | float (decimal) | Net profit margin |
| `operating_margin` | `operatingMargins` | float (decimal) | Operating margin |
| `roe` | `returnOnEquity` | float (decimal) | Return on Equity |
| `roa` | `returnOnAssets` | float (decimal) | Return on Assets |
| `debt_to_equity` | `debtToEquity` | float (percentage) | Debt-to-Equity as % |
| `current_ratio` | `currentRatio` | float | Current Ratio |
| `quick_ratio` | `quickRatio` | float | Quick Ratio |
| `dividend_yield` | `dividendYield` | float (decimal) | Dividend Yield |
| `payout_ratio` | `payoutRatio` | float (decimal) | Dividend Payout Ratio |
| `revenue_growth` | `revenueGrowth` | float (decimal) | YoY Revenue Growth |
| `earnings_growth` | `earningsGrowth` | float (decimal) | YoY Earnings Growth |

### 17.2 Fields Available from `FundamentalsClient.get_company_profile()`

| Platform Key | yfinance Key | Description |
|-------------|-------------|-------------|
| `name` | `longName` | Full company name |
| `sector` | `sector` | GICS sector |
| `industry` | `industry` | GICS industry |
| `market_cap` | `marketCap` | Market capitalization |
| `employees` | `fullTimeEmployees` | Full-time employee count |
| `country` | `country` | Country of domicile |
| `website` | `website` | Company website URL |
| `description` | `longBusinessSummary` | Business description |

### 17.3 Comparable Valuation Metrics

The `ValuationAnalyzer.comparable_valuation()` method compares these four metrics against peer medians:

- `pe_forward` -- Forward P/E
- `pb_ratio` -- Price/Book
- `ev_ebitda` -- EV/EBITDA
- `ps_ratio` -- Price/Sales

For each, it calculates premium/discount percentage: `(company_value / peer_median - 1) * 100`

---

## 18. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-09 | FE-Analyst Team | Initial comprehensive SOP |

---

*This SOP is intended for use by AI agents and human analysts operating the FE-Analyst platform. It is not financial advice. All scoring thresholds and methodologies should be periodically reviewed against market conditions and updated as the platform evolves.*
