# SOP-003: Valuation Methodologies

| Field             | Value                                                     |
|-------------------|-----------------------------------------------------------|
| **SOP Number**    | 003                                                       |
| **Title**         | Valuation Methodologies                                   |
| **Module**        | `src/analysis/valuation.py` (ValuationAnalyzer)           |
| **Scoring Module**| `src/analysis/scoring.py` (StockScorer)                   |
| **Config**        | `configs/settings.yaml` -> `analysis.valuation`           |
| **Universe**      | `configs/ai_moat_universe.yaml` (8 categories, 40+ cos)  |
| **Score Weight**  | 25% of composite score (0-100)                            |
| **Version**       | 1.0                                                       |
| **Last Updated**  | 2026-02-09                                                |

---

## 1. Purpose

Valuation is where analysis meets investment decision. This SOP codifies how expert analysts determine intrinsic value and identify mispriced securities within the FE-Analyst platform. It governs every step from free cash flow extraction through final score calculation, and provides the disciplined framework that AI agents and human analysts alike must follow to produce rigorous, repeatable, and defensible valuations.

The valuation score constitutes 25% of the composite investment score (`StockScorer.WEIGHTS["valuation"] = 0.25`) and directly drives buy/sell/hold recommendations. Getting valuation wrong cascades into bad investment decisions; therefore this SOP demands conservatism, multi-method triangulation, and explicit documentation of every assumption.

---

## 2. Core Principles

### 2.1 No Single Method Is Sufficient
The best analysts triangulate using multiple valuation approaches and weight results based on company characteristics. A DCF alone can produce any number you want by tweaking assumptions. Comparable analysis alone ignores company-specific dynamics. Only by running multiple methods and checking for convergence can an analyst have confidence in a valuation.

### 2.2 Conservatism Over Precision
It is better to be approximately right than precisely wrong. When in doubt:
- Use the lower growth estimate
- Use the higher discount rate
- Use the more conservative terminal value assumption
- Round margin of safety downward

### 2.3 Garbage In, Garbage Out
Every valuation model is only as good as its inputs. Before running any model, verify:
- Financial data is current (check `cache.ttl_hours.fundamentals` = 168 hours in `configs/settings.yaml`)
- Cash flow statements are complete (not truncated by data provider)
- Shares outstanding is fully diluted (includes options, warrants, convertibles)
- Risk-free rate is live from FRED, not stale (check `analysis.valuation.risk_free_rate: auto`)

### 2.4 Document Every Assumption
Any valuation without explicit, written assumptions is useless. Every analysis must record:
- Growth rate used and why
- Discount rate components (risk-free, ERP, beta, WACC)
- Terminal growth rate and justification
- Peer set and rationale for inclusion/exclusion
- Any manual adjustments and reasoning

---

## 3. Valuation Method Selection Matrix

Not every company should be valued the same way. The primary method depends on the company's business characteristics, cyclicality, and data quality.

| Company Type | Primary Method | Secondary Method | Tertiary Method | Examples from Universe |
|---|---|---|---|---|
| Stable cash flow (equipment) | DCF (single-stage) | EV/EBITDA comps | P/E relative | Tokyo Electron (8035.T), ASML, AMAT, LRCX |
| High growth (AI exposure) | DCF (multi-stage) | PEG ratio | EV/Revenue | Arista Networks (ANET), ARM Holdings |
| Cyclical (memory, semis) | Normalized earnings | Mid-cycle P/E | EV/EBITDA through-cycle | SK Hynix (000660.KS), Micron (MU), SUMCO (3436.T) |
| Capital-light (EDA/IP) | DCF | P/E | EV/FCF | Synopsys (SNPS), Cadence (CDNS) |
| Japanese companies | EV/EBITDA | P/B (common metric) | Sum-of-parts | Shin-Etsu (4063.T), Murata (6981.T), Ajinomoto (2801.T) |
| Diversified conglomerates | Sum-of-parts | Segment-weighted EV/EBITDA | DCF per segment | Ajinomoto (food + ABF), Fujifilm (4901.T) |
| Monopoly/near-monopoly | DCF (with pricing power premium) | EV/EBITDA | Reverse DCF | Lasertec (6920.T), ASML, Ajinomoto ABF |
| Pre-profit / early stage | EV/Revenue | DCF (with multi-year negative FCF) | TAM-based | N/A in current universe (all profitable) |

### 3.1 Decision Procedure for Method Selection

```
1. Is the company cyclical (memory, commodity semis)?
   YES -> Use normalized/through-cycle as PRIMARY
   NO  -> Continue

2. Is the company a diversified conglomerate with distinct segments?
   YES -> Use sum-of-parts as PRIMARY
   NO  -> Continue

3. Does the company generate consistent positive FCF?
   YES -> Use DCF as PRIMARY
   NO  -> Is it high-growth with negative FCF?
          YES -> Use EV/Revenue or multi-stage DCF
          NO  -> Flag as "valuation uncertain", use comps only

4. ALWAYS run at least ONE comparable analysis as a cross-check
5. ALWAYS compute margin of safety vs. current market price
```

---

## 4. Method 1: Discounted Cash Flow (DCF) Analysis

This is the primary valuation method in FE-Analyst, implemented in `ValuationAnalyzer.dcf_valuation()`.

### 4.1 Implementation Reference

The current code signature:

```python
def dcf_valuation(
    self,
    ticker: str,
    growth_rate: float = 0.08,        # 8% default FCF growth
    terminal_growth: float = 0.025,    # 2.5% terminal growth
    discount_rate: float | None = None,# Auto-calculated if None
    projection_years: int = 5,         # 5-year explicit period
) -> dict:
```

The method returns: `current_fcf`, `discount_rate`, `growth_rate`, `terminal_growth`, `enterprise_value`, `intrinsic_per_share`, `current_price`, `margin_of_safety_pct`, and `verdict` (UNDERVALUED / FAIR / OVERVALUED).

### 4.2 Step-by-Step Procedure

#### Step 1: Free Cash Flow (FCF) Extraction

**Data Source:** `FundamentalsClient.get_cash_flow(ticker)` which pulls from yfinance (primary) with SimFin/FMP fallback.

**Procedure:**
1. Retrieve annual cash flow statement via `self.fundamentals.get_cash_flow(ticker)`
2. Extract `Free Cash Flow` row from the DataFrame index
3. Take the most recent period value: `float(fcf_row.iloc[0])`
4. **Verification checks:**
   - FCF should be positive for mature companies (all equipment, EDA, materials companies in our universe)
   - If FCF is negative, investigate: is it growth CapEx or a sign of trouble?
   - Compare FCF to Operating Cash Flow: FCF = OCF - CapEx
   - FCF margin (FCF / Revenue) should be >5% for healthy companies, >15% for capital-light companies like EDA
5. **For high-growth AI companies:** negative FCF is acceptable if:
   - Funded by strong balance sheet (current ratio >1.5, low debt/equity)
   - CapEx is clearly growth-oriented (capacity expansion for AI demand)
   - Operating cash flow is positive or trending positive
   - The company has a credible path to positive FCF within the forecast period

**AI Supply Chain FCF Benchmarks:**

| Category | Typical FCF Margin | Notes |
|---|---|---|
| Semiconductor equipment | 15-25% | High margins, moderate CapEx |
| EDA / Design IP | 25-35% | Asset-light, subscription revenue |
| Specialty chemicals | 8-15% | Capital-intensive, but pricing power |
| Advanced packaging | 5-12% | Heavy CapEx for capacity expansion |
| Foundry (TSMC) | 20-30% | Massive CapEx but even more massive OCF |
| Memory (cyclical) | -10% to 30% | Wildly cyclical, use normalized |
| Networking | 15-25% | Software-driven margins |
| Power/cooling | 8-15% | Growing CapEx for AI build-out |

#### Step 2: Growth Rate Estimation

**This is the most subjective and consequential input.** The default in our system is 8% (`growth_rate=0.08`), but this must be adjusted per company.

**Estimation Hierarchy (use in order of priority):**

1. **Historical FCF growth rate:** Calculate 3-year and 5-year FCF CAGR from cash flow statements
   ```
   CAGR = (FCF_recent / FCF_oldest) ^ (1/years) - 1
   ```
2. **Analyst consensus estimates:** Available through Finnhub if API key is set (`Keys.FINNHUB`)
3. **Revenue growth as proxy:** From `FundamentalsClient.get_key_ratios()` -> `revenue_growth`
4. **Industry growth projections:** Semiconductor equipment ~7-10% CAGR, EDA ~10-12%, AI-exposed segments higher
5. **Company guidance:** From 10-K/earnings calls (available via `sec_filings.py`)

**Conservatism Rule:** Use the LOWER of historical and forward estimates unless there is a compelling, documented reason to use the higher figure.

**AI Supply Chain Growth Rate Guidelines:**

| Category | Conservative | Base Case | Aggressive | Rationale |
|---|---|---|---|---|
| Semiconductor equipment | 5% | 8% | 12% | Cyclical but AI secular tailwind |
| EDA tools (SNPS, CDNS) | 8% | 12% | 15% | Design complexity driving demand |
| Specialty chemicals | 4% | 7% | 10% | Tied to wafer starts, pricing power |
| Advanced packaging | 8% | 15% | 20% | CoWoS/HBM bottleneck driving spend |
| Foundry (TSMC) | 8% | 12% | 18% | AI capex supercycle |
| Memory (HBM) | 5% | 10% | 18% | HBM demand explosion, but cyclical |
| Networking | 8% | 12% | 18% | AI cluster build-out |
| Power/cooling | 10% | 15% | 20% | Data center power crisis |

**Multi-Stage Growth for High-Growth Companies:**

When a single growth rate is insufficient, implement a multi-stage approach:
- **Years 1-3:** High growth rate (company-specific, analyst estimates)
- **Years 4-7:** Fade growth toward industry average (50% of initial rate)
- **Years 8-10:** Fade toward GDP growth + inflation (3-5%)

For AI supply chain companies, above-average growth rates may be sustainable for 3-5 years given the secular trend, but the analyst must document why the S-curve adoption dynamics support extended high growth.

#### Step 3: Explicit Forecast Period (5-10 Years)

**System default:** 5 years (`projection_years=5`). Use 7-10 years for high-growth companies where the runway is clearly visible.

**Implementation in code:**
```python
projected_fcf = []
for year in range(1, projection_years + 1):
    fcf = current_fcf * (1 + growth_rate) ** year
    projected_fcf.append(fcf)
```

**Enhanced Procedure (when overriding defaults):**
1. **Years 1-3:** Use specific estimates if available from analyst consensus or company guidance
2. **Years 4-5:** Fade toward industry average growth rate
3. **Years 6-10 (if used):** Fade toward long-term GDP growth + inflation (3-4%)
4. **For AI companies:** Consider S-curve adoption dynamics:
   - Early adopters (we may be here for some AI applications): steep growth curve
   - Early majority: growth acceleration phase
   - Late majority: growth deceleration
   - Saturation: terminal growth rate territory
5. **Reality checks at each year:**
   - Is implied revenue plausible given total addressable market (TAM)?
   - Is implied market share realistic?
   - Are implied margins consistent with industry structure?

**When to Use 5 vs. 10 Year Forecasts:**

| Scenario | Period | Reasoning |
|---|---|---|
| Mature, stable cash flow | 5 years | Terminal value handles the rest |
| High-growth with clear runway | 7-10 years | Need explicit modeling of growth phase |
| Cyclical companies | 5 years (full cycle) | Ensure forecast spans peak-to-peak or trough-to-trough |
| Uncertain environment | 5 years | Less forecasting error with shorter horizon |

#### Step 4: Terminal Value Calculation

**Method:** Gordon Growth Model (perpetuity growth)

**Formula (as implemented):**
```python
terminal_value = projected_fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
```

**Terminal Growth Rate (g):**
- System default: 2.5% (`terminal_growth=0.025`)
- Acceptable range: 2.0% to 3.0%
- NEVER exceed long-term nominal GDP growth (~4-5% for US, ~2-3% for Japan)
- For Japanese companies: use 1.5-2.5% (lower nominal GDP growth environment)
- For high-growth AI companies: still cap at 3.0%. The terminal value represents MATURE business state

**Sanity Checks (MANDATORY):**
1. **Terminal value as percentage of total DCF value:**
   - Target: 50-75% of total enterprise value
   - If >80%: The model is excessively dependent on terminal assumptions. Either extend the explicit forecast period or reduce terminal growth
   - If <40%: Growth assumptions in explicit period may be too aggressive relative to terminal
2. **Implied terminal FCF yield:** Terminal FCF / Terminal Enterprise Value should be reasonable (3-8%)
3. **Implied terminal P/E:** Should be 12-20x, not 30x+ (which implies growth above terminal rate)

**Terminal Value Alternatives (for cross-checking):**
- **Exit multiple method:** TV = Terminal Year EBITDA x Industry EV/EBITDA multiple
  - Use for cyclical companies where perpetuity growth is unreliable
  - Exit EV/EBITDA for semicon equipment: 12-18x
  - Exit EV/EBITDA for EDA: 20-30x
  - Exit EV/EBITDA for memory: 6-10x (through-cycle)

#### Step 5: Discount Rate (WACC)

**Auto-calculation in code (when `discount_rate=None`):**
```python
risk_free = self.macro.get_risk_free_rate()  # 10-year Treasury from FRED
discount_rate = risk_free + 0.06             # risk-free + equity risk premium
```

**Detailed WACC Construction (for manual override or enhanced analysis):**

**5a. Risk-Free Rate:**
- **US companies:** 10-year US Treasury yield from FRED series `DGS10`
  - Retrieved via `MacroDataClient.get_risk_free_rate()` which calls `get_fred_series("DGS10")`
  - Fallback: 4.0% if FRED data unavailable (`return 0.04`)
- **Japanese companies:** Use 10-year JGB yield (approximate: 0.5-1.5%)
  - Adjust: use FRED series `IRLTLT01JPM156N` or hardcode current JGB yield
- **European companies (ASML):** Use German Bund yield or ECB reference rate
- **Taiwanese companies (TSMC, Unimicron):** Use Taiwan 10-year government bond yield

**5b. Equity Risk Premium (ERP):**
- System default: 6.0% (`market_premium: 0.06` in `configs/settings.yaml`)
- Historical US average: 5-6%
- Current forward-looking estimates: 4-6% depending on methodology
- For emerging markets (Taiwan, Korea): add 1-2% country risk premium
- For Japan: ERP ~5-7% (equity culture still developing, governance premium/discount)

**5c. Beta:**
- Calculated by the Risk module (`RiskAnalyzer._beta()` in `src/analysis/risk.py`)
- Regression of stock returns against SPY benchmark over 2 years of daily data
- Formula: `beta = cov(stock, benchmark) / var(benchmark)`
- For Japanese stocks: consider regressing against Nikkei 225 or TOPIX as well
- For AI supply chain stocks: beta typically 1.0-1.8 (higher than market due to cyclicality)
- If beta is unreliable (low R-squared, short trading history): use industry average beta

**AI Supply Chain Beta Benchmarks:**

| Category | Typical Beta | Notes |
|---|---|---|
| Semiconductor equipment | 1.2-1.6 | Cyclical, high beta |
| EDA tools | 1.0-1.3 | Recurring revenue dampens volatility |
| Specialty chemicals | 0.8-1.2 | More stable, diversified revenue |
| Memory | 1.3-1.8 | Highly cyclical |
| Foundry (TSMC) | 1.0-1.3 | Dominant position provides stability |
| Networking | 1.1-1.5 | Tied to capex cycles |

**5d. Cost of Equity:**
```
Ke = Rf + beta x ERP
```
Example: Ke = 4.0% + 1.3 x 6.0% = 11.8%

**5e. Cost of Debt (if company has significant debt):**
```
Kd = (Interest Expense / Total Debt) x (1 - Tax Rate)
```
- Most AI supply chain companies have low debt (semiconductor equipment, EDA)
- Exception: companies with large CapEx programs may carry more debt

**5f. WACC Assembly:**
```
WACC = (E / (D+E)) x Ke + (D / (D+E)) x Kd
```
- E = Market capitalization
- D = Total debt (from balance sheet)
- For companies with minimal debt: WACC approximates Cost of Equity

**Typical WACC Ranges for AI Supply Chain:**

| Category | WACC Range | Notes |
|---|---|---|
| US large-cap (SNPS, CDNS, AMAT) | 9-12% | Lower risk premium |
| Japanese companies | 6-9% | Lower risk-free rate, but add JPY premium |
| Taiwan (TSMC) | 8-11% | Add geopolitical/country risk |
| Korea (SK Hynix) | 9-13% | Cyclicality + country risk |
| High-beta cyclicals (MU, memory) | 11-14% | Higher beta drives up cost |

#### Step 6: Intrinsic Value Per Share

**Implementation:**
```python
# Sum discounted FCFs
pv_fcfs = sum(fcf / (1 + discount_rate) ** i for i, fcf in enumerate(projected_fcf, 1))
pv_terminal = terminal_value / (1 + discount_rate) ** projection_years
enterprise_value = pv_fcfs + pv_terminal

# Per share
shares = yf.Ticker(ticker).info.get("sharesOutstanding", 1)
intrinsic_per_share = enterprise_value / shares
```

**Enhanced Procedure:**
1. Calculate present value of all projected FCFs
2. Calculate present value of terminal value
3. Sum to get Enterprise Value
4. **Subtract net debt** (or add net cash):
   ```
   Equity Value = Enterprise Value - Total Debt + Cash & Equivalents
   ```
   - NOTE: Current code does not subtract net debt. This is a known simplification. For companies with significant net cash (common in Japan and for EDA companies), the current code UNDERSTATES intrinsic value. For leveraged companies, it OVERSTATES
5. Divide by **fully diluted** shares outstanding
   - Include in-the-money stock options and warrants
   - Include convertible bonds (if applicable)
   - yfinance provides `sharesOutstanding`; verify against most recent 10-K for accuracy
6. Compare to current market price from `yf.Ticker(ticker).info.get("currentPrice")`

**Critical Note on Japanese Stocks:**
- Japanese companies traded on TSE quote prices in JPY
- If performing DCF in JPY, ensure all inputs are in JPY
- If using ADR (e.g., TOELY for Tokyo Electron), prices are in USD
- Cross-rate validation: JPY intrinsic value / USD-JPY rate should approximate ADR intrinsic value

#### Step 7: Margin of Safety Calculation

**Implementation:**
```python
margin_of_safety = (intrinsic_per_share - current_price) / intrinsic_per_share * 100
```

**Interpretation Thresholds:**

| Margin of Safety | Classification | Current Code Verdict | Score Impact |
|---|---|---|---|
| > 30% | Deep undervaluation | UNDERVALUED | +30 points (max) |
| 15% to 30% | Moderate undervaluation | UNDERVALUED | +15 to +30 points |
| 0% to 15% | Slight undervaluation | FAIR | +0 to +15 points |
| -10% to 0% | Approximately fair | FAIR | -0 to -10 points |
| < -10% | Overvalued | OVERVALUED | -10 to -30 points |

**Margin of Safety Adjustments by Company Quality:**
- Wide moat companies (ASML, Lasertec, Ajinomoto ABF): accept lower margin of safety (10-15%) because quality deserves a premium
- Narrow moat / cyclical: demand higher margin of safety (25-30%+) to compensate for uncertainty
- Companies with geopolitical risk (TSMC, SK Hynix): add 5-10% additional required margin

### 4.3 DCF Sensitivity Analysis

**MANDATORY for every DCF valuation.** The single-point intrinsic value is insufficient without understanding how sensitive it is to assumptions.

**Required Sensitivity Dimensions:**
1. WACC: +/- 1.0% in 0.5% increments
2. Terminal growth rate: +/- 0.5% in 0.25% increments
3. FCF growth rate: +/- 2% in 1% increments

**Sensitivity Matrix Template (WACC vs Terminal Growth):**

```
Intrinsic Value per Share Sensitivity

                    Terminal Growth Rate
                 2.0%    2.25%   2.50%   2.75%   3.0%
WACC  9.0%     $XXX    $XXX    $XXX    $XXX    $XXX
      9.5%     $XXX    $XXX    $XXX    $XXX    $XXX
     10.0%     $XXX    $XXX    $XXX    $XXX    $XXX
     10.5%     $XXX    $XXX    $XXX    $XXX    $XXX
     11.0%     $XXX    $XXX    $XXX    $XXX    $XXX
```

**Scenario Analysis (Bull / Base / Bear):**

| Parameter | Bear | Base | Bull |
|---|---|---|---|
| FCF growth rate | Historical low | Blended estimate | Analyst high |
| Projection years | 5 | 5-7 | 10 |
| Terminal growth | 2.0% | 2.5% | 3.0% |
| WACC | Base + 1% | Calculated | Base - 0.5% |
| Net debt adjustment | Conservative | Mid | Favorable |

---

## 5. Method 2: Comparable Company Analysis

Implemented in `ValuationAnalyzer.comparable_valuation()`.

### 5.1 Implementation Reference

```python
def comparable_valuation(self, ticker: str, peers: list[str] | None = None) -> dict:
```

The method:
1. Retrieves key ratios for the target company
2. Fetches peers from Finnhub (`FundamentalsClient.get_peers()`) or accepts manual list
3. Calculates `pe_forward`, `pb_ratio`, `ev_ebitda`, `ps_ratio` for all peers
4. Computes peer median (not mean) for each multiple
5. Calculates premium/discount percentage for the target vs peer median

### 5.2 Peer Selection Criteria

**Automated Peer Selection:**
- Finnhub `company_peers()` endpoint provides initial peer list (limited to first 5)
- These are often US-only and same-exchange; insufficient for our AI supply chain universe

**Manual Peer Selection (preferred for accuracy):**
Use the category groupings from `configs/ai_moat_universe.yaml`:

| Category | Peer Group Tickers |
|---|---|
| Semiconductor equipment | 8035.T, 6920.T, 6857.T, 6146.T, 7735.T, ASML, LRCX, AMAT, KLAC |
| Specialty chemicals | 4063.T, 3436.T, 4185.T, 4186.T, 4901.T, 4004.T, ENTG, LIN |
| Advanced packaging | 2801.T (ABF only), 4062.T, 6967.T, 3037.TW |
| Electronic components | 6981.T, 6762.T, 6594.T, 7741.T |
| EDA / Design IP | SNPS, CDNS, ARM |
| Networking | AVGO, ANET, APH |
| Power / cooling | VRT, MPWR |
| Foundry / memory | TSM (2330.TW), 000660.KS, MU |

**Peer Selection Procedure:**
1. Start with companies from same `ai_moat_universe.yaml` category
2. Filter to 4-8 peers based on:
   - Similar market capitalization (0.5x to 2x target)
   - Similar growth profile (revenue growth within 10 percentage points)
   - Similar geographic exposure (separate JP peer group from US when relevant)
   - Similar business model (pure-play vs diversified)
3. Remove outliers (companies in distress, recently IPO'd, M&A targets)
4. Document the final peer set and rationale for any inclusions/exclusions

### 5.3 Key Multiples Reference

| Multiple | Formula | When to Use | Pitfalls | Typical AI Supply Chain Range |
|---|---|---|---|---|
| EV/EBITDA | Enterprise Value / EBITDA | Capital-intensive, cross-border | Ignores CapEx differences, D&A policies | Equipment: 15-25x, EDA: 25-40x |
| P/E (Forward) | Price / Forward EPS | Profitable, stable earnings | Accounting diffs, cyclicality | Equipment: 20-35x, EDA: 35-50x |
| P/S | Price / Revenue per Share | High-growth, pre-profit | Ignores profitability entirely | Varies widely: 3-15x |
| EV/FCF | Enterprise Value / FCF | Strong cash generators | Volatile FCF distorts | Equipment: 20-35x, EDA: 30-50x |
| PEG | P/E / Earnings Growth Rate | Growth companies | Assumes linear growth relationship | <1.0 = attractive, >2.0 = expensive |
| P/B | Price / Book Value per Share | Japanese companies, asset-heavy | Intangibles not captured | Japan: 1-4x, US semis: 5-15x |
| EV/Revenue | Enterprise Value / Revenue | Early-stage, unprofitable | No profitability filter | 3-15x for AI supply chain |

### 5.4 Comparable Analysis Procedure

1. **Select 4-8 comparable companies** (see peer selection above)
2. **Calculate multiples for all peers** using `FundamentalsClient.get_key_ratios()`
3. **Use MEDIAN (not mean)** to reduce outlier impact
   - Code correctly uses `np.median(peer_vals)` -- do not change to mean
4. **Calculate premium/discount:**
   ```python
   premium_pct = (company_val / median - 1) * 100
   ```
5. **Interpret the premium/discount:**
   - Premium >20%: Company trades expensive vs peers. Justified? (higher growth, better moat, better management)
   - Discount >20%: Company trades cheap vs peers. Why? (hidden risk, temporary issue, market overlooking?)
   - Within +/-10%: Approximately in-line with peers
6. **Derive implied price target:**
   ```
   Implied Price = Peer Median Multiple x Target Company's Metric / Shares Outstanding
   ```
7. **Adjust for growth differential:**
   - If target grows faster than peer median: apply 5-15% premium
   - If target grows slower: apply 5-15% discount
   - Document the adjustment factor

### 5.5 Cross-Border Comparable Pitfalls

When comparing Japanese companies to US/European peers (common in our universe):

| Factor | Issue | Mitigation |
|---|---|---|
| Accounting standards | J-GAAP vs US-GAAP vs IFRS | Adjust for major differences (R&D capitalization, goodwill amortization) |
| Tax rates | Japan ~30%, US ~21%, Netherlands ~25% | Use pre-tax multiples (EV/EBIT, EV/EBITDA) for better comparability |
| Capital structure | Japanese companies hold excess cash | Use EV-based multiples (EV/EBITDA) which adjust for cash |
| Cross-shareholdings | Japanese companies hold equity in partners | Adjust EV for investment securities |
| Currency | JPY, USD, EUR, KRW, TWD | Convert all to same currency; use consistent exchange rates |
| Governance discount | Japanese companies historically trade at discount | Acknowledge but do not automatically apply; improving corporate governance (TSE reforms) reducing this gap |
| Fiscal year | Japan: March-end vs US: December-end | Use LTM (last twelve months) data for comparability |

---

## 6. Method 3: Normalized / Through-Cycle Valuation (for Cyclicals)

### 6.1 When to Use

**Mandatory for:**
- Memory companies: SK Hynix (000660.KS), Micron (MU)
- Silicon wafer companies: SUMCO (3436.T)
- Semiconductor equipment (supplementary to DCF): all equipment companies during cycle extremes

**The Cyclical Value Trap:**
Cyclical companies appear cheapest (low P/E) at the PEAK of their cycle when earnings are highest. They appear most expensive (high P/E) at the TROUGH when earnings are depressed. Buying at low P/E during peak earnings is one of the most common and costly mistakes in semiconductor investing.

### 6.2 Procedure

1. **Identify the cycle position:**
   - Memory cycle: typically 3-4 year duration (peak to peak)
   - Equipment cycle: typically 3-4 year duration, lagging memory by 6-12 months
   - Where are we now? Check: DRAM/NAND ASP trends, capacity utilization, CapEx announcements

2. **Calculate mid-cycle (normalized) earnings:**
   - **Method A (simple):** Average of last 5 years EPS (should cover at least one full cycle)
   - **Method B (peak-trough):** Average of peak EPS and trough EPS from the last cycle
   - **Method C (revenue-based):** Apply mid-cycle operating margin to current revenue
     ```
     Normalized EPS = Current Revenue x Mid-Cycle OPM x (1 - Tax Rate) / Shares
     ```

3. **Apply mid-cycle P/E multiple:**
   - Use the 5-year median P/E (not current P/E)
   - Or use industry mid-cycle P/E benchmarks:
     - Memory: 8-12x mid-cycle P/E
     - Semiconductor equipment: 18-25x mid-cycle P/E
     - Silicon wafers: 12-18x mid-cycle P/E

4. **Calculate normalized fair value:**
   ```
   Normalized Fair Value = Normalized EPS x Mid-Cycle P/E
   ```

5. **Compare to current price for margin of safety**

### 6.3 Semiconductor Cycle Indicators

Monitor these to determine cycle position:

| Indicator | Source | Bullish Signal | Bearish Signal |
|---|---|---|---|
| DRAM ASP trend | DRAMeXchange | Rising 3+ consecutive quarters | Falling after peak |
| NAND ASP trend | TrendForce | Rising or stabilizing | Falling rapidly |
| Fab utilization | Company reports | >90% | <80% |
| Equipment orders (B/B ratio) | SEMI | >1.0 | <0.9 |
| Inventory days | Company financials | Declining | Rising above 100 days |
| CapEx announcements | Earnings calls | Increasing | Cuts or deferrals |

---

## 7. Method 4: Sum-of-Parts (SOTP) Valuation

### 7.1 When to Use

- Diversified companies with distinct business segments
- Companies where one segment is significantly more valuable than market recognizes
- Japanese conglomerates common in our universe

**Key Examples from Our Universe:**
- **Ajinomoto (2801.T):** Food & seasonings business + ABF substrate film (near-monopoly in AI chip packaging)
- **Fujifilm (4901.T):** Healthcare + materials + semiconductor chemicals
- **Broadcom (AVGO):** Semiconductor + infrastructure software (VMware)

### 7.2 Procedure

1. **Identify and isolate business segments** from company filings (segment reporting in 10-K or annual report)
2. **For each segment:**
   a. Determine segment revenue and operating profit
   b. Select the most appropriate valuation multiple for that segment's industry
   c. Apply the multiple to derive segment value
   d. Example for Ajinomoto:
      - Food segment: valued at food industry EV/EBITDA (10-14x)
      - ABF substrate film: valued at specialty semiconductor materials EV/EBITDA (20-30x) or DCF with high growth rate
3. **Sum all segment values** to get total enterprise value
4. **Subtract holding company discount:** 10-20%
   - Rationale: conglomerate governance, capital allocation inefficiency, complexity discount
   - For Japanese companies: historically 15-25% discount, but narrowing with TSE governance reforms
5. **Subtract net debt, add net cash**
6. **Divide by diluted shares** for per-share value

### 7.3 SOTP Validation

- Compare SOTP value to market cap: if SOTP >> market cap, investigate catalyst for value unlock (spinoff, activist, governance reform)
- Verify segment-level margins are sustainable (not temporarily inflated)
- Cross-check segment multiples against pure-play peers

---

## 8. Valuation Score Calculation (Platform Scoring System)

### 8.1 How Valuation Maps to the Composite Score

From `src/analysis/scoring.py`:

```python
# Valuation score (0-100)
dcf = self.val.dcf_valuation(ticker)
mos = dcf.get("margin_of_safety_pct", 0)
scores["valuation"] = max(0, min(100, 50 + mos))
```

**This means:**
- Base score: 50 (neutral)
- Margin of safety directly adds to or subtracts from base
- MoS of +30% -> score = 80 (strong undervaluation signal)
- MoS of +50% -> score = 100 (capped)
- MoS of 0% -> score = 50 (fairly valued)
- MoS of -20% -> score = 30 (overvalued)
- MoS of -50% -> score = 0 (capped at floor)

### 8.2 Enhanced Scoring Framework

The current code uses a simplified single-method score. For rigorous analysis, the full scoring framework should incorporate:

```
Base Score: 50

DCF Component (primary, weight: 60%):
  If Intrinsic Value > Current Price:
    DCF_Score = 50 + min(30, Margin_of_Safety_pct)
  If Intrinsic Value < Current Price:
    DCF_Score = 50 - min(30, abs(Margin_of_Safety_pct))

Comparable Component (secondary, weight: 25%):
  If trading at >15% discount to peer median: +10
  If trading at >15% premium to peer median: -10
  If within +/-15%: +0

Quality Adjustments (weight: 15%):
  Earnings quality (consistent FCF, low accruals): +/- 5
  Growth sustainability (wide moat, secular tailwind): +/- 5
  Balance sheet strength (net cash, low leverage): +/- 5

Final Valuation Score = Clamp(weighted_sum, 0, 100)
```

### 8.3 Score Integration into Composite

The valuation score receives 25% weight in the final composite:

```python
WEIGHTS = {
    "fundamental": 0.30,
    "valuation": 0.25,   # <-- this SOP governs this component
    "technical": 0.20,
    "sentiment": 0.10,
    "risk": 0.15,
}
```

A valuation score of 80 contributes 80 x 0.25 = 20 points to the composite score. Combined with strong fundamentals (30%), this can drive a STRONG BUY recommendation (composite >= 75).

---

## 9. Special Considerations for AI Supply Chain Companies

### 9.1 Secular Growth Tailwind

The AI infrastructure buildout represents a multi-year capital expenditure supercycle. This has specific valuation implications:

- **Higher sustainable growth rates:** Companies like TSMC, ASML, and Ajinomoto ABF may sustain above-historical growth for 3-5 additional years
- **Multiple expansion justification:** If the market recognizes a longer growth runway, higher P/E and EV/EBITDA multiples are not automatically "overvalued"
- **But beware:** Multiple expansion beyond fundamentals is the most common source of permanent capital loss. Always ask: "What growth rate is the current price implying?" (reverse DCF)

### 9.2 Capacity Constraints and Pricing Power

Several companies in our universe operate at or near capacity constraints:
- **ASML EUV tools:** 2+ year lead times, order backlog
- **Ajinomoto ABF film:** Monopoly position, demand exceeds supply
- **TSMC CoWoS packaging:** Multi-quarter wait times for AI chip customers
- **SK Hynix HBM:** Sold out through next year

**Valuation impact:** Capacity constraints create pricing power, which:
- Supports higher margins (positive for FCF projections)
- Reduces revenue uncertainty (backlog provides visibility)
- Justifies lower discount rate (less business risk)
- But also invites competitive response (new entrants or substitutes in 3-5 years)

### 9.3 Technology Obsolescence Risk

Specific to semiconductor equipment and materials companies:
- EUV could be superseded by next-generation lithography (High-NA EUV, eventually something beyond)
- Current substrate materials could be replaced by alternatives
- Testing requirements evolve with new chip architectures

**Valuation adjustment:** Apply a technology risk discount of 5-10% to terminal value for companies dependent on a single technology platform. Monopolies like Lasertec (EUV mask inspection) are most exposed if EUV itself becomes obsolete.

### 9.4 Customer Concentration Risk

Many AI supply chain companies depend heavily on a small number of customers:
- TSMC: Apple + NVIDIA + AMD = majority of advanced node revenue
- SK Hynix: NVIDIA is dominant HBM customer
- Equipment companies: TSMC + Samsung + Intel = majority of orders

**Valuation adjustment:** Apply 3-5% discount to intrinsic value for companies with top customer >30% of revenue. Apply 5-10% for >50%.

### 9.5 Geopolitical Risk Discount

Taiwan and to a lesser extent Korea face material geopolitical risk:
- **Taiwan Strait risk:** Affects TSMC (2330.TW), Unimicron (3037.TW)
- **Korea-specific risk:** Affects SK Hynix (000660.KS)
- **Japan-China relations:** Affects all Japanese semiconductor companies (export controls)
- **US-China tech decoupling:** Affects all companies in the supply chain

**Valuation adjustment:**
- Taiwan exposure: 5-15% discount to intrinsic value depending on risk assessment
- Korea exposure: 3-8% discount
- Japan companies with China revenue >15%: 3-5% discount
- US companies affected by export controls: 2-5% discount (demand reduction risk)

### 9.6 Currency Considerations

For our multi-currency universe:
- **JPY-denominated stocks (TSE):** FCF in JPY, intrinsic value in JPY, compare to JPY stock price
- **ADRs:** FCF in local currency, convert at current FX rate, compare to USD ADR price
- **Cross-listed stocks:** Verify no persistent ADR premium/discount
- **FX sensitivity:** A strong USD weakens JPY-denominated intrinsic values for USD investors. Consider hedged vs unhedged returns

---

## 10. Common Valuation Mistakes (Anti-Patterns)

This section catalogs the most frequent and costly valuation errors. Every analyst must review this list before finalizing a valuation.

### 10.1 Fatal Errors (Will Produce Meaningfully Wrong Values)

| Mistake | Why It Is Wrong | How to Avoid |
|---|---|---|
| Using trailing earnings for cyclical companies at peak | Overstates sustainable earnings, leads to buying at the worst time | Use normalized/mid-cycle earnings (Method 3) |
| Ignoring dilution from stock options and convertibles | Understates share count, overstates per-share value | Use fully diluted shares from most recent filing |
| Double-counting growth | Setting both high explicit growth AND high terminal growth | Terminal growth must be 2-3% regardless of explicit period growth |
| Comparing EV-based and equity-based multiples inconsistently | EV/EBITDA vs P/E are not comparable frameworks | Keep numerator and denominator consistent: EV ratios for enterprise metrics, price ratios for equity metrics |
| Not adjusting for net cash/debt | Missing large cash positions (common in Japan) understates value; missing debt overstates | Always compute: Equity Value = EV - Debt + Cash |
| Using stale comparable data | Peer multiples from last quarter may not reflect current conditions | Refresh all peer data; check cache TTL |
| Using revenue growth as FCF growth | Revenue growth != FCF growth if margins are changing | Calculate FCF growth directly from historical FCF data |

### 10.2 Judgment Errors (Will Reduce Accuracy)

| Mistake | Why It Is Wrong | How to Avoid |
|---|---|---|
| Anchoring to previous price levels | "It was $200 last year, so $150 is cheap" -- price history is irrelevant to intrinsic value | Value from fundamentals only; ignore price charts during valuation |
| Ignoring minority interests in EV calculation | Overstates EV available to parent shareholders | Subtract minority interest from EV |
| Not adjusting for different tax jurisdictions | P/E comparison across US (21% tax), Japan (30%), Netherlands (25%) is misleading | Use pre-tax multiples or adjust earnings to common tax rate |
| Confusing one-time items with recurring | Restructuring charges, asset sales, litigation distort earnings | Use adjusted/normalized earnings; verify via cash flow statement |
| Applying US multiples to Japanese companies | Japanese companies historically trade at lower multiples | Use Japan-specific peer groups; acknowledge the valuation gap |
| Ignoring operating leases | Under-capitalizes asset-heavy businesses | Adjust for operating leases per IFRS 16 / ASC 842 |

### 10.3 Process Errors (Will Reduce Confidence in Output)

| Mistake | Why It Is Wrong | How to Avoid |
|---|---|---|
| Running only one valuation method | Single point of failure; no triangulation | Always run DCF + at least one comparable method |
| Not running sensitivity analysis | Presents false precision | Always produce WACC-growth sensitivity matrix |
| Not documenting assumptions | Valuation is unreproducible | Record every input and its source |
| Using default growth rates without thought | 8% is not appropriate for every company | Analyze company-specific growth drivers |
| Not sanity-checking terminal value percentage | TV >80% of total DCF means model is useless | Verify TV is 50-75% of total value |

---

## 11. Cross-Validation Requirements

No valuation should be published without cross-validation between methods.

### 11.1 Convergence Test

- DCF intrinsic value should be within 20% of comparable-based implied value
- If divergence > 20%, investigate and document the reason:
  - Is the DCF growth assumption too high/low?
  - Are the peers truly comparable?
  - Is the company a unique asset with no good comps? (e.g., Lasertec, ASML)
  - Is there a temporary distortion in either model?

### 11.2 Reverse DCF Validation

Answer the question: "What growth rate is the market currently pricing in?"

```
Solve for g in:
Current Price = Sum of [ FCF x (1+g)^t / (1+WACC)^t ] + Terminal Value / (1+WACC)^n
```

**Then evaluate:**
- Is the implied growth rate reasonable given company fundamentals?
- Is it below analyst consensus? (potential undervaluation)
- Is it above any reasonable estimate? (potential overvaluation)
- For AI supply chain: is the market pricing in 5 years of 20%+ growth? That may be aggressive even for this sector

### 11.3 Historical Valuation Range

Check where the stock trades relative to its own history:
- 5-year P/E range: is current P/E above/below historical median?
- 5-year EV/EBITDA range: same check
- If at the extremes, investigate why:
  - Justified by fundamental change (new AI demand, capacity expansion)?
  - Or market euphoria/pessimism that will revert?

### 11.4 Implied Return Calculation

```
Implied Annual Return = (Intrinsic Value / Current Price) ^ (1 / Time Horizon) - 1
```

- If implied return < cost of equity: stock is overvalued on a risk-adjusted basis
- If implied return > cost of equity + 3%: stock offers attractive risk premium
- Use 3-5 year time horizon for this calculation

---

## 12. Output Format and Reporting

Every valuation analysis must produce the following standardized output for inclusion in the final report (generated by `src/reports/generator.py`).

### 12.1 Required Output Fields

```
1. DCF Intrinsic Value per Share
   - Point estimate
   - Confidence range (bear/base/bull)
   - Key assumptions table (growth rate, WACC, terminal growth)

2. Comparable Analysis
   - Peer group with tickers
   - Peer median multiples (EV/EBITDA, P/E, P/S)
   - Premium/discount percentages
   - Implied price target from comps

3. Margin of Safety
   - Percentage (primary: DCF-based)
   - Classification (deep undervaluation / moderate / fair / overvalued)

4. Valuation Score (0-100)
   - Breakdown of score components
   - Weight in composite score

5. Scenario Analysis
   - Bull case value and assumptions
   - Base case value and assumptions
   - Bear case value and assumptions

6. Sensitivity Matrix
   - WACC vs terminal growth rate matrix
   - At least 5x5 grid (25 intrinsic values)

7. Cross-Validation Summary
   - DCF vs comps convergence (pass/fail, % divergence)
   - Reverse DCF implied growth rate
   - Historical valuation percentile
```

### 12.2 JSON Output Structure

The `dcf_valuation()` method returns:

```json
{
  "current_fcf": 5000000000,
  "discount_rate": 0.10,
  "growth_rate": 0.08,
  "terminal_growth": 0.025,
  "enterprise_value": 75000000000,
  "intrinsic_per_share": 185.50,
  "current_price": 142.30,
  "margin_of_safety_pct": 23.31,
  "verdict": "UNDERVALUED"
}
```

The `comparable_valuation()` method returns:

```json
{
  "ticker": "SNPS",
  "peers": ["CDNS", "ARM", "ANSS", "ADSK"],
  "comparison": {
    "pe_forward": {
      "company": 45.2,
      "peer_median": 42.8,
      "premium_pct": 5.6
    },
    "ev_ebitda": {
      "company": 35.1,
      "peer_median": 33.5,
      "premium_pct": 4.8
    }
  }
}
```

---

## 13. Workflow Integration

### 13.1 Valuation in the Full Analysis Pipeline

```
main.py analyze <TICKER>
  -> ReportGenerator.full_report()
    -> StockScorer.score()
      -> ValuationAnalyzer.dcf_valuation()      # This SOP, Method 1
      -> ValuationAnalyzer.comparable_valuation() # This SOP, Method 2
      -> scores["valuation"] = max(0, min(100, 50 + MoS))
    -> Combined with fundamental, technical, sentiment, risk scores
    -> Composite score and recommendation
```

### 13.2 Data Dependencies

| Input | Source | Module | Cache TTL |
|---|---|---|---|
| Free Cash Flow | yfinance cash flow statement | `FundamentalsClient.get_cash_flow()` | 168 hours (1 week) |
| Shares Outstanding | yfinance ticker info | `yf.Ticker(ticker).info` | Not cached (live) |
| Current Price | yfinance ticker info | `yf.Ticker(ticker).info` | Not cached (live) |
| Risk-Free Rate | FRED DGS10 series | `MacroDataClient.get_risk_free_rate()` | 24 hours |
| Key Ratios | yfinance ticker info | `FundamentalsClient.get_key_ratios()` | Not cached (live) |
| Peer Companies | Finnhub API | `FundamentalsClient.get_peers()` | Not cached (live) |
| Beta | 2-year daily returns vs SPY | `RiskAnalyzer._beta()` | Calculated on demand |

### 13.3 Error Handling and Fallbacks

| Failure Scenario | Current Behavior | Impact |
|---|---|---|
| No cash flow data | Returns `{"error": "No cash flow data available"}` | Valuation score defaults to 50 (neutral) |
| No FCF line item | Returns `{"error": "Free Cash Flow not found"}` | Valuation score defaults to 50 |
| FRED unavailable | Falls back to 4.0% risk-free rate | WACC may be slightly off |
| No peers from Finnhub | Returns `{"error": "No peer companies available"}` | Comparable analysis unavailable |
| yfinance rate limited | Cached data used if available | Stale data risk if cache expired |
| Negative intrinsic value | MoS calculation returns 0 | Score stays at 50 |

---

## 14. Practical Worked Examples

### 14.1 Example: Tokyo Electron (8035.T) -- Semiconductor Equipment

**Company Profile:** #3 global semiconductor equipment company. Coater/developer, etch, deposition tools. 45% AI exposure.

**Method Selection:** DCF (primary) + EV/EBITDA comps (secondary) per matrix: "Stable cash flow (equipment)"

**DCF Inputs:**
- Current FCF: retrieved from `get_cash_flow("8035.T")`
- Growth rate: 8% (base case, semicon equipment industry average + AI tailwind)
- Terminal growth: 2.0% (Japan nominal GDP proxy)
- Risk-free rate: JGB 10-year yield (~1.0%)
- ERP for Japan: 6.0%
- Beta: ~1.3 (regression vs TOPIX)
- WACC: 1.0% + 1.3 x 6.0% = 8.8%
- Projection years: 7 (extended for AI demand visibility)

**Comparable Peers:** ASML, LRCX, AMAT, KLAC, 6857.T (Advantest), 6146.T (Disco)
- Peer median EV/EBITDA: ~22x
- TEL EV/EBITDA: ~20x -> 9% discount to peers
- Interpretation: slight discount, possibly justified by lower growth or Japan governance discount

**Cross-validation:** DCF value vs comp-implied value: check for <20% divergence

### 14.2 Example: Synopsys (SNPS) -- EDA / Capital-Light

**Method Selection:** DCF (primary) + P/E comps (secondary) per matrix: "Capital-light (EDA/IP)"

**DCF Inputs:**
- Growth rate: 12% (EDA market growth + AI design complexity tailwind)
- Terminal growth: 2.5%
- Risk-free rate: US 10-year Treasury from FRED
- Beta: ~1.1 (lower volatility, recurring revenue)
- WACC: ~10-11%
- Projection years: 7

**Comparable Peers:** CDNS, ARM, ANSS (Ansys, pre/post acquisition)
- Use P/E and EV/FCF (capital-light business, FCF is clean)

### 14.3 Example: SK Hynix (000660.KS) -- Cyclical Memory

**Method Selection:** Normalized earnings (primary) + Mid-cycle P/E (secondary) per matrix: "Cyclical (memory, semis)"

**Normalized Earnings:**
- 5-year average EPS (covers at least one full memory cycle)
- Alternative: average of 2021 peak EPS and 2023 trough EPS
- Apply mid-cycle P/E of 8-10x

**Supplementary DCF:**
- Use mid-cycle FCF (not current year FCF which may be peak or trough)
- Higher WACC: 12-13% (Korea risk + cyclicality)
- Be cautious of terminal value -- memory is permanently cyclical

---

## 15. Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-02-09 | FE-Analyst Team | Initial comprehensive SOP |

---

## 16. References

- **Source Code:** `src/analysis/valuation.py` (ValuationAnalyzer class)
- **Scoring Integration:** `src/analysis/scoring.py` (StockScorer class, valuation weight = 0.25)
- **Data Sources:** `src/data_sources/fundamentals.py`, `src/data_sources/macro_data.py`
- **Risk Module (Beta):** `src/analysis/risk.py` (RiskAnalyzer._beta)
- **Configuration:** `configs/settings.yaml` (analysis.valuation section)
- **Company Universe:** `configs/ai_moat_universe.yaml` (peer groups, moat scores)
- **Moat Analysis:** `src/analysis/moat.py` (MoatAnalyzer, used for quality adjustments)

---

*This SOP is a living document. It must be updated when the valuation module code changes, when new methods are added, or when market conditions require revised assumptions. All AI agents operating within the FE-Analyst platform must follow this SOP when performing valuations.*
