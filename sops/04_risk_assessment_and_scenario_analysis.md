# SOP-004: Risk Assessment & Scenario Analysis

| Field             | Value                                              |
|-------------------|----------------------------------------------------|
| **SOP ID**        | SOP-004                                            |
| **Version**       | 1.0                                                |
| **Effective Date**| 2025-01-01                                         |
| **Owner**         | FE-Analyst Risk Module                             |
| **Status**        | Active                                             |
| **Applies To**    | All quantitative and qualitative risk assessment for individual securities and portfolios within the FE-Analyst platform |

---

## 1. Purpose

Risk management separates professional analysts from amateurs. This SOP documents how to systematically identify, quantify, and communicate investment risks for all securities analyzed by the FE-Analyst platform.

The FE-Analyst platform scores stocks on a 0-100 composite scale. The risk module contributes a 15% weight to the composite score (`StockScorer.WEIGHTS["risk"] = 0.15`). A higher risk score indicates lower risk (i.e., more favorable from a risk standpoint). The risk score is computed as:

```
Risk Score = (1 - volatility) * 100   # clamped to [0, 100]
```

This SOP governs every step of risk analysis, from raw data acquisition through final risk communication. It is designed to guide both human analysts and AI agents in performing rigorous, repeatable risk assessments.

---

## 2. Scope

This SOP covers:

- **Individual security risk analysis** for all companies in the AI supply chain universe (semiconductor equipment, specialty chemicals, advanced packaging, electronic components, EDA/design IP, networking, power/cooling, foundry/memory) across Japan, Taiwan, the United States, the Netherlands, South Korea, the United Kingdom, and Ireland.
- **Portfolio-level risk aggregation** including correlation, concentration, and factor analysis.
- **Scenario analysis and stress testing** for tail risk events relevant to the AI supply chain.
- **Risk communication standards** for reports and dashboards.

Out of scope: Derivatives pricing, options Greeks, credit risk analysis for fixed income, and operational risk of the platform itself.

---

## 3. Definitions and Abbreviations

| Term | Definition |
|------|-----------|
| **ADR** | American Depositary Receipt -- US-listed share representing foreign equity |
| **ADV** | Average Daily Volume -- mean number of shares traded per day |
| **ATH** | All-Time High -- the highest price a security has ever reached |
| **ATR** | Average True Range -- volatility indicator measuring average daily range |
| **Beta** | Sensitivity of a security's returns to benchmark returns |
| **CAGR** | Compound Annual Growth Rate |
| **CoWoS** | Chip on Wafer on Substrate -- TSMC's advanced packaging technology |
| **CVaR** | Conditional Value at Risk (Expected Shortfall) -- mean loss beyond VaR threshold |
| **DCF** | Discounted Cash Flow -- intrinsic valuation methodology |
| **EUV** | Extreme Ultraviolet Lithography -- cutting-edge semiconductor patterning technology |
| **GARCH** | Generalized Autoregressive Conditional Heteroskedasticity -- volatility model |
| **HBM** | High Bandwidth Memory -- stacked DRAM critical for AI accelerators |
| **MDD** | Maximum Drawdown -- largest peak-to-trough decline in a period |
| **Rf** | Risk-Free Rate -- annualized, sourced from FRED (default 4% fallback) |
| **Sharpe Ratio** | Risk-adjusted return metric: (Return - Rf) / Volatility |
| **Sortino Ratio** | Downside-risk-adjusted return: (Return - Rf) / Downside Deviation |
| **VaR** | Value at Risk -- maximum expected loss at a given confidence level |

---

## 4. Data Sources and Configuration

### 4.1 Primary Data Source

All price data is sourced through yfinance via `MarketDataClient.get_price_history()`:

```python
# src/data_sources/market_data.py
stock = yf.Ticker(ticker)
df = stock.history(period=period, interval=interval)
```

**Key parameters from `configs/settings.yaml`:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| `analysis.risk.var_confidence` | 0.95 | Confidence level for VaR/CVaR calculations |
| `analysis.risk.lookback_days` | 252 | Trading days in lookback window (~1 calendar year) |
| `cache.ttl_hours.price_historical` | 24 | Cache TTL for historical price data |
| `analysis.valuation.risk_free_rate` | auto | Pulled from FRED; 4% annual fallback in code |

### 4.2 Ticker Conventions

The universe spans multiple exchanges. Tickers must use the correct suffix:

| Exchange | Format | Example |
|----------|--------|---------|
| Tokyo Stock Exchange | `{code}.T` | `8035.T` (Tokyo Electron) |
| Taiwan Stock Exchange | `{code}.TW` | `2330.TW` (TSMC) |
| Korea Stock Exchange | `{code}.KS` | `000660.KS` (SK Hynix) |
| US exchanges (NYSE/NASDAQ) | `{symbol}` | `ASML`, `LRCX`, `MU` |
| ADRs for US-listed foreign stocks | `{symbol}` | `TSM` (TSMC ADR), `TOELY` (Tokyo Electron ADR) |

When analyzing foreign-listed equities, always pull **both** the local ticker and the ADR ticker (if one exists) to cross-validate price data and identify currency-driven discrepancies.

### 4.3 Benchmark Definitions

| Benchmark | Ticker | Use Case |
|-----------|--------|----------|
| S&P 500 | `SPY` | Primary market benchmark for beta calculation |
| Semiconductor ETF | `SMH` | Sector benchmark for semiconductor companies |
| Alternative semi ETF | `SOXX` | Secondary sector benchmark |
| TOPIX ETF | `1306.T` | Japanese market benchmark (for Japan-listed equities) |
| TAIEX ETF | `0050.TW` | Taiwanese market benchmark (for Taiwan-listed equities) |

---

## 5. Quantitative Risk Metrics

The `RiskAnalyzer` class (`src/analysis/risk.py`) computes all quantitative metrics. Each metric is detailed below with its formula, implementation reference, interpretation guidelines, and edge cases.

### 5.1 Annualized Volatility

**Definition:** Standard deviation of daily log returns, annualized to represent expected annual price variability.

**Formula:**

```
Annualized Volatility = daily_std_dev * sqrt(252)
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _annualized_volatility(returns: pd.Series) -> float:
    return round(float(returns.std() * np.sqrt(252)), 4)
```

**Interpretation Thresholds:**

| Volatility Range | Risk Level | Typical Companies |
|------------------|------------|-------------------|
| < 15% | LOW | Utilities, large-cap staples (rare in AI supply chain) |
| 15% - 25% | MODERATE | Large-cap semis (ASML, TSMC ADR), diversified industrials (Ajinomoto) |
| 25% - 40% | HIGH | Mid-cap semis (Advantest, Lasertec), memory (SK Hynix, Micron) |
| > 40% | VERY HIGH | Small-cap Japanese suppliers, highly cyclical equipment plays |

**Note:** The code in `RiskAnalyzer.analyze()` uses slightly different thresholds for the `risk_level` label: <15% LOW, 15-30% MODERATE, 30-50% HIGH, >50% VERY HIGH. The scoring module (`StockScorer`) uses a simpler formula: `risk_score = max(0, min(100, (1 - vol) * 100))`.

**Rolling Volatility Analysis:**

In addition to the single-period volatility, analysts and agents should compute rolling volatility to detect regime changes:

- **30-day rolling:** Captures short-term volatility spikes (earnings, geopolitical events)
- **60-day rolling:** Intermediate-term regime identification
- **90-day rolling:** Smoothed trend for regime classification

**Volatility Regime Detection:**

| Regime | Criteria | Implication |
|--------|----------|-------------|
| Low volatility | Current 30d vol < 0.7 * 90d vol | Complacency; potential for vol expansion |
| Normal volatility | 30d vol within 0.7-1.3 * 90d vol | Stable environment |
| High volatility | Current 30d vol > 1.3 * 90d vol | Stress; position sizing should decrease |
| Volatility clustering | 3+ consecutive days of >2 sigma moves | GARCH-like behavior; expect persistence |

**Cross-Asset Volatility Comparison:**

Always compare a stock's volatility to its peer group. For example, compare Lasertec (6920.T) against other semiconductor equipment names (Tokyo Electron, Advantest, ASML). A stock trading at the high end of peer volatility demands a higher risk premium.

**Historical vs. Implied Volatility:**

When available (primarily for US-listed names with liquid options), compare historical realized volatility against implied volatility (IV):

| Condition | Signal |
|-----------|--------|
| IV > HV by >20% | Market pricing in future risk (potential event: earnings, regulation) |
| IV < HV by >20% | Market may be underpricing risk; or recent vol spike subsiding |
| IV ~ HV | Options market in agreement with recent price action |

### 5.2 Beta Analysis

**Definition:** Measures a stock's systematic risk relative to a benchmark. Beta of 1.0 means the stock moves in line with the market.

**Formula:**

```
Beta = Cov(stock_returns, benchmark_returns) / Var(benchmark_returns)
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _beta(stock_returns: pd.Series, bench_returns: pd.Series) -> float:
    cov = stock_returns.cov(bench_returns)
    var = bench_returns.var()
    if var == 0:
        return 0.0
    return round(float(cov / var), 4)
```

**Data alignment:** The `analyze()` method aligns stock and benchmark return dates via inner join before computing beta, which is critical for international stocks where trading calendars differ.

**Interpretation:**

| Beta Range | Meaning | Example Companies |
|------------|---------|-------------------|
| < 0.5 | Defensive; low market sensitivity | Rare in AI supply chain; Ajinomoto (diversified) |
| 0.5 - 1.0 | Below-market sensitivity | ASML (large, liquid), Shin-Etsu Chemical |
| 1.0 - 1.5 | Above-market sensitivity | Most AI supply chain stocks |
| 1.5 - 2.0 | High sensitivity; amplifies market swings | Lasertec, Advantest, smaller Japanese semis |
| > 2.0 | Very high sensitivity; speculative | Micro-cap suppliers, pre-profit companies |

**Adjusted Beta (Bloomberg Method):**

Raw beta tends to be noisy, especially for international stocks with calendar mismatches. Apply mean-reversion adjustment:

```
Adjusted Beta = (2/3 * Raw Beta) + (1/3 * 1.0)
```

This assumes betas revert toward 1.0 over time. Use adjusted beta for forward-looking analyses (DCF cost of equity, expected drawdown).

**Multi-Benchmark Beta:**

For AI supply chain stocks, compute beta against multiple benchmarks:

| Benchmark | Purpose |
|-----------|---------|
| SPY | Market risk (used in primary scoring) |
| SMH / SOXX | Sector-specific risk for semiconductor companies |
| Local index (TOPIX / TAIEX) | Country-specific risk for non-US companies |

**Important consideration for international stocks:** Beta vs. SPY for Japanese/Taiwanese stocks includes a currency component. A stock may have low local beta but high USD beta due to JPY/USD or TWD/USD movements. Always note whether beta is calculated on local-currency returns or USD-denominated returns.

**Rolling Beta:**

Compute 60-day and 120-day rolling beta to detect secular changes in market sensitivity. A rising beta may indicate:
- Increased speculative interest in the stock
- Higher correlation to market risk factors
- Transition from defensive to growth narrative

### 5.3 Sharpe Ratio

**Definition:** Return earned per unit of total risk (volatility), excess of the risk-free rate.

**Formula:**

```
Sharpe Ratio = (Annualized Return - Rf) / Annualized Volatility

Where:
- Rf_daily = annual_risk_free_rate / 252
- Excess daily returns = daily_returns - Rf_daily
- Sharpe = mean(excess_daily_returns) / std(excess_daily_returns) * sqrt(252)
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _sharpe_ratio(returns: pd.Series, risk_free_annual: float = 0.04) -> float:
    rf_daily = risk_free_annual / 252
    excess = returns - rf_daily
    if excess.std() == 0:
        return 0.0
    return round(float(excess.mean() / excess.std() * np.sqrt(252)), 4)
```

**Interpretation:**

| Sharpe Ratio | Quality | Action Implication |
|--------------|---------|-------------------|
| < 0 | Negative | Stock is losing money vs. risk-free; penalize risk score by -10 |
| 0.0 - 0.5 | Poor | Insufficient compensation for risk taken |
| 0.5 - 1.0 | Acceptable | Adequate risk-adjusted return |
| 1.0 - 2.0 | Good | Strong risk-adjusted performance |
| > 2.0 | Excellent | Exceptional; verify sustainability (may be short sample artifact) |

**Caveats:**
- Sharpe assumes normally distributed returns. AI supply chain stocks often exhibit fat tails and skewness, making Sharpe potentially misleading.
- Short lookback periods can produce artificially high Sharpe ratios during momentum rallies.
- Always present Sharpe alongside Sortino (which better handles asymmetric distributions).

### 5.4 Sortino Ratio

**Definition:** Return earned per unit of downside risk only. Superior to Sharpe for stocks with asymmetric return distributions (common in high-growth AI supply chain names).

**Formula:**

```
Sortino Ratio = (Annualized Return - Rf) / Annualized Downside Deviation

Where:
- Downside Deviation = std(negative excess returns) * sqrt(252)
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _sortino_ratio(returns: pd.Series, risk_free_annual: float = 0.04) -> float:
    rf_daily = risk_free_annual / 252
    excess = returns - rf_daily
    downside = excess[excess < 0]
    if downside.std() == 0:
        return 0.0
    return round(float(excess.mean() / downside.std() * np.sqrt(252)), 4)
```

**Interpretation:**

| Sortino Ratio | Quality | Notes |
|---------------|---------|-------|
| < 0 | Negative | Losing money; same as negative Sharpe |
| 0.0 - 1.0 | Below average | Downside risk exceeds compensation |
| 1.0 - 2.0 | Good | Downside well-compensated; +5 bonus to risk score |
| > 2.0 | Excellent | Outstanding downside-adjusted return |

**Why Sortino > Sharpe for AI Supply Chain:**

AI supply chain stocks (Lasertec, Advantest, TSMC) frequently exhibit positive skewness during bull markets. Sharpe penalizes upside volatility equally with downside volatility. Sortino isolates downside risk, providing a more accurate picture of "bad" volatility.

### 5.5 Maximum Drawdown (MDD)

**Definition:** The largest peak-to-trough decline in portfolio/stock value over a given period. Measures worst-case historical loss.

**Formula:**

```
Drawdown(t) = (Price(t) - Peak(t)) / Peak(t)
Maximum Drawdown = min(Drawdown(t)) for all t in period
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _max_drawdown(prices: pd.Series) -> float:
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    return round(float(drawdown.min()), 4)
```

**Interpretation for AI Supply Chain:**

| Max Drawdown | Severity | Context |
|--------------|----------|---------|
| 0% to -10% | Mild | Normal market fluctuation |
| -10% to -20% | Moderate | Sector rotation, earnings miss |
| -20% to -30% | Significant | Sector-wide correction, macro event |
| -30% to -50% | Severe | Cyclical downturn (typical for semis in recessions) |
| > -50% | Critical | Existential threat, permanent capital loss risk |

**Semiconductor-Specific Context:**

Semiconductor stocks are deeply cyclical. Historical drawdown norms for this sector:

- **Normal cycle trough:** 30-40% drawdown from peak (expect this every 3-5 years)
- **Severe recession (2008-type):** 50-70% drawdowns across the board
- **Company-specific shock:** 40-60% (customer loss, technology miss, export ban)

**Extended Drawdown Metrics (Compute Beyond Core Module):**

| Metric | Definition | Why It Matters |
|--------|-----------|----------------|
| Drawdown Duration | Days from peak to trough | Measures how long pain persists |
| Recovery Duration | Days from trough back to prior peak | Measures how long recovery takes |
| Current Drawdown | Distance from current ATH | Opportunity indicator if fundamentals intact |
| Drawdown Frequency | Count of >10% drawdowns per year | Behavioral: how often does the stock test investor patience |
| Ulcer Index | RMS of drawdown percentages | Captures both depth and duration of drawdowns |

### 5.6 Value at Risk (VaR)

**Definition:** The maximum expected loss over a given time horizon at a specified confidence level.

**Formula (Historical Method):**

```
VaR(95%) = 5th percentile of historical daily returns distribution
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    return round(float(np.percentile(returns, (1 - confidence) * 100)), 4)
```

**Interpretation:**

A VaR(95%) of -0.0325 means: "On any given day, there is a 95% probability that the stock will not lose more than 3.25% of its value."

**Dollar VaR for Position Sizing:**

```
Dollar VaR = Position Value * VaR(95%)

Example:
  Position: $100,000 in Lasertec (6920.T)
  VaR(95%): -3.8%
  Dollar VaR: $100,000 * 0.038 = $3,800 daily risk
```

**VaR Methods Comparison:**

| Method | Implementation | Pros | Cons |
|--------|---------------|------|------|
| Historical | Sort returns, find percentile (our implementation) | No distribution assumption; captures fat tails | Backward-looking; sample-size dependent |
| Parametric | Assume normal: VaR = mean - z * sigma | Simple; fast | Underestimates tail risk for leptokurtic distributions |
| Monte Carlo | Simulate return paths | Flexible; can model complex distributions | Computationally expensive; model-dependent |

**Critical Limitation:** VaR tells you nothing about the magnitude of losses *beyond* the threshold. A stock with 95% VaR of -3% could lose 3.1% or 30% on the worst day -- VaR cannot distinguish these. This is why CVaR is essential.

### 5.7 Conditional VaR (CVaR / Expected Shortfall)

**Definition:** The average loss in the worst (1 - confidence)% of cases. Answers: "When things go really bad, how bad do they get on average?"

**Formula:**

```
CVaR(95%) = mean of returns where return <= VaR(95%)
```

**Implementation:**

```python
# src/analysis/risk.py
@staticmethod
def _conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    var = np.percentile(returns, (1 - confidence) * 100)
    return round(float(returns[returns <= var].mean()), 4)
```

**Interpretation:**

A CVaR(95%) of -0.052 means: "In the worst 5% of trading days, the average loss is 5.2%."

**CVaR vs. VaR:**

| Metric | What It Tells You | Use Case |
|--------|-------------------|----------|
| VaR(95%) | "Losses won't exceed X% on 95% of days" | General risk budgeting |
| CVaR(95%) | "When losses do exceed VaR, they average Y%" | Tail risk assessment; critical for concentrated positions |

**For AI supply chain stocks specifically:** The CVaR/VaR ratio is informative:

| CVaR / VaR Ratio | Interpretation |
|-------------------|---------------|
| 1.0 - 1.3 | Thin tails; losses beyond VaR are moderate |
| 1.3 - 1.6 | Normal fat tails for growth/cyclical equities |
| 1.6 - 2.0 | Heavy tails; significant tail risk |
| > 2.0 | Extreme tail risk; consider position size reduction |

---

## 6. Risk Score Calculation

### 6.1 Core Risk Score (Current Implementation)

The `StockScorer` computes the risk component as:

```python
# src/analysis/scoring.py
risk = self.risk.analyze(ticker)
vol = risk.get("volatility", 0.3)
scores["risk"] = max(0, min(100, (1 - vol) * 100))
```

**Mapping examples:**

| Volatility | Risk Score | Interpretation |
|------------|------------|----------------|
| 10% (0.10) | 90 | Very low risk |
| 20% (0.20) | 80 | Low risk |
| 30% (0.30) | 70 | Moderate risk |
| 40% (0.40) | 60 | Elevated risk |
| 50% (0.50) | 50 | High risk |
| 70% (0.70) | 30 | Very high risk |
| 100% (1.00) | 0 | Extreme risk |

### 6.2 Enhanced Risk Score (Recommended Adjustments)

The base score uses only volatility. For more accurate risk assessment, apply adjustments:

```
Enhanced Risk Score = Base Score + Adjustments

Base Score = (1 - normalized_volatility) * 100

Where:
  normalized_volatility = (stock_vol - min_vol) / (max_vol - min_vol)
  min_vol = minimum volatility in peer group
  max_vol = maximum volatility in peer group
  Score 0 = highest volatility in peer group
  Score 100 = lowest volatility in peer group

Adjustments:
  Beta > 1.5:              penalty  -5 points
  Max Drawdown > 40%:      penalty  -5 points
  Sharpe Ratio < 0:        penalty -10 points
  Sortino Ratio > 1.0:     bonus   +5 points
  CVaR/VaR ratio > 2.0:    penalty  -5 points  (heavy tail risk)
  Current drawdown > 25%:  penalty  -3 points  (elevated loss potential)
  Beta < 0.8:              bonus   +3 points   (defensive characteristic)
```

**Final Score Clamping:**

```
Final Risk Score = max(0, min(100, Enhanced Risk Score))
```

### 6.3 Risk Level Classification

The `RiskAnalyzer.analyze()` method assigns a risk level label:

```python
if vol < 0.15:
    result["risk_level"] = "LOW"
elif vol < 0.30:
    result["risk_level"] = "MODERATE"
elif vol < 0.50:
    result["risk_level"] = "HIGH"
else:
    result["risk_level"] = "VERY HIGH"
```

**Extended classification incorporating multiple metrics:**

| Risk Rating | Volatility | Beta | Max Drawdown | Sharpe | Additional Criteria |
|-------------|-----------|------|--------------|--------|-------------------|
| LOW | < 15% | < 1.0 | > -15% | > 1.0 | No single risk flag triggered |
| MODERATE | 15-25% | 1.0-1.5 | -15% to -30% | 0.5-1.0 | At most 1 risk flag |
| HIGH | 25-40% | 1.5-2.0 | -30% to -50% | 0-0.5 | 2-3 risk flags |
| VERY HIGH | > 40% | > 2.0 | > -50% | < 0 | 4+ risk flags or any single extreme value |

**Rule:** Never classify a stock as "LOW" risk if any single metric falls in the "HIGH" or "VERY HIGH" range. The overall rating is constrained by the worst individual metric.

---

## 7. Qualitative Risk Assessment

Quantitative metrics capture historical statistical risk. Qualitative assessment identifies forward-looking risks that statistics cannot measure.

### 7.1 Business Risk Categories

For every company in the AI supply chain universe, assess the following risk categories:

**7.1.1 Technology Obsolescence Risk**

| Risk Factor | Description | High-Risk Indicators |
|-------------|-------------|---------------------|
| Lithography transition | Shift from DUV to EUV to High-NA EUV | Companies reliant on legacy DUV tools |
| Packaging technology | Transition to advanced packaging (CoWoS, HBM) | Companies without advanced packaging capability |
| Process node advancement | 3nm, 2nm, 1.4nm transitions | Equipment not qualified for next node |
| Architecture shifts | Chiplets, 3D stacking, photonics | Material suppliers for legacy architectures |

**7.1.2 Customer Concentration Risk**

| Company Type | Key Risk | Mitigation Check |
|-------------|----------|-----------------|
| Equipment makers | TSMC, Samsung, Intel as primary customers | Diversification across foundries |
| Material suppliers | Qualification with multiple fabs | Single-source risk assessment |
| Substrate makers | Dependency on specific chipmakers | Revenue concentration by customer |
| EDA tools | Top 10 semiconductor companies | Recurring license revenue model |

**Rule:** Flag any company where a single customer represents >25% of revenue.

**7.1.3 Supply Chain Disruption Risk**

| Event Type | Impact | Companies Most Exposed |
|-----------|--------|----------------------|
| Natural disaster (earthquake, typhoon) | Fab shutdown, supply interruption | All Japan-based suppliers (earthquake zone) |
| Pandemic resurgence | Logistics delays, demand shock | Companies dependent on cross-border shipping |
| Energy crisis | Fab production slowdown | Taiwan-listed (TSMC water/power dependency) |
| Raw material shortage | Production bottleneck | Specialty chemical companies (rare materials) |

**7.1.4 Regulatory and Legal Risk**

| Risk Type | Description | Impact Assessment |
|-----------|-------------|------------------|
| Export controls | US/Japan/NL semiconductor equipment restrictions on China | Revenue at risk from China exposure |
| Antitrust | Merger challenges (Synopsys/Ansys type) | Deal failure, management distraction |
| Environmental regulation | PFAS restrictions affecting chemical suppliers | Reformulation cost, product obsolescence |
| IP litigation | Patent disputes across jurisdictions | Legal expense, injunction risk |

**7.1.5 Competition Risk**

| Dimension | Analysis Method |
|-----------|----------------|
| Market share trends | 3-year market share trajectory (growing, stable, shrinking) |
| New entrants | Monitor Chinese domestic equipment/material suppliers |
| Technology substitution | Alternative approaches that could bypass existing solutions |
| Commoditization pressure | Margin trend analysis (covered in moat scoring) |

**7.1.6 Management and Governance Risk**

| Factor | What to Check |
|--------|---------------|
| CEO tenure and track record | Stability of leadership team |
| Capital allocation history | Discipline in M&A, buybacks, dividends |
| Insider ownership | Alignment of management interests |
| Board independence | Governance quality (especially for Japanese companies with cross-holdings) |
| Succession planning | Key-person risk for founder-led companies |

**7.1.7 ESG and Sustainability Risks**

| Category | Risk Factors |
|----------|-------------|
| Environmental | Water usage in fabs, chemical waste, carbon footprint of equipment manufacturing |
| Social | Labor practices in supply chain, workforce availability (aging Japan demographics) |
| Governance | Cross-shareholdings (common in Japan), related-party transactions |

### 7.2 Geopolitical Risk (Critical for AI Supply Chain)

This is the single most important qualitative risk factor for the FE-Analyst universe.

**7.2.1 Taiwan Strait Tensions**

| Scenario | Probability Assessment | Companies Affected | Revenue Impact |
|----------|----------------------|-------------------|---------------|
| Status quo (manageable tension) | Monitor continuously | N/A | Baseline |
| Escalated rhetoric / military exercises | Elevated | TSMC, Unimicron, all Taiwan-listed | 5-15% discount warranted |
| Limited blockade | Low but non-zero | All companies with TSMC dependency | 30-50% revenue at risk for equipment/material suppliers |
| Full military conflict | Tail risk | Entire AI supply chain | Catastrophic; model as 80-100% loss scenario |

**Risk quantification for Taiwan exposure:**

```
Taiwan Risk Premium (basis points) = f(tension_level, company_exposure)

Where:
  company_exposure = % of revenue from Taiwan-based customers
                   + % of production located in Taiwan

  Tension levels:
    Normal:   +0 bps
    Elevated: +100-200 bps to discount rate
    High:     +300-500 bps to discount rate
    Critical: Do not rely on DCF; use scenario-based valuation only
```

**7.2.2 US-China Technology Export Controls**

| Control Type | Companies Affected | Revenue Impact |
|-------------|-------------------|---------------|
| Equipment restrictions (current) | ASML, Tokyo Electron, Lam Research, Applied Materials, KLA | 5-15% China revenue at risk |
| Expanded equipment restrictions | All semiconductor equipment companies | 10-25% revenue at risk |
| Materials restrictions | Specialty chemical suppliers | Varies by product |
| EDA tool restrictions | Synopsys, Cadence | China design revenue at risk |

**Risk quantification:**

```
Export Control Revenue at Risk = China Revenue * Probability of Restriction

For each company, document:
1. Total revenue from China (% and absolute)
2. Revenue from restricted entities (current)
3. Revenue from entities potentially restricted (stress case)
4. Alternative market potential to offset lost China revenue
```

**7.2.3 Japan-Korea Trade Tensions**

Historical precedent: 2019 Japan export controls on photoresists and hydrogen fluoride to Korea. Impact: Temporary disruption to Korean semiconductor production, accelerated Korean domestic supply development.

**Monitor for:** Recurring tensions that could affect material flows between Japan and Korean fabs.

**7.2.4 European Semiconductor Sovereignty (EU Chips Act)**

| Opportunity/Risk | Description |
|-----------------|-------------|
| Upside | Increased equipment demand from new European fabs |
| Risk | Potential forced technology transfer or local sourcing requirements |
| Timeline | 2025-2030 implementation horizon |

### 7.3 Currency Risk

**7.3.1 Currency Exposure by Country**

| Country | Currency Pair | Direction of Risk | Companies |
|---------|--------------|-------------------|-----------|
| Japan | JPY/USD | Weak JPY = higher USD-translated revenue BUT lower local purchasing power | Tokyo Electron, Lasertec, Advantest, Shin-Etsu, SUMCO, Disco, Screen, Ibiden, Shinko, Murata, TDK, Nidec, Hamamatsu, JSR, TOK, Fujifilm, Resonac, Ajinomoto |
| Taiwan | TWD/USD | TWD depreciation benefits TSMC exports | TSMC, Unimicron |
| Netherlands | EUR/USD | ASML reports in EUR; USD weakness benefits | ASML |
| South Korea | KRW/USD | KRW depreciation benefits memory exporters | SK Hynix |
| UK | GBP/USD | ARM reports in USD (US-listed) | ARM Holdings |

**7.3.2 Natural Hedging Assessment**

For each international company, evaluate natural hedging:

```
Currency Mismatch = Revenue Currency Mix - Cost Currency Mix

Example (Tokyo Electron):
  Revenue: ~30% JPY, ~70% USD/EUR/other
  Costs: ~80% JPY, ~20% other
  Mismatch: Significant -- weak JPY is a strong positive
```

**7.3.3 ADR vs. Local Share Analysis**

When analyzing ADRs:

| Factor | ADR | Local Share |
|--------|-----|-------------|
| Currency exposure for investor | USD-denominated | Local currency |
| Liquidity | Often lower | Usually higher on home exchange |
| Price discovery | May lag local trading | Primary |
| Dividend taxation | Withholding tax may differ | Country-specific |

**Rule:** Always calculate beta and volatility on the local share if the stock is primarily traded on a foreign exchange. ADR beta may be artificially elevated by currency volatility.

### 7.4 Liquidity Risk

**7.4.1 Liquidity Metrics**

| Metric | Formula | Threshold |
|--------|---------|-----------|
| Average Daily Volume (ADV) | 20-day average shares traded | Minimum 100,000 shares/day for coverage |
| Dollar Volume | ADV * Average Price | Minimum $1M/day for institutional analysis |
| Bid-Ask Spread | (Ask - Bid) / Midpoint | < 0.5% acceptable; > 1% = liquidity concern |
| Volume/Market Cap Turnover | ADV * Price / Market Cap | Low turnover = potential exit difficulty |

**7.4.2 Position Sizing Constraint**

```
Maximum Position = ADV_20day * Average_Price * 0.05

Rule: Position should represent no more than 5% of average daily dollar volume
      to ensure orderly exit within 1 trading day.
```

**7.4.3 Special Considerations for International Stocks**

| Issue | Description | Mitigation |
|-------|-------------|------------|
| ADR liquidity | Japanese/Taiwanese ADRs trade with much lower volume than local shares | Use local share liquidity for risk assessment |
| Trading hours overlap | Limited overlap between TSE/TWSE and US markets | Gap risk on overnight events |
| Holiday calendar mismatch | Japanese market closed on different holidays | Position adjustment before local holidays |

### 7.5 Cyclicality Risk

The semiconductor industry is deeply cyclical. Cyclicality assessment is essential for timing and position sizing.

**7.5.1 Semiconductor Cycle Phase Identification**

| Phase | Indicators | Duration (typical) | Investment Implication |
|-------|-----------|-------------------|----------------------|
| **Trough** | Inventory correction complete, utilization <70%, negative YoY growth | 2-4 quarters | Highest risk-adjusted entry point |
| **Recovery** | Book-to-bill >1.0, utilization rising, sequential growth | 3-6 quarters | Increasing exposure warranted |
| **Expansion** | Revenue acceleration, capacity additions, margin expansion | 4-8 quarters | Full position; monitor for peak signals |
| **Peak** | Record revenues, stretched valuations, overbuilding | 1-3 quarters | Begin reducing exposure |
| **Contraction** | Revenue declines, inventory builds, margin compression | 2-4 quarters | Defensive positioning |

**7.5.2 Leading Indicators to Monitor**

| Indicator | Source | Signal |
|-----------|--------|--------|
| SEMI book-to-bill ratio | SEMI.org | >1.0 expansion; <1.0 contraction |
| Fab utilization rates | Company earnings calls, IC Insights | >85% tight; <75% oversupply |
| Memory pricing (DRAM/NAND spot) | DRAMeXchange | Leading indicator for SK Hynix, Micron |
| Inventory-to-revenue ratio | Company financials | Rising = caution; falling = tightening |
| CapEx guidance from TSMC | TSMC quarterly earnings | Sets tone for equipment demand |
| Foundry lead times | Industry reports | Lengthening = strong demand |

**7.5.3 Revenue and Earnings Cyclicality Measurement**

```
Revenue Cyclicality = Max(Revenue YoY) - Min(Revenue YoY) over full cycle

For equipment companies (high cyclicality):
  Peak-to-trough revenue decline: typically 20-40%
  Peak-to-trough earnings decline: typically 40-70% (operating leverage)

For materials companies (moderate cyclicality):
  Peak-to-trough revenue decline: typically 10-25%
  Peak-to-trough earnings decline: typically 20-40%

For EDA companies (low cyclicality):
  Peak-to-trough revenue decline: typically 0-10%
  Recurring license model provides buffer
```

---

## 8. Scenario Analysis Framework

### 8.1 Three-Scenario Model (Required for Every Analysis)

Every stock analysis MUST include a three-scenario valuation. Scenarios should be mutually exclusive and collectively exhaustive.

#### 8.1.1 Bull Case (25% Default Probability)

**Construction methodology:**

1. Start with consensus revenue estimates
2. Apply upside assumptions:
   - AI spending accelerates beyond consensus by 15-30%
   - Company gains 2-5% market share
   - Margin expansion of 200-400 bps from pricing power and operating leverage
   - Favorable currency tailwind (for Japanese exporters: weaker JPY)
3. Apply appropriate valuation multiple (peer premium justified by growth)
4. Calculate implied price target

**AI supply chain specific bull case drivers:**

| Category | Bull Driver |
|----------|-------------|
| Equipment | Accelerated fab build-out (new fabs from TSMC, Intel, Samsung) |
| Materials | Node migration driving higher material content per wafer |
| Packaging | CoWoS/HBM capacity expansion faster than expected |
| EDA | AI-assisted chip design drives new license revenue |
| Networking | AI cluster interconnect spend exceeds hyperscaler guidance |
| Memory | HBM supply shortage persists, ASP expansion |

#### 8.1.2 Base Case (50% Default Probability)

**Construction methodology:**

1. Use consensus revenue and earnings estimates
2. Assume current competitive dynamics persist
3. Apply median historical valuation multiple
4. Account for normal semiconductor cyclicality
5. Use current forward guidance as anchor

**Key assumptions to document:**
- Revenue growth rate (consensus)
- Operating margin trajectory
- CapEx as % of revenue
- Working capital requirements
- Tax rate assumptions
- Share count (dilution/buyback)

#### 8.1.3 Bear Case (25% Default Probability)

**Construction methodology:**

1. Identify the most material downside risks
2. Quantify impact of each risk materializing:
   - AI spending slowdown: -20-40% from consensus
   - Customer loss: model specific revenue at risk
   - Pricing pressure: -200-400 bps margin compression
   - Geopolitical disruption: quantify revenue at risk
   - Technology shift: market share loss of 5-15%
3. Apply trough valuation multiple (historical cycle low)
4. Calculate floor price target

**AI supply chain specific bear case drivers:**

| Category | Bear Driver |
|----------|-------------|
| Equipment | AI CapEx pullback, fab deferrals, extended equipment lifetimes |
| Materials | Inventory correction, pricing pressure from Chinese alternatives |
| Packaging | CoWoS yield improvement reducing substrate demand per unit |
| EDA | Cloud computing model shift reducing upfront license revenue |
| Networking | AI scaling hits diminishing returns, reduced cluster sizes |
| Memory | HBM oversupply, DRAM price collapse |

### 8.2 Probability-Weighted Expected Value

```
Expected Value = (P_bull * Bull_Target) + (P_base * Base_Target) + (P_bear * Bear_Target)

Default weights:
  P_bull = 0.25
  P_base = 0.50
  P_bear = 0.25

Example:
  Bull target:  $200  (25%)
  Base target:  $150  (50%)
  Bear target:  $80   (25%)

  EV = (0.25 * 200) + (0.50 * 150) + (0.25 * 80) = $145

  Upside to EV from current price = (EV / Current_Price - 1) * 100%
```

**Probability Adjustment Guidelines:**

Adjust default probabilities when evidence strongly favors one scenario:

| Condition | Adjustment |
|-----------|-----------|
| Leading indicators confirm cycle peak | Increase bear to 35%, reduce bull to 15% |
| Major new growth catalyst confirmed | Increase bull to 35%, reduce bear to 15% |
| High uncertainty / binary event | Widen: bull 30%, base 30%, bear 40% |
| Stable, predictable business | Narrow: bull 20%, base 60%, bear 20% |

**Rule:** Never assign less than 10% probability to any scenario. Tail risks are always possible.

### 8.3 Stress Testing

Stress tests model extreme but plausible events. Every analysis should include at least three stress tests.

#### 8.3.1 Market Crash Scenario

```
Stock Impact = Beta * Market Decline

Scenario: SPY drops 30%
  Stock with Beta 1.5: Expected decline = 1.5 * 30% = 45%
  Stock with Beta 0.8: Expected decline = 0.8 * 30% = 24%

For position sizing:
  Maximum acceptable loss = Position Size * Beta * Stress Decline
```

**Important:** During actual crashes, correlations spike toward 1.0 and betas increase. Apply a "stress beta" multiplier of 1.2-1.5x to normal beta for crash scenarios.

#### 8.3.2 Interest Rate Shock

```
Scenario: +200 basis points to risk-free rate

Impact channels:
1. Valuation compression:
   DCF discount rate increases -> lower present value
   Growth stocks most affected (longer duration cash flows)

   Approximate price impact = -Duration * Rate Change
   For high-growth AI stocks (equity duration ~20-30 years):
     Impact = -25 * 0.02 = -50% (extreme case)
   For mature value stocks (equity duration ~10-15 years):
     Impact = -12 * 0.02 = -24%

2. Earnings impact:
   Higher borrowing costs for leveraged companies
   Reduced consumer/enterprise spending
   Stronger USD (negative for US importers, positive for Japanese exporters)
```

#### 8.3.3 Currency Shock

```
Scenario: +/-15% move in relevant currency pair

For Japanese companies (JPY/USD):
  15% JPY weakening:
    Revenue impact: Positive (USD-denominated sales worth more in JPY)
    Margin impact: Positive (costs largely in JPY)
    Estimated EPS impact: +10-20% for export-heavy companies (TEL, Advantest)

  15% JPY strengthening:
    Reverse of above
    Estimated EPS impact: -10-20% for export-heavy companies

For Taiwanese companies (TWD/USD):
  Similar dynamics but magnitude typically smaller (less TWD volatility)
```

#### 8.3.4 Customer Loss Scenario

```
Scenario: Largest customer reduces orders by 50%

Steps:
1. Identify largest customer (or segment) revenue contribution
2. Assume 50% reduction in that revenue
3. Model margin impact (operating leverage works in reverse)
4. Assess probability of replacement demand
5. Calculate revised EPS and fair value

Example:
  Company with 30% revenue from TSMC
  TSMC reduces orders 50%
  Revenue impact: -15%
  Operating profit impact: -25% to -35% (operating deleverage)
```

#### 8.3.5 Supply Chain Disruption

```
Scenario: Extended fab shutdown (earthquake, power crisis)

For Japan-based suppliers:
  Revenue loss: 1-3 months production (major earthquake scenario)
  Insurance recovery timeline: 6-12 months
  Market cap impact: Typically -15-30% initially, partial recovery within 6 months

For Taiwan-based companies:
  Earthquake or drought scenario
  TSMC contingency plans (geographic diversification to Japan, US, Europe)
  Impact assessment: Duration-dependent
```

#### 8.3.6 Export Control Expansion

```
Scenario: New restrictions on semiconductor equipment/materials to China

For each company, document:
  China revenue %: [specific number from latest filings]
  Revenue at risk under expanded controls: [estimated % of China revenue]

  Revenue impact = China_Revenue * Restriction_Probability * Revenue_Loss_Pct

  Example (Tokyo Electron):
    China revenue: ~25% of total
    Revenue at risk if expanded controls: ~50% of China revenue
    Impact: 25% * 0.50 = 12.5% total revenue at risk
```

---

## 9. Portfolio-Level Risk Analysis

### 9.1 Correlation Analysis

**Compute pairwise correlation matrix for all positions:**

```
Correlation Matrix:
  Input: Daily returns for all portfolio holdings
  Period: Same lookback as individual risk analysis (252 trading days)
  Method: Pearson correlation
```

**Interpretation guidelines:**

| Correlation | Classification | Diversification Benefit |
|-------------|---------------|------------------------|
| > 0.8 | Very high | Minimal; positions behave similarly |
| 0.5 - 0.8 | High | Limited diversification |
| 0.2 - 0.5 | Moderate | Meaningful diversification benefit |
| -0.2 - 0.2 | Low | Strong diversification benefit |
| < -0.2 | Negative | Hedge-like benefit |

**AI supply chain correlation warning:** Most companies in this universe are highly correlated (0.6-0.9) because they share common demand drivers (semiconductor CapEx, AI spending). True diversification within this universe is limited. Portfolio construction should acknowledge this.

### 9.2 Concentration Limits

| Dimension | Limit | Rationale |
|-----------|-------|-----------|
| Single stock | Max 15% of portfolio | Idiosyncratic risk management |
| Single sub-sector (e.g., equipment) | Max 35% of portfolio | Sub-sector concentration |
| Single country (e.g., Japan) | Max 50% of portfolio | Geographic/political risk |
| Single customer dependency | Monitor aggregate exposure to TSMC/Samsung | Supply chain concentration |

### 9.3 Factor Exposure Analysis

| Factor | Measurement | Target |
|--------|-------------|--------|
| Market (beta) | Portfolio-weighted average beta | 1.0-1.5 for growth portfolio |
| Size | Average market cap, small-cap weight | Document any small-cap tilt |
| Value vs. Growth | Weighted average P/E, P/B | Most AI supply chain is growth |
| Momentum | % of holdings above 200-day MA | Track for timing signals |
| Quality | Average ROE, debt/equity | Favor high-quality names |
| Currency | % exposed to JPY, TWD, EUR, KRW | Manage total FX exposure |

### 9.4 Portfolio VaR

```
Portfolio VaR considers correlations between positions:

Portfolio_VaR = sqrt(w' * Sigma * w) * z_alpha

Where:
  w = vector of position weights
  Sigma = covariance matrix of returns
  z_alpha = z-score for confidence level (1.645 for 95%)

Note: Portfolio VaR < sum of individual VaRs due to diversification
      (unless all correlations = 1.0)
```

---

## 10. Risk Communication Standards

### 10.1 Presentation Rules

1. **Always pair risk with return.** Never present expected returns without corresponding risk metrics. Every return projection must include volatility, drawdown potential, and risk-adjusted ratio.

2. **Use plain language alongside statistics.** Every statistical measure must be accompanied by a human-readable interpretation.

   - BAD: "VaR(95%) = -0.0342"
   - GOOD: "VaR(95%) = -3.42%, meaning on 95% of trading days, we expect the stock to lose no more than 3.42%. However, on the worst 5% of days, losses could be significantly larger."

3. **Provide historical context.** Anchor statistics to meaningful events.

   - "Current annualized volatility of 38% is in the 85th percentile of the stock's 5-year range. The last time volatility exceeded this level was during the 2022 semiconductor correction."

4. **Visualize key risk metrics.** Recommended charts:
   - Drawdown chart (cumulative, showing depth and duration)
   - Rolling volatility (30d, 60d, 90d overlaid)
   - Return distribution histogram with VaR/CVaR markers
   - Beta scatter plot (stock returns vs. benchmark returns)
   - Correlation heatmap (for portfolio analysis)

5. **Never label a stock as "low risk" if annualized volatility exceeds 25%.** This is a hard rule for the platform.

6. **Distinguish between recoverable and permanent risk.**
   - Recoverable: Cyclical drawdown, sentiment-driven sell-off, temporary supply disruption
   - Permanent: Technology obsolescence, customer permanent loss, regulatory ban, competitive displacement

### 10.2 Risk Disclosure Language

Every risk report must include:

```
RISK DISCLOSURE:
Historical risk metrics are backward-looking and may not predict future risk.
Extreme events (tail risks) can exceed historical ranges.
Semiconductor stocks are cyclical and can experience drawdowns of 30-50%+ during industry downturns.
International stocks carry additional currency and geopolitical risks.
This analysis does not constitute investment advice.
```

---

## 11. Output Format Specification

### 11.1 Standard Risk Analysis Output

Every risk analysis must produce the following structured output:

```
=================================================================
RISK ANALYSIS REPORT: {TICKER} ({COMPANY_NAME})
Generated: {TIMESTAMP}
Lookback Period: {PERIOD} | Benchmark: {BENCHMARK}
=================================================================

1. RISK METRICS TABLE
---------------------
| Metric              | Value     | Interpretation        |
|---------------------|-----------|-----------------------|
| Annualized Vol      | XX.XX%    | {LOW/MODERATE/HIGH}   |
| Beta (vs SPY)       | X.XX      | {interpretation}      |
| Adjusted Beta       | X.XX      | {interpretation}      |
| Sharpe Ratio        | X.XX      | {interpretation}      |
| Sortino Ratio       | X.XX      | {interpretation}      |
| Max Drawdown        | -XX.XX%   | {interpretation}      |
| VaR (95%)           | -X.XX%    | {interpretation}      |
| CVaR (95%)          | -X.XX%    | {interpretation}      |
| CVaR/VaR Ratio      | X.XX      | {tail risk assessment}|
| Current Drawdown    | -X.XX%    | {from ATH}            |

2. RISK SCORE
-------------
Base Score:         XX / 100
Adjustments:        {list each adjustment with reason}
Final Risk Score:   XX / 100
Risk Rating:        {LOW / MODERATE / HIGH / VERY HIGH}

3. SCENARIO ANALYSIS
--------------------
| Scenario   | Prob  | Target Price | Implied Return | Key Assumptions         |
|------------|-------|-------------|----------------|-------------------------|
| Bull Case  | XX%   | $XXX.XX     | +XX%           | {brief description}     |
| Base Case  | XX%   | $XXX.XX     | +XX%           | {brief description}     |
| Bear Case  | XX%   | $XXX.XX     | -XX%           | {brief description}     |
| **EV**     | 100%  | **$XXX.XX** | **+XX%**       | Probability-weighted    |

4. KEY RISK FACTORS (Ranked by Severity)
-----------------------------------------
1. {Risk Factor 1} - {CRITICAL/HIGH/MODERATE/LOW} severity
   Description: {brief}
   Potential Impact: {quantified if possible}
   Mitigation: {if any}

2. {Risk Factor 2} - ...
   ...

5. STRESS TEST RESULTS
-----------------------
| Scenario                    | Estimated Impact | Probability |
|-----------------------------|------------------|-------------|
| Market crash (SPY -30%)     | -XX%             | {p}         |
| Rate shock (+200bps)        | -XX%             | {p}         |
| Currency shock (JPY +15%)   | +/-XX% EPS       | {p}         |
| Customer loss (-50% orders) | -XX% revenue     | {p}         |
| Export control expansion     | -XX% revenue     | {p}         |
| Supply chain disruption     | -XX% (temp)      | {p}         |

6. RISK RATING SUMMARY
-----------------------
Overall Risk Rating: {LOW / MODERATE / HIGH / VERY HIGH}
Risk Score: XX / 100
Key Takeaway: {1-2 sentence summary of risk profile}

=================================================================
```

### 11.2 Abbreviated Output (For Dashboard/Screening)

When used in screening or dashboard context, provide a condensed format:

```json
{
  "ticker": "8035.T",
  "risk_score": 62,
  "risk_level": "MODERATE",
  "volatility": 0.2834,
  "beta": 1.32,
  "sharpe_ratio": 0.89,
  "sortino_ratio": 1.24,
  "max_drawdown": -0.2841,
  "var_95": -0.0298,
  "cvar_95": -0.0447,
  "scenario_ev": 155.00,
  "scenario_upside_pct": 12.3,
  "top_risk": "Export control expansion",
  "risk_flags": ["beta_elevated", "cyclical_peak_risk"]
}
```

---

## 12. Common Risk Assessment Mistakes

This section documents pitfalls that analysts and AI agents must actively avoid.

### 12.1 Statistical Pitfalls

| Mistake | Why It Is Wrong | Correct Approach |
|---------|----------------|-----------------|
| Assuming normal distribution of returns | Semiconductor stock returns are leptokurtic (fat tails) and often negatively skewed | Use CVaR alongside VaR; examine return distribution shape; note kurtosis |
| Using short lookback periods that miss crisis events | A 6-month lookback during a bull market produces artificially low risk metrics | Always use at least 252-day lookback; ideally 2 years; compare to 5-year metrics if available |
| Ignoring correlation spikes during market stress | Diversification benefit disappears when correlations converge toward 1.0 in crises | Use stressed correlation assumptions for crash scenarios (multiply normal correlation by 1.3-1.5, cap at 1.0) |
| Overfitting to historical data | Past regime may not repeat | Supplement historical analysis with forward-looking scenario construction |
| Treating volatility as the sole risk measure | Permanent capital loss is the real risk; a stock can have low volatility and still be a value trap | Combine volatility with fundamental quality, moat analysis, and qualitative assessment |

### 12.2 Analytical Pitfalls

| Mistake | Why It Is Wrong | Correct Approach |
|---------|----------------|-----------------|
| Not updating risk metrics after material events | Risk profile changes after earnings, M&A, regulatory action | Re-run risk analysis after any material event; never rely on stale metrics |
| Anchoring to historical risk when regime has changed | A stock that was low-risk in a growth phase may become high-risk approaching a cycle peak | Incorporate cycle phase and forward-looking indicators into risk assessment |
| Ignoring currency effects on international stocks | A Japanese stock may appear low-risk in JPY but high-risk in USD | Always note the currency basis of risk calculations; compute both local and USD metrics |
| Confusing correlation with causation in stress tests | Two stocks may be correlated without having a causal relationship | Focus on causal transmission mechanisms, not just statistical correlation |
| Neglecting liquidity risk for smaller names | Statistical risk metrics assume orderly markets | Apply liquidity discount for stocks with ADV below threshold |
| Survivorship bias in peer comparison | Only comparing to current survivors ignores failed competitors | Acknowledge survivorship bias; include historical drawdown data from delisted peers when available |

### 12.3 Communication Pitfalls

| Mistake | Why It Is Wrong | Correct Approach |
|---------|----------------|-----------------|
| Presenting risk in isolation from return | Risk without context is meaningless | Always pair risk metrics with expected return and risk-adjusted ratios |
| Using jargon without explanation | Non-specialist readers lose understanding | Define every statistical term on first use |
| Expressing false precision | A VaR of -3.2847% implies false accuracy | Round appropriately; communicate uncertainty ranges |
| Omitting tail risk discussion | VaR creates a false sense of safety | Always discuss what happens beyond VaR (use CVaR, stress tests) |

---

## 13. Procedure: Step-by-Step Risk Analysis Workflow

This section defines the exact sequence of operations for an AI agent or analyst performing a risk assessment.

### Step 1: Data Acquisition

```
Input:  ticker (str), benchmark (str, default "SPY"), period (str, default "2y")
Action: Call RiskAnalyzer.analyze(ticker, benchmark, period)
        This calls MarketDataClient.get_price_history() for both stock and benchmark
Output: Raw OHLCV DataFrames for stock and benchmark, aligned by date
```

**Validation checks:**
- Verify returned DataFrame is not empty
- Verify at least 200 trading days of data (for statistical significance)
- Check for data gaps (>5 consecutive missing days = data quality issue)
- For international stocks, verify the correct ticker suffix is used

### Step 2: Compute Quantitative Metrics

```
Action: Calculate all metrics from Section 5:
  1. Annualized volatility
  2. Beta vs. SPY (and sector ETF if applicable)
  3. Sharpe ratio
  4. Sortino ratio
  5. Maximum drawdown
  6. VaR (95%)
  7. CVaR (95%)

Additional (beyond core module):
  8. Rolling volatility (30d, 60d, 90d)
  9. Rolling beta (60d, 120d)
  10. Adjusted beta
  11. Drawdown duration
  12. CVaR/VaR ratio
  13. Current drawdown from ATH

Output: Dict of computed metrics
```

### Step 3: Compute Risk Score

```
Action: Apply scoring formula from Section 6
  1. Compute base score: (1 - volatility) * 100
  2. Apply peer-group normalization (if peer data available)
  3. Apply adjustment factors (beta, drawdown, Sharpe, Sortino penalties/bonuses)
  4. Clamp to [0, 100]
  5. Assign risk level label

Output: Risk score (0-100) and risk level (LOW/MODERATE/HIGH/VERY HIGH)
```

### Step 4: Qualitative Risk Assessment

```
Action: Evaluate all qualitative risk categories from Section 7
  1. Business risk assessment (technology, customer, supply chain, regulatory, competition, management, ESG)
  2. Geopolitical risk assessment (Taiwan, export controls, regional tensions)
  3. Currency risk assessment (exposure analysis, natural hedging)
  4. Liquidity risk assessment (ADV, bid-ask, position sizing limits)
  5. Cyclicality assessment (cycle phase, leading indicators)

Output: Ranked list of key risk factors with severity ratings
```

### Step 5: Scenario Analysis

```
Action: Construct three scenarios per Section 8
  1. Define bull case (25% probability) with specific price target
  2. Define base case (50% probability) with specific price target
  3. Define bear case (25% probability) with specific price target
  4. Calculate probability-weighted expected value
  5. Adjust probabilities if warranted by current conditions
  6. Run stress tests (minimum 3 scenarios)

Output: Scenario table, stress test results, probability-weighted EV
```

### Step 6: Compile and Communicate

```
Action: Assemble full risk report per Section 11 format
  1. Populate risk metrics table with interpretations
  2. Document risk score with adjustment breakdown
  3. Present scenario analysis in tabular format
  4. Rank and describe key risk factors
  5. Present stress test results
  6. Assign overall risk rating with summary narrative
  7. Include risk disclosure language

Output: Formatted risk analysis report (markdown or JSON)
```

### Step 7: Cross-Validate

```
Action: Perform sanity checks before finalizing
  1. Does the risk score align with the risk level label?
  2. Are the scenario targets internally consistent (bear < base < bull)?
  3. Does the EV imply reasonable upside/downside from current price?
  4. Are qualitative risks reflected in the scenario analysis?
  5. Is the risk rating consistent across quantitative and qualitative inputs?
  6. Compare against peer group risk profiles for reasonableness

Output: Validated, final risk report
```

---

## 14. Appendix: Reference Tables

### 14.1 Universe Companies by Risk Category (Typical Characteristics)

| Category | Typical Vol | Typical Beta | Typical MDD (Cycle) | Cyclicality |
|----------|------------|-------------|---------------------|-------------|
| Semiconductor Equipment (JP) | 30-50% | 1.2-2.0 | -35% to -55% | Very high |
| Semiconductor Equipment (US) | 25-40% | 1.1-1.6 | -30% to -50% | High |
| Semiconductor Equipment (NL) | 25-35% | 1.0-1.4 | -25% to -45% | High |
| Specialty Chemicals | 20-35% | 0.8-1.3 | -20% to -40% | Moderate-High |
| Advanced Packaging | 25-40% | 1.0-1.5 | -25% to -45% | High |
| Electronic Components | 20-30% | 0.8-1.3 | -20% to -35% | Moderate |
| EDA / Design IP | 20-30% | 1.0-1.3 | -20% to -35% | Low-Moderate |
| Networking | 25-40% | 1.1-1.6 | -25% to -45% | Moderate-High |
| Power / Cooling | 30-45% | 1.2-1.8 | -30% to -50% | Moderate-High |
| Foundry (TSMC) | 20-30% | 1.0-1.3 | -20% to -40% | Moderate |
| Memory (SK Hynix, Micron) | 35-50% | 1.3-2.0 | -40% to -60% | Very high |

### 14.2 Risk-Free Rate Reference

| Source | Current Proxy | Update Frequency |
|--------|--------------|-----------------|
| FRED (automated) | US 10-year Treasury yield | Auto-pull via `analysis.valuation.risk_free_rate: auto` |
| Fallback (hardcoded) | 4.0% annual (`risk_free_annual: float = 0.04`) | Manual update required |

**Note:** The 4% fallback in `risk.py` should be periodically validated against actual Treasury rates. When rates change significantly (>100 bps from hardcoded value), the fallback should be updated.

### 14.3 Scoring Weight in Composite

From `StockScorer.WEIGHTS`:

```
fundamental:  30%
valuation:    25%
technical:    20%
risk:         15%
sentiment:    10%
```

The risk score contributes 15% to the final composite score (0-100). A stock with a risk score of 0 (maximum volatility) incurs a 15-point drag on the composite. A stock with a risk score of 100 (minimum volatility) contributes 15 points to the composite.

---

## 15. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-01 | FE-Analyst Team | Initial release |

---

## 16. Related Documents

| Document | Description |
|----------|-------------|
| `configs/settings.yaml` | Platform configuration including risk parameters |
| `configs/ai_moat_universe.yaml` | Universe definition with moat scores |
| `src/analysis/risk.py` | Risk analysis implementation (RiskAnalyzer class) |
| `src/analysis/scoring.py` | Composite scoring implementation (StockScorer class) |
| `src/analysis/moat.py` | Moat analysis (MoatAnalyzer class) |
| `src/data_sources/market_data.py` | Market data client (yfinance integration) |
