# SOP-008: Quality Assurance & Peer Review

**Version:** 1.0
**Effective Date:** 2026-02-09
**Owner:** FE-Analyst Platform Team
**Classification:** Internal -- Mandatory Compliance
**Review Cycle:** Quarterly

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Definitions](#3-definitions)
4. [QA Philosophy: Defense in Depth](#4-qa-philosophy-defense-in-depth)
5. [Layer 1: Data Validation (Automated)](#5-layer-1-data-validation-automated)
6. [Layer 2: Calculation Verification](#6-layer-2-calculation-verification)
7. [Layer 3: Analytical Review (Human/AI)](#7-layer-3-analytical-review-humanai)
8. [Layer 4: Output Quality](#8-layer-4-output-quality)
9. [Pre-Analysis QA Checklist](#9-pre-analysis-qa-checklist)
10. [Post-Analysis QA Checklist](#10-post-analysis-qa-checklist)
11. [Peer Review Process](#11-peer-review-process)
12. [Common Errors Catalog](#12-common-errors-catalog)
13. [Regression Testing](#13-regression-testing)
14. [Escalation Procedures](#14-escalation-procedures)
15. [Moat Scoring QA](#15-moat-scoring-qa)
16. [Data Source-Specific Validation](#16-data-source-specific-validation)
17. [Continuous Improvement](#17-continuous-improvement)
18. [Audit Trail Requirements](#18-audit-trail-requirements)
19. [QA Output Format](#19-qa-output-format)
20. [Appendices](#20-appendices)

---

## 1. Purpose

Quality assurance is the final gate before analysis reaches decision-makers. This SOP establishes systematic procedures for validating analysis accuracy, identifying errors, and ensuring intellectual rigor across every layer of the FE-Analyst platform.

Even the best analysts make mistakes. Even the best code has edge cases. Even the best data sources have outages, gaps, and inconsistencies. QA processes exist to catch what individual diligence misses. This document codifies the standards, checklists, and review mechanisms that every analytical output must pass through before it can be acted upon.

**Non-negotiable principle:** No analysis, score, recommendation, or report leaves the platform without completing the QA process defined here. There are no shortcuts, no "quick looks," and no exceptions for urgency. Speed that sacrifices accuracy destroys capital.

---

## 2. Scope

This SOP applies to **all analytical outputs** produced by the FE-Analyst platform, including but not limited to:

- Individual stock analysis reports (generated via `python main.py analyze <TICKER>`)
- Multi-stock comparison reports (generated via `python main.py compare <TICKERS>`)
- Composite scores (0-100) and their component sub-scores
- Recommendations (STRONG BUY / BUY / HOLD / SELL / STRONG SELL)
- DCF valuations and intrinsic value estimates
- Moat scores and classifications for AI supply chain companies
- Technical signal outputs (RSI, MACD, MA crossover, Bollinger Band signals)
- Risk metrics (volatility, beta, Sharpe, Sortino, VaR, CVaR, max drawdown)
- Sentiment aggregations (news via FinBERT, Reddit via PRAW, analyst recommendations)
- Screening results (value, growth, momentum, dividend strategies)
- Data pipeline outputs (raw fetches, cached data, processed datasets)
- Any ad-hoc or custom analysis produced using platform components

**Out of scope:** This SOP does not cover infrastructure operations (server uptime, deployment), user interface testing, or marketing materials.

---

## 3. Definitions

| Term | Definition |
|------|-----------|
| **Composite Score** | Weighted aggregate of five dimension scores: Fundamental (30%), Valuation (25%), Technical (20%), Sentiment (10%), Risk (15%). Range: 0-100. Computed in `src/analysis/scoring.py` via `StockScorer.score()`. |
| **Sub-Score** | Individual dimension score (0-100) for Fundamental, Valuation, Technical, Sentiment, or Risk. |
| **Recommendation** | Action label derived from composite score: STRONG BUY (>=75), BUY (>=60), HOLD (>=45), SELL (>=30), STRONG SELL (<30). |
| **Moat Score** | Weighted aggregate of six competitive advantage dimensions for AI supply chain companies. Computed in `src/analysis/moat.py`. Classifications: WIDE MOAT (>=80), NARROW MOAT (>=60), WEAK MOAT (>=40), NO MOAT (<40). |
| **Neutral Fallback** | Score of 50 assigned when an analysis dimension fails (exception caught). Indicates data unavailability, not a neutral assessment. Must be flagged in reports. |
| **Cache TTL** | Time-to-live for cached data, configured in `configs/settings.yaml`. Ranges from 1 hour (news, daily prices) to 720 hours (SEC filings). |
| **Cross-Source Reconciliation** | Comparing the same metric (e.g., market cap, P/E) from two or more independent data sources to verify accuracy. |
| **Regression Baseline** | A set of known-good analysis outputs for benchmark companies, used to detect unintended changes when code is modified. |

---

## 4. QA Philosophy: Defense in Depth

Quality assurance for the FE-Analyst platform operates on four layers, each catching different categories of errors. No single layer is sufficient on its own. All four must pass before analysis is considered validated.

```
+------------------------------------------------------------------+
|                    LAYER 4: OUTPUT QUALITY                        |
|  Report formatting, label accuracy, completeness, presentation   |
+------------------------------------------------------------------+
|                    LAYER 3: ANALYTICAL REVIEW                     |
|  Internal consistency, thesis coherence, bias checks, contrarian  |
+------------------------------------------------------------------+
|                    LAYER 2: CALCULATION VERIFICATION              |
|  Unit tests, boundary tests, formula correctness, weight sums    |
+------------------------------------------------------------------+
|                    LAYER 1: DATA VALIDATION                       |
|  Schema checks, range validation, staleness, cross-source, nulls |
+------------------------------------------------------------------+
|                    RAW DATA SOURCES                               |
|  yfinance, Finnhub, SEC EDGAR, FRED, SimFin, Finviz, Reddit     |
+------------------------------------------------------------------+
```

**Error propagation principle:** A data error at Layer 1 will corrupt every subsequent layer. A calculation error at Layer 2 will produce a misleading analysis at Layer 3 and a polished-but-wrong report at Layer 4. This is why layers are ordered by precedence -- lower layers must pass first.

---

## 5. Layer 1: Data Validation (Automated)

Layer 1 validates that raw data from external sources is structurally sound, complete, current, and consistent before it enters any analysis pipeline.

### 5.1 Schema Validation

Every API response must be checked for the presence of expected fields before processing.

**Market Data (`MarketDataClient`):**
- OHLCV DataFrame must contain columns: `Open`, `High`, `Low`, `Close`, `Volume`
- Index must be a `DatetimeIndex`
- No duplicate dates in index
- Volume column must be integer or float, not string

**Fundamentals (`FundamentalsClient`):**
- `get_key_ratios()` must return a dict with all 16 expected keys (see `src/data_sources/fundamentals.py` lines 66-85)
- Keys: `ticker`, `pe_trailing`, `pe_forward`, `peg_ratio`, `pb_ratio`, `ps_ratio`, `ev_ebitda`, `profit_margin`, `operating_margin`, `roe`, `roa`, `debt_to_equity`, `current_ratio`, `quick_ratio`, `dividend_yield`, `payout_ratio`, `revenue_growth`, `earnings_growth`
- None values are acceptable (indicate data not available) but must be tracked
- `get_company_profile()` must include at minimum: `ticker`, `name`, `sector`

**Financial Statements:**
- Income statement, balance sheet, cash flow DataFrames: index must contain recognizable GAAP/IFRS line items
- "Free Cash Flow" must exist in cash flow statement for DCF analysis to proceed
- At least 2 years of annual data or 4 quarters of quarterly data

**Sentiment Data:**
- News articles: `headline` field must be non-empty string
- FinBERT output labels must be one of: `positive`, `negative`, `neutral`
- FinBERT scores must be in [0, 1] range
- Reddit posts: `score` must be integer, `upvote_ratio` must be in [0, 1]

### 5.2 Type Checking

| Field Category | Expected Type | Validation Rule |
|---------------|---------------|-----------------|
| Prices (Open, High, Low, Close) | float | Must be finite, non-negative |
| Volume | int or float | Must be non-negative |
| Ratios (P/E, P/B, etc.) | float or None | If present, must be finite |
| Percentages (margins, growth) | float or None | Typically in [-1.0, 10.0] range (flag outliers) |
| Dates | datetime | Must be parseable, must not be in the future |
| Tickers | string | Must match expected format (e.g., `^[A-Z0-9.]{1,10}$` or with `.T`, `.TW`, `.KS` suffixes) |
| Currency | string | Must be valid ISO 4217 code |

### 5.3 Range Validation

These ranges represent normal bounds. Values outside these ranges are not necessarily wrong, but must be flagged for manual review.

| Metric | Normal Range | Flag If |
|--------|-------------|---------|
| Stock price | > $0 | <= 0 or > $100,000 |
| P/E ratio (forward) | 0 to 200 | Negative (loss-making) or > 200 |
| P/B ratio | 0 to 100 | Negative (negative book value) or > 100 |
| Debt/Equity | 0 to 500 | > 500 (extreme leverage) or negative |
| Current ratio | 0 to 20 | > 20 (unusual) or exactly 0 |
| ROE | -1.0 to 1.0 | Outside this range (check for one-time items) |
| Revenue growth | -0.5 to 5.0 | > 5.0 (500% growth, verify) or < -0.5 |
| Annualized volatility | 0.05 to 1.5 | > 1.5 (extremely volatile) or < 0.01 |
| Beta | -2.0 to 5.0 | Outside this range |
| Sharpe ratio | -3.0 to 5.0 | Outside this range |
| Composite score | 0 to 100 | Outside [0, 100] (system error) |
| Sub-scores | 0 to 100 | Outside [0, 100] (system error) |
| Discount rate (DCF) | 0.04 to 0.20 | Outside this range |
| Terminal growth rate (DCF) | 0.0 to 0.04 | > 0.04 or >= discount rate |
| Margin of safety % | -200 to 200 | Outside this range (model instability) |
| Moat dimension scores | 0 to 100 | Outside [0, 100] |

### 5.4 Temporal Consistency

- All dates in price history must be in strictly chronological ascending order
- No future dates in any dataset (compare against `datetime.now()`)
- Trading day gaps must align with known market holidays and weekends
- Financial statement dates must be sequential (Q1 before Q2 before Q3 before Q4)
- Filing dates on SEC data must be after the period-end date they cover
- News article timestamps must be within the requested date range

### 5.5 Completeness Checks

| Data Type | Minimum Threshold | Rationale |
|-----------|-------------------|-----------|
| Annual price history (1y) | 230 trading days | ~252 trading days/year, allow for holidays and data gaps |
| 2-year price history | 460 trading days | Required for risk analysis default lookback |
| SMA-200 calculation | 200+ data points | Cannot compute 200-day moving average with less |
| Annual financial statements | 3 years minimum | Configured in `configs/settings.yaml` (`analysis.fundamental.min_years: 3`) |
| Quarterly financials | 4 quarters minimum | Full year comparison |
| News articles for sentiment | 5 articles minimum | Fewer produces unreliable aggregate sentiment |
| Reddit posts for sentiment | 10 posts minimum | Statistically insufficient below this |
| Peer companies | 3 peers minimum | Meaningful comparison requires breadth |

### 5.6 Cross-Source Reconciliation

When the same metric is available from multiple sources, compare them to detect data errors.

**Reconciliation pairs:**
| Metric | Source A | Source B | Tolerance |
|--------|----------|----------|-----------|
| Current price | yfinance | Finnhub quote | 2% (accounts for slight delay) |
| Market cap | yfinance `info` | Calculated (price x shares) | 5% |
| P/E ratio | yfinance `info` | Calculated (price / EPS from financials) | 10% |
| Revenue | yfinance income stmt | SimFin income stmt | 5% |
| Free Cash Flow | yfinance cash flow | SimFin cash flow | 5% |
| 10-Year Treasury | FRED DGS10 | Macro client fallback | 0.05 ppts |

**Procedure when reconciliation fails:**
1. Log the discrepancy with both values and their sources
2. Use the value from the primary source (per `configs/settings.yaml` data_sources priority)
3. Flag the metric in the analysis output with a data quality warning
4. If discrepancy exceeds 2x tolerance, halt and investigate before proceeding

### 5.7 Staleness Detection

Data must be within its configured cache TTL to be considered fresh. TTLs from `configs/settings.yaml`:

| Category | TTL | Implication |
|----------|-----|-------------|
| `price_daily` | 1 hour | Intraday re-fetch required for active analysis |
| `price_historical` | 24 hours | Daily refresh for technical analysis |
| `fundamentals` | 168 hours (7 days) | Weekly refresh; re-fetch after earnings |
| `sec_filings` | 720 hours (30 days) | Monthly check sufficient for 10-K/10-Q |
| `macro_data` | 24 hours | Daily for rates and indicators |
| `news` | 1 hour | Sentiment decays rapidly |

**Staleness rules:**
- If analysis uses data beyond its TTL, it must be re-fetched before proceeding
- The `DataCache` class (in `src/utils/cache.py`) automatically expires stale data by comparing `time.time() - path.stat().st_mtime` against `self.ttl_seconds`
- If a re-fetch fails (API down), document that stale data was used and its age
- Never silently serve stale data as fresh in a report

### 5.8 Null/NaN Tracking

- Count null/None values per metric per analysis run
- Null ratios > 30% of expected fields should trigger a data quality warning
- Never silently impute missing values -- if imputation is needed, it must be:
  - Explicitly documented in the report
  - Using a stated method (e.g., "median of peers" or "sector average")
  - Flagged so the reader knows it is estimated, not observed
- In `StockScorer.score()`, exception-caught dimensions fall back to score 50 -- this neutral fallback must be logged and flagged in the output, not treated as a legitimate score
- Track which sub-scores used fallback values in the final output dict

---

## 6. Layer 2: Calculation Verification

Layer 2 verifies that scoring formulas, valuation models, and risk calculations produce correct results given validated input data.

### 6.1 Unit Test Coverage Requirements

Every scoring function must have unit tests covering:

**Normal cases:**
- Typical values for a healthy large-cap company
- Typical values for a growth stock (high growth, high P/E)
- Typical values for a value stock (low P/E, high dividend)
- Typical values for a distressed company

**Boundary cases:**
- Score exactly at each recommendation threshold: 0, 30, 45, 60, 75, 100
- Sub-scores at exactly 0 and exactly 100
- Values at the boundary of each scoring tier (e.g., current_ratio at 1.0, 1.5)

**Edge cases:**
- Zero revenue, negative earnings, negative book value
- Infinite P/E (zero earnings)
- Missing data for one or more dimensions
- All dimensions fail (all fallback to 50)
- Extremely high growth rates (>1000%)
- Negative free cash flow in DCF

### 6.2 Composite Score Arithmetic Verification

The composite score formula must be verified on every run:

```
composite = (fundamental * 0.30) + (valuation * 0.25) + (technical * 0.20) + (sentiment * 0.10) + (risk * 0.15)
```

**Verification checks:**
1. **Weights sum to 1.0:** `sum(StockScorer.WEIGHTS.values()) == 1.0` -- verify this is true. Currently defined in `src/analysis/scoring.py` as `{"fundamental": 0.30, "valuation": 0.25, "technical": 0.20, "sentiment": 0.10, "risk": 0.15}`
2. **Weighted sum is correct:** Manually compute `sum(scores[k] * weights[k] for k in weights)` and compare to the returned `composite_score`
3. **Rounding consistency:** The composite is rounded to 1 decimal place via `round(composite, 1)`. Verify no truncation or floor/ceil is accidentally applied
4. **All five dimensions present:** Verify `scores` dict contains exactly the five keys matching `WEIGHTS` keys before computing composite
5. **Score clamping:** Each sub-score must be in [0, 100] before entering the weighted sum. Verify `max(0, min(100, ...))` is applied where appropriate

**Spot-check procedure (manual):**
Given sub-scores: Fundamental=72, Valuation=65, Technical=58, Sentiment=55, Risk=70

```
Expected composite = (72 * 0.30) + (65 * 0.25) + (58 * 0.20) + (55 * 0.10) + (70 * 0.15)
                   = 21.60 + 16.25 + 11.60 + 5.50 + 10.50
                   = 65.45
                   -> rounded to 65.5
Recommendation: BUY (65.5 >= 60, < 75)
```

### 6.3 Sub-Score Calculation Verification

#### 6.3.1 Fundamental Sub-Score

Defined in `src/analysis/scoring.py` lines 40-46:

```
health = fund_result["health"]["score"] / fund_result["health"]["max_score"]
growth = fund_result["growth"]["score"] / fund_result["growth"]["max_score"]
val_score = fund_result["valuation"]["score"] / fund_result["valuation"]["max_score"]
scores["fundamental"] = (health * 0.4 + growth * 0.3 + val_score * 0.3) * 100
```

**Verification points:**
- `health` max_score = 6 (from `_assess_financial_health`: current_ratio up to 2 + debt_to_equity up to 2 + ROE up to 2)
- `growth` max_score = 4 (from `_assess_growth`: revenue_growth up to 2 + earnings_growth up to 2)
- `valuation` max_score = 4 (from `_assess_valuation`: pe_forward up to 2 + peg_ratio up to 2)
- Internal weights sum: 0.4 + 0.3 + 0.3 = 1.0
- Result is multiplied by 100 to convert fraction to 0-100 scale
- Verify: a company scoring 6/6 health, 4/4 growth, 4/4 valuation yields exactly 100

#### 6.3.2 Valuation Sub-Score

Defined in `src/analysis/scoring.py` lines 52-56:

```
mos = dcf.get("margin_of_safety_pct", 0)
scores["valuation"] = max(0, min(100, 50 + mos))
```

**Verification points:**
- Margin of safety = `(intrinsic - price) / intrinsic * 100` (only if intrinsic > 0)
- Score = 50 + MoS, clamped to [0, 100]
- Undervalued by 30% -> score = 80 (50 + 30)
- Fairly valued (MoS = 0) -> score = 50
- Overvalued by 50% -> score = 0 (50 - 50, clamped at 0)
- Overvalued by 60% -> score = 0 (50 - 60 = -10, clamped at 0)
- Verify terminal value is not >80% of total enterprise value (if so, assumptions dominate and model is fragile)
- Verify discount_rate > terminal_growth (otherwise terminal value is negative/infinite)

#### 6.3.3 Technical Sub-Score

Defined in `src/analysis/scoring.py` lines 62-68:

```
buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
total = len(signals) or 1
scores["technical"] = (buy_count / total) * 100
```

**Verification points:**
- Signals come from `TechnicalAnalyzer.get_signals()` which produces up to 4 signals: `rsi`, `ma_crossover`, `macd`, `bbands`
- If all 4 are BUY -> score = 100
- If 2 of 4 are BUY -> score = 50
- If 0 of 4 are BUY -> score = 0
- If signals dict is empty, `total` defaults to 1, score = 0 (not division by zero)
- HOLD signals are counted as non-BUY (they do not contribute to the score)
- Verify that SELL signals and HOLD signals are both treated the same way (neither counts as BUY)

#### 6.3.4 Sentiment Sub-Score

Defined in `src/analysis/scoring.py` lines 74-77:

```
scores["sentiment"] = max(0, min(100, 50 + sent["overall_score"] * 100))
```

**Verification points:**
- `overall_score` is in [-1, 1] range (computed in `SentimentAnalyzer.analyze()`)
- Score = 50 + (overall_score * 100), clamped to [0, 100]
- Fully bullish (overall_score = 0.5) -> score = 100 (50 + 50)
- Neutral (overall_score = 0.0) -> score = 50
- Fully bearish (overall_score = -0.5) -> score = 0 (50 - 50)
- When no data, overall_score defaults to 0 (neutral), label = "NO DATA" -- this must be flagged

#### 6.3.5 Risk Sub-Score

Defined in `src/analysis/scoring.py` lines 82-87:

```
vol = risk.get("volatility", 0.3)
scores["risk"] = max(0, min(100, (1 - vol) * 100))
```

**Verification points:**
- Higher volatility = lower score (inverse relationship: risk score means "how safe")
- Volatility of 0.10 (low) -> score = 90
- Volatility of 0.30 (moderate) -> score = 70
- Volatility of 0.50 (high) -> score = 50
- Volatility of 1.00 -> score = 0
- Volatility > 1.0 -> score clamped at 0
- Volatility annualization: `returns.std() * sqrt(252)` -- verify 252 trading days used
- Default volatility fallback of 0.3 produces score of 70 -- this must be flagged as fallback

### 6.4 DCF Model Validation

The DCF model in `src/analysis/valuation.py` requires specific validation:

| Check | Rule | How to Verify |
|-------|------|--------------|
| Terminal growth < discount rate | `terminal_growth < discount_rate` | If violated, terminal value is negative (model breaks) |
| Terminal value proportion | TV should be <80% of enterprise value | `pv_terminal / enterprise_value < 0.80` |
| Discount rate range | 4% to 20% | Auto-calculated as risk_free + 0.06; verify risk_free is reasonable |
| Growth rate reasonableness | Aligned with historical and analyst estimates | Compare `growth_rate` (default 0.08) against actual revenue/earnings growth |
| FCF is positive | Negative FCF breaks standard DCF | If FCF < 0, DCF produces misleading intrinsic value |
| Shares outstanding | Must be current | Compare `yf.Ticker(ticker).info["sharesOutstanding"]` to a second source |
| Projection years | Default 5, range 3-10 | Longer projections increase terminal value weight |

### 6.5 Risk Metric Validation

| Metric | Formula Location | Verification |
|--------|-----------------|-------------|
| Annualized volatility | `RiskAnalyzer._annualized_volatility()` | `returns.std() * np.sqrt(252)` -- verify sqrt(252), not 365 |
| Sharpe ratio | `RiskAnalyzer._sharpe_ratio()` | `(excess.mean() / excess.std()) * sqrt(252)` with rf_daily = 0.04/252 |
| Sortino ratio | `RiskAnalyzer._sortino_ratio()` | Uses only downside deviation, not total std |
| Max drawdown | `RiskAnalyzer._max_drawdown()` | `(price - cummax) / cummax` then take min; result should be negative |
| Beta | `RiskAnalyzer._beta()` | `cov(stock, bench) / var(bench)` -- verify alignment of return series |
| VaR (95%) | `RiskAnalyzer._value_at_risk()` | 5th percentile of returns: `np.percentile(returns, 5)` |
| CVaR (95%) | `RiskAnalyzer._conditional_var()` | Mean of returns <= VaR |

### 6.6 Moat Score Arithmetic Verification

From `src/analysis/moat.py`:

```
MOAT_WEIGHTS = {
    "market_dominance": 0.20,
    "switching_costs": 0.15,
    "technology_lockin": 0.15,
    "supply_chain_criticality": 0.20,
    "pricing_power": 0.15,
    "barriers_to_entry": 0.15,
}
```

**Verification points:**
- Weights sum: 0.20 + 0.15 + 0.15 + 0.20 + 0.15 + 0.15 = 1.00
- `pricing_power` is computed quantitatively from margin data
- Other 5 dimensions use overrides from `configs/ai_moat_universe.yaml` or default to 50
- Classification thresholds: WIDE >= 80, NARROW >= 60, WEAK >= 40, NO < 40
- Verify that companies like ASML with all-100 overrides score at or near 100 (only pricing_power varies)
- Verify that the default (no overrides, pricing_power = 50) scores exactly 50

---

## 7. Layer 3: Analytical Review (Human/AI)

Layer 3 is the intellectual quality gate. It evaluates whether the analysis, taken as a whole, tells a coherent, defensible, and actionable story.

### 7.1 Internal Consistency Check

Every analysis must be reviewed for agreement between its own sections:

| Check | What to Look For |
|-------|-----------------|
| Score-recommendation alignment | A composite score of 75+ MUST produce STRONG BUY, not BUY. A score of 44 MUST produce SELL, not HOLD. Verify threshold application is exact. |
| Fundamental-valuation agreement | If fundamentals are strong (high sub-score) but valuation says OVERVALUED, the report must explicitly address why the market may be pricing in the strength. |
| Technical-fundamental divergence | A BUY from technicals with a SELL from fundamentals needs explanation. Which timeframe is each reflecting? |
| Risk-recommendation coherence | A STRONG BUY with VERY HIGH risk should raise flags. Is the risk-reward explicitly addressed? |
| Sentiment-thesis alignment | If sentiment is BEARISH but the recommendation is BUY, the report must explain the contrarian position. |
| Moat-fundamental consistency | A WIDE MOAT company should generally have strong fundamental metrics (high margins, high ROE). If not, explain why. |

### 7.2 Thesis Coherence

For every analysis, the reviewer must be able to answer:

1. **What is the investment thesis in one sentence?** If it cannot be stated concisely, the analysis lacks clarity.
2. **What are the 3 most important facts supporting this thesis?** They must come from the data, not assumptions.
3. **What would invalidate this thesis?** Every BUY has a bear case. Every SELL has a bull case. These must be stated.
4. **What is the time horizon?** Technical signals have short horizons; DCF has long horizons. Mixing them without acknowledgment is an error.
5. **What does the market appear to believe, and why do we disagree (if we do)?** If the recommendation aligns with consensus, what gives us additional confidence?

### 7.3 Assumption Review

All assumptions must be explicit, documented, and defensible:

| Assumption | Default Value | Reasonableness Check |
|-----------|---------------|---------------------|
| DCF growth rate | 8% (default in code) | Compare to historical revenue growth, analyst consensus, industry average |
| Terminal growth rate | 2.5% (default) | Should not exceed long-term GDP growth (~2-3% nominal) |
| Discount rate | Risk-free + 6% equity premium | Verify risk-free rate is current (from FRED), equity premium is within 4-7% range |
| Projection years | 5 (default) | Appropriate for most companies; extend to 7-10 for high-growth |
| Risk-free rate | Auto from FRED 10Y Treasury | Verify it is current (within 24 hours) and in reasonable range (1-6%) |
| Sharpe risk-free | 4% annual | Hardcoded -- verify against current 10Y Treasury |
| Volatility annualization | sqrt(252) | Standard -- verify no code uses sqrt(365) |

### 7.4 Peer Comparison Sanity

- Are the peer companies actually comparable? (Same industry, similar market cap range, similar business model)
- Peers are fetched via `FundamentalsClient.get_peers()` using Finnhub. Verify the returned list makes sense.
- For AI supply chain companies in `configs/ai_moat_universe.yaml`, use the companies within the same category as natural peers (e.g., compare Lasertec to ASML, not to Murata)
- Are all peers using the same fiscal period? (A March-end Japanese company vs. December-end US company requires alignment)
- Is the comparison using the correct ticker variant? (e.g., 8035.T for Tokyo Electron on TSE, TOELY for the ADR)

### 7.5 Cognitive Bias Checklist

Before finalizing any analysis, the reviewer must explicitly check for:

| Bias | Question | Mitigation |
|------|----------|-----------|
| **Anchoring** | Am I anchored to a previous price, valuation, or score? | Compare to intrinsic value, not recent price |
| **Confirmation bias** | Did I only seek evidence supporting my initial view? | List at least 2 pieces of contradicting evidence |
| **Recency bias** | Am I overweighting the latest quarter or news cycle? | Check 3-5 year trends, not just trailing 12 months |
| **Herding** | Am I agreeing with consensus because it feels safe? | State the consensus view and explain whether you agree or disagree and why |
| **Survivorship bias** | Is my screening universe missing failed/delisted companies? | Acknowledge limitations of screening on currently-listed stocks only |
| **Authority bias** | Am I trusting a single analyst or data source too much? | Cross-validate with at least one independent source |
| **Narrative fallacy** | Am I fitting a story to random data? | Ensure thesis is based on quantifiable metrics, not just a compelling narrative |
| **Loss aversion** | Am I reluctant to issue a SELL on a previous BUY? | Evaluate on current merit only; historical recommendations are irrelevant |

### 7.6 Contrarian Check

For every completed analysis:
- **STRONG BUY / BUY:** Write a 3-sentence bear case. What could go wrong? Is the market seeing something we're not?
- **SELL / STRONG SELL:** Write a 3-sentence bull case. What could go right? Is there a catalyst we are dismissing?
- **HOLD:** Is this genuinely a hold, or is it indecision? Is there a clear catalyst in either direction within 6-12 months?

### 7.7 Historical Back-Check

- Has this company been analyzed before? If so, compare the current score to the previous score.
- Was the previous recommendation accurate? (Did the price move in the predicted direction?)
- If the previous analysis was wrong, what was the cause? (Data error, model error, unpredictable event?)
- Document any pattern of systematic bias (e.g., consistently too bullish on growth stocks).

---

## 8. Layer 4: Output Quality

Layer 4 validates that the final deliverable is professionally formatted, accurately labeled, and complete.

### 8.1 Report Formatting Compliance

Reports are generated as markdown by `ReportGenerator._format_markdown()` in `src/reports/generator.py`.

**Format checks:**
- Title uses `# Stock Analysis: {TICKER}` format
- Generation timestamp is present and accurate
- Component scores table uses proper markdown table syntax with header separators
- All sections present: Composite Score, Recommendation, Component Scores, Fundamental Analysis, Valuation (DCF), Technical Signals, Risk Profile, Sentiment
- Disclaimer is present at the end
- No broken markdown (unclosed bold, misaligned tables, missing line breaks)

### 8.2 Data Label Accuracy

| Label | Verification |
|-------|-------------|
| Ticker symbol | Must match the analyzed company (not a peer, not a typo) |
| Company name | Must match the ticker (e.g., "Tokyo Electron" for 8035.T) |
| Sector/Industry | Must match the company's actual sector per yfinance |
| Period dates | Must reflect the actual data range used |
| Currency | Must be stated when dollar figures are presented |
| Score labels | "Fundamental", "Valuation", "Technical", "Sentiment", "Risk" must be spelled correctly and in the correct order |
| Weight labels | Must show correct weight for each dimension |

### 8.3 Chart/Visualization Accuracy

If visual outputs are generated (via scripts in `/scripts/`):
- Axes are labeled with units
- Data in charts matches data in text
- Time axes are in correct chronological order
- Legend entries match the plotted series
- No misleading truncated y-axes (e.g., starting a price chart at $90 instead of $0 for a $100 stock)

### 8.4 Completeness Verification

Every report must include:
- [ ] Composite score (single number, 0-100, 1 decimal)
- [ ] Recommendation label (one of the five standard labels)
- [ ] All five component sub-scores with weights
- [ ] Fundamental details: health score, growth score, valuation score, key reasons
- [ ] Valuation details: intrinsic value, current price, margin of safety, verdict
- [ ] Technical signals: at least RSI and MA crossover, preferably all four
- [ ] Risk profile: volatility, beta, Sharpe, max drawdown, VaR
- [ ] Sentiment: overall label and score, source breakdown
- [ ] Generation timestamp
- [ ] Disclaimer

### 8.5 JSON Output Verification

Raw JSON output (saved alongside markdown reports) must:
- Be valid JSON (parseable by `json.loads()`)
- Contain all fields present in the `StockScorer.score()` return dict
- Use `default=str` serialization for non-serializable types (datetime, numpy types)
- Be indented with 2 spaces for readability
- Filename format: `{TICKER}_{YYYYMMDD_HHMMSS}.json`

---

## 9. Pre-Analysis QA Checklist

Complete this checklist **before** starting any analysis. Any unchecked item is a blocker.

### 9.1 Data Source Health

- [ ] **yfinance responsive:** Test with `yf.Ticker("AAPL").info` -- returns data within 10 seconds
- [ ] **Finnhub API responsive** (if key configured): Test with a quote request
- [ ] **FRED API responsive** (if key configured): Test with `DGS10` series fetch
- [ ] **SEC EDGAR accessible** (if needed): Test company lookup
- [ ] **Reddit API accessible** (if key configured): Test subreddit search
- [ ] **Network connectivity:** General internet access confirmed

### 9.2 Market Data Currency

- [ ] **Market is open or data is from latest close:** If running on a weekend or holiday, acknowledge that data is from the prior trading day
- [ ] **No market-wide disruption:** Check for circuit breakers, exchange outages, or emergency halts
- [ ] **Pre-market / after-hours awareness:** If running outside regular hours, price data may not reflect latest information

### 9.3 Ticker Validation

- [ ] **Correct ticker format:** US stocks (e.g., `AAPL`), Japanese (e.g., `8035.T`), Taiwanese (e.g., `2330.TW`), Korean (e.g., `000660.KS`)
- [ ] **ADR vs. local listing clarity:** Using `TOELY` (ADR) or `8035.T` (TSE)? Analysis must be consistent with one or the other
- [ ] **No recent ticker change:** Check if the company has rebranded or changed its ticker (e.g., FB -> META)
- [ ] **Correct exchange:** Ensure `.T` is Tokyo, `.TW` is Taiwan, `.KS` is Korea

### 9.4 Corporate Event Awareness

- [ ] **No pending stock split:** If a split is announced but not yet effective, prices may be misleading
- [ ] **No pending merger/acquisition:** M&A targets trade at acquisition price, not intrinsic value
- [ ] **No pending delisting:** Delisting announcements make standard analysis invalid
- [ ] **Earnings date awareness:** If earnings are imminent (within 5 days), note that financials may be stale
- [ ] **Dividend ex-date awareness:** Recent ex-date can cause price drop unrelated to fundamentals

### 9.5 Fiscal Year Alignment

- [ ] **Fiscal year end identified:** Most US companies use December; Japanese companies often use March
- [ ] **Period alignment for comparisons:** When comparing a March-end company to a December-end company, the "latest annual" data is from different calendar periods
- [ ] **Quarterly alignment:** Q1 for a March-end company is April-June, not January-March

### 9.6 Environment Readiness

- [ ] **Correct Python environment active:** `venv` activated, all dependencies installed
- [ ] **API keys configured:** Required keys present in `.env` file
- [ ] **Cache state known:** Fresh analysis requires cache clear (`data/cache/` directory); routine analysis can use cached data within TTL
- [ ] **Sufficient disk space:** Cache writes and report saves require available storage

---

## 10. Post-Analysis QA Checklist

Complete this checklist **after** analysis is generated but **before** distribution. Any unchecked item requires remediation.

### 10.1 Score Verification

- [ ] **Composite score formula verified:**
  ```
  composite = 0.30 * fundamental + 0.25 * valuation + 0.20 * technical + 0.10 * sentiment + 0.15 * risk
  ```
  Manually compute from the five sub-scores and verify it matches the reported composite
- [ ] **Each sub-score is in [0, 100] range:** No sub-score below 0 or above 100
- [ ] **Recommendation matches score thresholds exactly:**
  - >= 75: STRONG BUY
  - >= 60 and < 75: BUY
  - >= 45 and < 60: HOLD
  - >= 30 and < 45: SELL
  - < 30: STRONG SELL
- [ ] **No fallback scores without documentation:** If any sub-score is exactly 50 due to exception fallback, it must be explicitly noted

### 10.2 Data Verification

- [ ] **Financial data matches latest available filings:** Compare key figures (revenue, net income, FCF) to the most recent 10-K or 10-Q
- [ ] **Price data is current:** The `current_price` in the valuation section should match a spot-check on a financial data site
- [ ] **Correct number of trading days in price history:** At least 230 for 1-year, 460 for 2-year
- [ ] **Technical indicators computed on sufficient data:** SMA-200 requires 200+ data points

### 10.3 Calculation Spot-Check

- [ ] **Manually verify 2-3 key ratios:** Pick 2-3 ratios from the report (e.g., P/E, D/E, ROE) and verify against a second source (e.g., Yahoo Finance website, Finviz)
- [ ] **DCF reasonableness check:**
  - Terminal value < 80% of enterprise value
  - Discount rate is in 4-20% range
  - Terminal growth < discount rate
  - Intrinsic value is within a plausible range (not $0, not $1,000,000)
- [ ] **Risk metric sanity:**
  - Volatility is positive
  - Beta is non-zero (unless truly uncorrelated)
  - Sharpe ratio sign matches return sign (positive return -> positive Sharpe)
  - Max drawdown is negative (or zero for never-declining stocks)
  - VaR is negative (represents a loss)

### 10.4 Consistency Check

- [ ] **Peer companies are actually comparable:** Review the peer list for sector/size appropriateness
- [ ] **No section contradicts another:** Bullish fundamentals + bearish recommendation = error (or needs explicit explanation)
- [ ] **Sentiment data is fresh enough:** News sentiment should be from within the last 7 days
- [ ] **All required output fields are populated:** No "N/A" for fields that should have data
- [ ] **Report sections don't use conflicting timeframes:** If fundamental analysis uses 2023 annual data, technical analysis shouldn't reference 2021 price data

### 10.5 Moat Score Verification (if applicable)

- [ ] **Moat weights sum to 1.0:** 0.20 + 0.15 + 0.15 + 0.20 + 0.15 + 0.15 = 1.00
- [ ] **Override values match `ai_moat_universe.yaml`:** If overrides were provided, verify they match the YAML configuration
- [ ] **Pricing power score derived from actual financials:** Not a hardcoded value
- [ ] **Classification matches threshold:** WIDE >= 80, NARROW >= 60, WEAK >= 40, NO < 40

### 10.6 Output File Verification

- [ ] **Markdown report saved to `reports/output/`** with correct filename format
- [ ] **JSON output saved alongside markdown** with matching timestamp
- [ ] **JSON is valid and parseable**
- [ ] **No sensitive data in reports** (no API keys, no personal information)

---

## 11. Peer Review Process

### 11.1 Self-Review (Minimum Standard -- Always Required)

Self-review is the absolute minimum QA for any analysis. It must be completed even if no other reviewer is available.

**Procedure:**

1. **Cool-down period:** Wait at least 15 minutes after generating the analysis before reviewing. Fresh eyes catch errors that fatigue misses.

2. **Full re-read:** Read the entire report from beginning to end, as if you are seeing it for the first time. Do not skim.

3. **Skeptical PM test:** Ask yourself: "If I had to defend this analysis in front of a skeptical portfolio manager, what would they challenge?" Write down the top 3 challenges and verify that the analysis addresses them.

4. **Independent data verification:** Take the 3 most important data points in the analysis (e.g., current P/E, revenue growth rate, free cash flow) and verify them against an independent source (Yahoo Finance website, company IR page, SEC filing).

5. **Logic chain test:** Read just the conclusion/recommendation. Then read just the supporting evidence. Does the conclusion follow logically from the evidence? Would someone with no prior opinion arrive at the same conclusion from this evidence?

6. **Bias self-check:** Go through the cognitive bias checklist in Section 7.5. For each bias, honestly assess whether it may have influenced the analysis.

7. **Score recalculation:** Take the five sub-scores, manually compute the weighted sum, and verify it matches the reported composite. Verify the recommendation matches the threshold.

### 11.2 Cross-Review (Best Practice -- Required for Publication)

Cross-review involves a second analyst independently evaluating the analysis. Required before any analysis is published or distributed externally.

**Reviewer responsibilities:**

1. **Methodology application review:** Does the analysis correctly apply the scoring methodology? Are the right metrics feeding into the right sub-scores?

2. **Independent data verification:** The reviewer must independently fetch at least 3 key data points and compare to the analysis. Use a different data source if possible (e.g., if the analysis used yfinance, the reviewer checks Finviz or the company's investor relations page).

3. **Assumption challenge:** Identify the top 3 assumptions in the analysis (growth rate, discount rate, peer group, moat durability, etc.) and challenge each:
   - Is this assumption explicitly stated?
   - What evidence supports it?
   - What would happen if it's wrong by 20%?
   - Is there a more conservative/aggressive assumption that is equally valid?

4. **Peer comparison verification:** Independently verify that the peer companies are appropriate. Check that they are in the same industry, similar in size, and that the comparison uses the correct time period.

5. **Risk section adequacy:** Does the risk section address the ACTUAL key risks for this company, or does it just report generic risk metrics? For example:
   - A semiconductor company should address geopolitical risk (China/Taiwan)
   - A high-growth company should address execution risk
   - A highly leveraged company should address interest rate risk
   - An AI supply chain company should address demand cyclicality

6. **Written feedback:** The reviewer must provide written feedback noting:
   - Any errors found (data, calculation, or analytical)
   - Any concerns about assumptions or methodology
   - Any suggestions for improvement
   - Explicit approval or rejection

### 11.3 Devil's Advocate Review (Required for High-Conviction Calls)

A Devil's Advocate review is required when:
- The composite score is >= 85 (very strong conviction BUY)
- The composite score is < 20 (very strong conviction SELL)
- The recommendation contradicts consensus by 2+ categories (e.g., we say STRONG BUY, consensus is SELL)
- The analysis is on a company with > $1B market cap impact potential

**Procedure:**

1. **Assign a contrarian:** One person is specifically tasked with arguing the opposite position. Their job is NOT to be balanced -- it is to be maximally skeptical.

2. **For every BUY/STRONG BUY, the Devil's Advocate must answer:**
   - What is the single most likely way an investor loses money on this position?
   - What data point, if wrong, would invalidate the entire thesis?
   - Is the market already pricing in the bullish thesis (making it a crowded trade)?
   - What comparable company looked this good before declining 50%+?
   - Is the valuation margin of safety genuine, or is it based on aggressive growth assumptions?

3. **For every SELL/STRONG SELL, the Devil's Advocate must answer:**
   - What catalyst could cause a re-rating upward?
   - Is the bad news already priced in?
   - Is there hidden value (IP, real estate, brand) not captured in financial statements?
   - What activist investor or strategic acquirer might see value here?
   - Is the industry about to inflect positively?

4. **For every HOLD, the Devil's Advocate must answer:**
   - Is this a genuine hold, or does the analyst lack conviction?
   - What catalyst would move this to BUY or SELL within 6 months?
   - Is the opportunity cost of holding justified?

5. **Resolution:** The original analyst must respond to each Devil's Advocate point in writing. If the contrarian argument is valid and not adequately addressed, the recommendation may need revision.

---

## 12. Common Errors Catalog

This section catalogs the most frequently encountered errors, organized by category, along with detection methods and impact assessment.

### 12.1 Data Errors

| # | Error | How to Detect | Impact | Severity |
|---|-------|--------------|--------|----------|
| D-01 | Wrong ticker variant (e.g., `8035` instead of `8035.T`) | Company name in response doesn't match expected | Complete analysis invalid -- wrong company | CRITICAL |
| D-02 | ADR vs local listing mismatch | Per-share metrics differ by ADR ratio | Incorrect valuations, misleading peer comparisons | HIGH |
| D-03 | Stale financial data | Compare filing dates to analysis date | Outdated conclusions, missed earnings changes | HIGH |
| D-04 | Currency mismatch | Verify currency field in API response; JPY vs USD | Ratios off by orders of magnitude | CRITICAL |
| D-05 | Split-unadjusted prices | Compare recent price to known market price | Technical analysis invalid, P/E distorted | CRITICAL |
| D-06 | Missing quarters in financial data | Count data points vs expected | Incomplete trend analysis, wrong growth rates | MEDIUM |
| D-07 | Weekend/holiday stale prices | Check if last trading date is current | Risk metrics may be slightly off | LOW |
| D-08 | API returning default/placeholder data | Check for suspiciously round numbers or zeros | False confidence in bogus data | HIGH |
| D-09 | Timezone misalignment on dates | Verify timezone of datetime objects | Off-by-one-day errors in date-sensitive analysis | MEDIUM |
| D-10 | Delisted or suspended ticker | API returns empty or error | Analysis cannot be completed | CRITICAL |

### 12.2 Calculation Errors

| # | Error | How to Detect | Impact | Severity |
|---|-------|--------------|--------|----------|
| C-01 | Wrong weight in composite score | `sum(WEIGHTS.values()) != 1.0` | Incorrect composite score | CRITICAL |
| C-02 | Double-counting metrics | Review which ratios feed into each sub-score | Inflated or deflated dimension scores | HIGH |
| C-03 | Sign errors in scoring | Verify: higher metric = higher score for positive indicators | Reversed signals | CRITICAL |
| C-04 | Division by zero | Check for zero denominators (zero earnings for P/E, zero variance for beta) | Runtime errors, NaN propagation | HIGH |
| C-05 | Annualization errors (sqrt(252)) | Verify factor matches trading-day convention | Volatility, Sharpe, Sortino off by sqrt(252) | HIGH |
| C-06 | Terminal value domination in DCF | `pv_terminal / enterprise_value > 0.80` | Valuation is essentially a guess about long-term growth | MEDIUM |
| C-07 | Rounding errors accumulating | Compare rounded vs unrounded composite | Up to 0.5 point deviation per rounding step | LOW |
| C-08 | Integer vs float division | Python 3 handles this, but verify in edge cases | Truncated results | MEDIUM |
| C-09 | Incorrect period alignment in growth calculation | Verify period-over-period logic | Growth rates computed from wrong base periods | HIGH |
| C-10 | VaR percentile direction | `np.percentile(returns, 5)` for 95% VaR | Wrong VaR sign or magnitude | HIGH |

### 12.3 Analytical Errors

| # | Error | How to Detect | Impact | Severity |
|---|-------|--------------|--------|----------|
| A-01 | Comparing different fiscal periods | Verify period alignment between company and peers | Misleading comparisons | HIGH |
| A-02 | Using peak earnings for cyclical P/E | Check where the company is in its cycle | Value trap -- cheap P/E on peak earnings | HIGH |
| A-03 | Ignoring stock-based compensation | Review cash flow adjustments | Overstated FCF, overstated intrinsic value | MEDIUM |
| A-04 | Survivorship bias in screening | Check universe completeness | Biased screening results | MEDIUM |
| A-05 | Forward-looking data bias | Verify data availability dates in backtesting | Backtesting invalidation | CRITICAL |
| A-06 | Ignoring off-balance-sheet items | Review 10-K footnotes for operating leases, SPEs | Understated leverage | MEDIUM |
| A-07 | Misclassifying one-time items | Check for restructuring charges, asset sales | Distorted earnings trajectory | MEDIUM |
| A-08 | Using nominal growth without inflation adjustment | Compare to real GDP growth | Overstated terminal growth rate | LOW |
| A-09 | Ignoring market regime | Bull market biases all technicals positive | Overly bullish technical scores | MEDIUM |
| A-10 | Confusing reported vs operating vs adjusted EPS | Verify which EPS figure is used in P/E | Inconsistent valuation | HIGH |

### 12.4 Output Errors

| # | Error | How to Detect | Impact | Severity |
|---|-------|--------------|--------|----------|
| O-01 | Wrong company name in report header | Compare ticker to name | Confusing, unprofessional | MEDIUM |
| O-02 | Broken markdown table formatting | Render the markdown and visually inspect | Unreadable tables | LOW |
| O-03 | Missing report section | Check against completeness checklist (Section 8.4) | Incomplete analysis | MEDIUM |
| O-04 | Stale timestamp | Compare generation timestamp to current time | Misleading about data freshness | LOW |
| O-05 | JSON serialization failure | Attempt `json.loads()` on saved JSON | Report data cannot be programmatically consumed | MEDIUM |

---

## 13. Regression Testing

### 13.1 Purpose

Regression testing ensures that code changes to scoring models, data pipelines, or report generation do not introduce unintended changes to analytical outputs.

### 13.2 Benchmark Company Set

Maintain a set of 5 benchmark companies with diverse characteristics:

| # | Ticker | Characteristics | Why Selected |
|---|--------|----------------|-------------|
| 1 | AAPL | US large-cap, stable, high margins | Baseline for well-covered US equities |
| 2 | ASML | EU company, monopoly position, high moat | Tests international data, extreme moat scores |
| 3 | 8035.T | Japanese listing, `.T` suffix, March fiscal year | Tests non-US ticker handling, fiscal year alignment |
| 4 | MU | Cyclical semiconductor, volatile | Tests cyclical analysis, higher risk scores |
| 5 | A small-cap or recent IPO (updated quarterly) | Limited data, sparse coverage | Tests edge cases, missing data handling |

### 13.3 Regression Testing Procedure

**When to run:** Before merging any code change that touches:
- `src/analysis/*.py` (scoring logic)
- `src/data_sources/*.py` (data retrieval)
- `src/reports/generator.py` (output formatting)
- `configs/settings.yaml` (configuration changes)
- `configs/ai_moat_universe.yaml` (moat overrides)

**Procedure:**

1. **Run baseline:** Execute full analysis on all 5 benchmark companies using the CURRENT code. Save results.
2. **Apply changes:** Switch to the new code branch.
3. **Run comparison:** Execute full analysis on all 5 benchmark companies using the NEW code. Save results.
4. **Compare outputs:**

| Comparison | Threshold | Action |
|-----------|-----------|--------|
| Composite score change | < 3 points | Acceptable, document |
| Composite score change | 3-10 points | Investigate, may be acceptable if justified |
| Composite score change | > 10 points | BLOCK -- must be investigated and explicitly justified |
| Sub-score change | < 5 points | Acceptable, document |
| Sub-score change | > 10 points | Investigate, may indicate formula change |
| Recommendation change | Any change | BLOCK -- must be investigated and explicitly justified |
| New NaN or None values | Any new nulls | BLOCK -- data pipeline regression |
| Report section missing | Any missing | BLOCK -- formatting regression |

5. **Document results:** Record the comparison in a regression test log with:
   - Date and code version (git commit hash)
   - All score differences
   - Justification for any accepted differences
   - Approval sign-off

### 13.4 Versioned Baselines

- Store baseline results in `data/regression_baselines/` (not checked into git if they contain API data)
- Filename format: `baseline_{TICKER}_{YYYYMMDD}_{git_commit_short}.json`
- Refresh baselines quarterly or when intentional methodology changes are approved
- Never overwrite baselines -- create new ones and keep the old ones for historical comparison

### 13.5 Automated Regression (Future)

Target: implement `pytest` test suite that:
- Loads baseline JSONs
- Runs analysis on benchmark tickers
- Compares scores within tolerance
- Fails the test if any threshold is exceeded
- Integrates with CI/CD pipeline

---

## 14. Escalation Procedures

### 14.1 Score Anomaly (>20 Point Swing Day-Over-Day)

A composite score change of >20 points between consecutive analysis runs for the same company warrants investigation.

**Escalation steps:**
1. **Investigate data quality first:** Did a data source return different data? Check cache freshness, API response content.
2. **Check for corporate events:** Earnings report, acquisition announcement, stock split, dividend change, analyst upgrade/downgrade.
3. **Compare sub-scores:** Identify which dimension(s) caused the swing. A 20-point composite swing likely means one sub-score moved 40+ points.
4. **Verify with second data source:** If the swing is driven by a single data point, verify it independently.
5. **If legitimate:** Document the cause and proceed. Volatile stocks (e.g., Lasertec, Micron) may have genuine 20+ point swings.
6. **If data error:** Correct the data, re-run analysis, and document the error in the error log.

### 14.2 Cross-Source Disagreement (>10% on Same Metric)

When two data sources report the same metric with >10% discrepancy:

1. **Identify the metric and sources:** e.g., yfinance says P/E is 25.3, SimFin says P/E is 29.1
2. **Check calculation methodology:** Different sources may use TTM vs forward, diluted vs basic, GAAP vs non-GAAP
3. **Check timing:** One source may have updated with the latest quarter, the other may not
4. **Use authoritative source:** Per `configs/settings.yaml`, primary sources take precedence
5. **Document the discrepancy:** Include both values and the resolution in the analysis output
6. **If the discrepancy exceeds 2x tolerance (>20%):** Halt analysis for that metric and investigate further

### 14.3 Model Output Outside Historical Range

When a metric or score falls outside all previously observed values:

1. **Verify the data:** Is the input data correct?
2. **Verify the calculation:** Is the formula computing correctly?
3. **Assess whether the result is plausible:** Unprecedented does not mean wrong. COVID-era volatility produced historically unprecedented VaR values. AI boom produces unprecedented revenue growth for some companies.
4. **Document and justify:** If the result is valid, include explicit commentary explaining why it is outside historical norms.
5. **Consider model limitations:** If the model is not designed for this range (e.g., DCF with negative FCF), state the limitation.

### 14.4 Conflicting Signals Between Dimensions

When different analysis dimensions produce contradictory signals (e.g., Fundamental says BUY, Technical says SELL):

1. **Acknowledge the conflict explicitly in the report.** Do not hide it.
2. **Assess the reliability of each dimension for this specific case:**
   - Technical signals are more reliable for liquid, widely-traded stocks
   - Fundamental signals are more reliable for stable, established businesses
   - Sentiment signals are more reliable during periods of extreme market emotion
   - Risk metrics are more reliable with longer lookback periods
3. **Consider the timeframe:** Technical and sentiment operate on shorter timeframes than fundamental and valuation
4. **State which dimension you weight more heavily for this specific case and why**
5. **The composite score already mathematically resolves conflicting signals via weights.** The commentary should explain the composite, not override it.

### 14.5 Complete Data Source Failure

When a primary data source is entirely unavailable:

1. **Use fallback source** per `configs/settings.yaml` data_sources priority
2. **If no fallback available:** Use neutral fallback score (50) and clearly flag it
3. **If multiple sources fail:** Consider postponing the analysis rather than producing a low-quality output
4. **Log the failure:** Record the source, timestamp, error message, and fallback used
5. **Never present a fallback-heavy analysis as high-confidence:** If >= 2 of 5 dimensions used fallback scores, add a prominent data quality warning

---

## 15. Moat Scoring QA

Special QA procedures for the competitive moat analysis used on AI supply chain companies tracked in `configs/ai_moat_universe.yaml`.

### 15.1 Universe Completeness

- The moat universe currently tracks 60+ companies across 8 categories: Semiconductor Equipment, Chemicals & Materials, Packaging & Substrates, Electronic Components, EDA & Chip Design, Networking, Power & Cooling, Foundry & Memory
- **Quarterly review:** Verify no significant AI supply chain company is missing from the universe
- **Verify entries are current:** Check for acquisitions (JSR was acquired by JIC), delistings, or major business model changes that would affect moat scores

### 15.2 Override Validation

Moat dimension scores in `ai_moat_universe.yaml` are qualitative overrides (0-100). They must be:

- **Sourced and justified:** Each override should be traceable to a market share report, industry analysis, or documented competitive assessment
- **Consistent within categories:** Companies in the same category should have relatively comparable scores for similar competitive positions. If Lasertec has `market_dominance: 100` (monopoly), no other non-monopoly company in that category should also be 100.
- **Periodically re-validated:** Qualitative assessments can become stale. Require annual re-assessment of all overrides.
- **Internally consistent:** A company with `switching_costs: 100` should logically also have high `technology_lockin` and `barriers_to_entry`

### 15.3 Pricing Power Score Verification

The `pricing_power` dimension is the only quantitatively-derived moat dimension (from `MoatAnalyzer._score_pricing_power()`).

**Verification:**
- Base score starts at 50
- Gross margin > 40%: +25; > 25%: +15; > 15%: +5
- Operating margin > 30%: +15; > 20%: +10; > 10%: +5
- Margin trend expanding > 3%: +10; contracting > 3%: -10
- Max score: 100, min score: 0
- Verify the margin values used match the company's actual reported margins
- Verify the trend direction is computed correctly (recent minus oldest, not the reverse)

### 15.4 Cross-Company Comparison Sanity

When comparing moat scores across the universe:
- The top-scoring companies should be known monopolies/duopolies (ASML, Lasertec, Ajinomoto ABF)
- No commodity supplier should score above WIDE MOAT (>=80) without strong justification
- Scores within a category should form a reasonable ranking that aligns with known market positions

---

## 16. Data Source-Specific Validation

### 16.1 yfinance

| Check | Description |
|-------|-------------|
| `info` dict completeness | Some tickers return sparse `info` dicts. Check for None values. |
| Historical data gaps | yfinance may silently return fewer data points than expected |
| Currency consistency | Japanese stocks return JPY; ADRs return USD. Verify which. |
| `.info` vs `.fast_info` | `fast_info` has fewer fields but is faster. Know which is being used. |
| Rate limiting | yfinance can throttle aggressive requests. Watch for HTTP 429 errors. |

### 16.2 Finnhub

| Check | Description |
|-------|-------------|
| API key validity | Expired or rate-limited keys return empty results, not errors |
| Peer list quality | `company_peers()` can return ETFs, indices, or loosely related companies |
| News freshness | Verify `datetime` field in news responses is recent |
| Quote staleness | Free tier may have 15-minute delay |

### 16.3 FRED (Federal Reserve Economic Data)

| Check | Description |
|-------|-------------|
| Series availability | Some series are discontinued or renamed |
| Publication lag | GDP data lags by ~1 month; employment by ~1 week |
| Revision awareness | Economic data is frequently revised. Initial release != final value |
| Missing recent data point | Latest observation may not be the current period |

### 16.4 SEC EDGAR

| Check | Description |
|-------|-------------|
| Non-US companies | SEC filings only available for US-listed companies (including ADRs filing with SEC) |
| XBRL availability | Older filings or smaller companies may lack XBRL |
| Filing delay | 10-K filings are due 60 days (accelerated filers) to 90 days after fiscal year end |
| Restatements | Check for amended filings (10-K/A) that supersede original |

### 16.5 FinBERT (Sentiment Model)

| Check | Description |
|-------|-------------|
| Input length | Truncated to 512 tokens. Longer headlines lose context. |
| Financial domain | FinBERT is trained on financial text. Non-financial news may produce unreliable labels. |
| Neutral bias | FinBERT tends to classify ambiguous text as neutral. Scores may cluster around 0. |
| Batch consistency | Running the same text twice should produce identical results (model is deterministic with same seed) |

### 16.6 Reddit (PRAW)

| Check | Description |
|-------|-------------|
| Bot/spam filtering | Reddit posts include spam, bots, and memes. Raw scores may be misleading. |
| Subreddit selection | Default `wallstreetbets` is retail-focused and high-noise. Consider `investing` or `stocks` for different perspective. |
| Ticker ambiguity | Short tickers (e.g., `MU`, `ARM`) may match unrelated posts |
| Sample size | 50 posts (default limit) may be insufficient for statistical reliability |

---

## 17. Continuous Improvement

### 17.1 Recommendation Accuracy Tracking

Track the accuracy of recommendations over time:

**Hit rate analysis framework:**

| Time Horizon | How to Measure |
|-------------|----------------|
| 1 month | Did STRONG BUY outperform SPY by >3%? |
| 3 months | Did the recommendation direction hold? |
| 6 months | Did the fundamental thesis play out? |
| 12 months | Was the recommendation validated by hindsight? |

**What to track:**
- Total recommendations issued per category (STRONG BUY, BUY, HOLD, SELL, STRONG SELL)
- Percentage that achieved their implied return within 12 months
- Average return of each recommendation category vs benchmark (SPY)
- Hit rate (% of correct directional calls)

### 17.2 Post-Mortem Analysis

**For significant misses (recommendation was wrong by 2+ categories):**

1. **Identify the miss:** Which recommendation, which ticker, what actually happened?
2. **Root cause analysis:**
   - Was the data wrong? (Data error)
   - Was the model wrong? (Calculation/methodology error)
   - Was the analysis wrong? (Human judgment error)
   - Was it unpredictable? (Black swan, regulatory change, fraud)
3. **Lesson learned:** What could have been done differently?
4. **Process change:** Does the QA process need to be updated to catch this type of error?
5. **Document in a lessons-learned log**

### 17.3 Scoring Threshold Calibration

- **Annually:** Review whether the recommendation thresholds (30, 45, 60, 75) are well-calibrated
- **Method:** Backtest the scoring model on historical data. Are STRONG BUY stocks actually outperforming? Are STRONG SELL stocks actually underperforming?
- **Adjustment:** If thresholds are poorly calibrated, propose new thresholds with supporting evidence. Any threshold change requires:
  - Statistical justification (backtest results)
  - Regression testing on benchmark companies
  - Version bump on the scoring model
  - Documentation of the change and rationale

### 17.4 Peer Group Maintenance

- **Quarterly:** Review peer groups for each tracked company
- **Check for:** Mergers, acquisitions, spin-offs, or significant business model changes that would change peer relevance
- **Update `ai_moat_universe.yaml`:** Add new entrants, remove acquired companies, update moat overrides based on changed competitive positions

### 17.5 Data Source Reliability Review

- **Quarterly:** Assess each data source for reliability:
  - Uptime (% of time the API was available)
  - Data accuracy (% of spot-checks that matched independent sources)
  - Timeliness (average delay from event to data availability)
  - Coverage (% of our universe that the source covers)
- **Action:** If a primary source falls below 95% reliability, consider promoting a fallback to primary

### 17.6 Model Version Tracking

Every change to the scoring methodology must be tracked:

| Version | Date | Change | Justification |
|---------|------|--------|---------------|
| v1.0 | Initial | Baseline methodology | Original implementation |
| vX.Y | TBD | TBD | (Template for future changes) |

---

## 18. Audit Trail Requirements

### 18.1 Data Fetch Logging

Every external data fetch must be logged with:
- **Timestamp:** When the fetch occurred
- **Source:** Which API/service was queried
- **Parameters:** Ticker, date range, any other query parameters
- **Response status:** Success, failure, partial
- **Data points received:** Count of records/fields returned
- **Cache status:** Cache hit, cache miss, cache expired

The `src/utils/logger.py` logger already provides timestamps. Ensure all data clients (`MarketDataClient`, `FundamentalsClient`, `NewsSentimentClient`, `AlternativeDataClient`, `MacroDataClient`, `SECFilingsClient`) log fetches at `INFO` level.

### 18.2 Scoring Model Versioning

- Record which version of the scoring model was used for each analysis
- Include the git commit hash in report metadata
- If weights or thresholds change, bump the model version

### 18.3 Manual Override Tracking

Any manual override or adjustment to an automated score must be:
- Logged with the analyst's identification
- Justified with a written explanation
- Recorded with both the original automated value and the overridden value
- Reversible (the original value is preserved, not destroyed)

### 18.4 Report Version History

- Reports are saved with timestamps in filenames (`{TICKER}_{YYYYMMDD_HHMMSS}.md`)
- Never overwrite previous reports; always create new files
- Maintain an index of all reports generated (consider a CSV or database log)
- JSON outputs enable programmatic comparison between report versions

### 18.5 Cache Preservation for Reproducibility

- Raw API responses are cached in `data/cache/` organized by category
- Cache files use MD5 hashed keys (via `DataCache._key_path()`)
- For any disputed analysis, the cached data should allow exact reproduction of the result
- Consider archiving cache snapshots for published analyses (copy from `data/cache/` to `data/archive/{date}/`)

---

## 19. QA Output Format

Every QA review must produce a structured output. This format ensures consistency and accountability.

### 19.1 QA Summary Report Template

```
=============================================================
QA REVIEW SUMMARY
=============================================================
Analysis Target:  [TICKER] - [Company Name]
Analysis Date:    [YYYY-MM-DD HH:MM]
Reviewer:         [Name/Role]
Review Type:      [Self-Review / Cross-Review / Devil's Advocate]
Model Version:    [vX.Y]
Git Commit:       [short hash]
=============================================================

1. DATA QUALITY
   Sources Checked:        [list of sources verified]
   Freshness Verified:     [YES/NO - oldest data point age]
   Cross-Source Agreement:  [PASS/FAIL - discrepancies noted]
   Null/Missing Values:    [count and affected fields]
   Schema Validation:      [PASS/FAIL]
   Data Quality Grade:     [A/B/C/D/F]

2. CALCULATION VERIFICATION
   Composite Score Manual Check:  [computed value] vs [reported value] = [MATCH/MISMATCH]
   Sub-Score Range Check:         [all in 0-100: YES/NO]
   Weight Sum Verified:           [sum = X.XX, expected 1.00]
   Spot-Check Results:
     - [Metric 1]: [our value] vs [independent value] = [MATCH/MISMATCH]
     - [Metric 2]: [our value] vs [independent value] = [MATCH/MISMATCH]
     - [Metric 3]: [our value] vs [independent value] = [MATCH/MISMATCH]
   Calculation Grade:             [A/B/C/D/F]

3. ANALYTICAL CONSISTENCY
   Score-Recommendation Alignment: [CORRECT/INCORRECT]
   Internal Consistency:           [PASS/FAIL - conflicts noted]
   Thesis Coherence:               [STRONG/ADEQUATE/WEAK]
   Assumption Reasonableness:      [PASS/FAIL - concerns noted]
   Bias Check Completed:           [YES/NO]
   Contrarian Case Addressed:      [YES/NO]
   Analytical Grade:               [A/B/C/D/F]

4. OUTPUT QUALITY
   Format Compliance:     [PASS/FAIL]
   All Sections Present:  [YES/NO - missing sections]
   Labels Accurate:       [PASS/FAIL]
   JSON Valid:            [PASS/FAIL]
   Output Grade:          [A/B/C/D/F]

5. ISSUES FOUND
   [Issue #1]: [description] - [severity] - [resolution status]
   [Issue #2]: [description] - [severity] - [resolution status]
   ...

6. OVERALL ASSESSMENT
   Overall Grade:    [A/B/C/D/F]
   Recommendation:   [APPROVE / APPROVE WITH CAVEATS / REJECT]
   Caveats (if any): [description]

7. SIGN-OFF
   Reviewer:   [Name]        Date: [YYYY-MM-DD]
   Approver:   [Name]        Date: [YYYY-MM-DD]
=============================================================
```

### 19.2 Grading Criteria

| Grade | Criteria |
|-------|---------|
| **A** | No issues found. All checks pass. Data is fresh, calculations are correct, analysis is coherent. |
| **B** | Minor issues found (e.g., 1-2 stale data points, cosmetic formatting issues). All corrected before distribution. |
| **C** | Moderate issues found (e.g., one sub-score using fallback data, a peer comparison question). Issues documented and caveats added. |
| **D** | Significant issues found (e.g., calculation error corrected, data source disagreement unresolved). Requires re-analysis of affected sections. |
| **F** | Critical issues found (e.g., wrong ticker, incorrect recommendation, broken scoring formula). Analysis must be rejected and re-done from scratch. |

**Minimum passing grade for distribution: B**
**Minimum passing grade for internal use: C (with documented caveats)**

---

## 20. Appendices

### Appendix A: Quick Reference -- Score Thresholds

| Composite Score | Recommendation |
|----------------|----------------|
| >= 75 | STRONG BUY |
| >= 60, < 75 | BUY |
| >= 45, < 60 | HOLD |
| >= 30, < 45 | SELL |
| < 30 | STRONG SELL |

### Appendix B: Quick Reference -- Composite Weights

| Dimension | Weight | Source Module |
|-----------|--------|---------------|
| Fundamental | 30% | `src/analysis/fundamental.py` |
| Valuation | 25% | `src/analysis/valuation.py` |
| Technical | 20% | `src/analysis/technical.py` |
| Sentiment | 10% | `src/analysis/sentiment.py` |
| Risk | 15% | `src/analysis/risk.py` |

### Appendix C: Quick Reference -- Moat Thresholds

| Moat Score | Classification |
|------------|---------------|
| >= 80 | WIDE MOAT |
| >= 60, < 80 | NARROW MOAT |
| >= 40, < 60 | WEAK MOAT |
| < 40 | NO MOAT |

### Appendix D: Quick Reference -- Moat Dimension Weights

| Dimension | Weight |
|-----------|--------|
| Market Dominance | 20% |
| Switching Costs | 15% |
| Technology Lock-in | 15% |
| Supply Chain Criticality | 20% |
| Pricing Power | 15% |
| Barriers to Entry | 15% |

### Appendix E: Quick Reference -- Cache TTLs

| Data Category | TTL (Hours) | TTL (Human-Readable) |
|---------------|-------------|---------------------|
| price_daily | 1 | 1 hour |
| price_historical | 24 | 1 day |
| fundamentals | 168 | 7 days |
| sec_filings | 720 | 30 days |
| macro_data | 24 | 1 day |
| news | 1 | 1 hour |

### Appendix F: Quick Reference -- Data Source Priority

| Data Type | Primary | Fallback(s) |
|-----------|---------|-------------|
| Market Data | yfinance | Finnhub, Alpaca |
| Fundamentals | SimFin | Finnhub, FMP |
| News | Finnhub | (none) |
| Sentiment | FinBERT (local) | (none) |
| Social | Reddit (PRAW) | (none) |
| Macro | FRED | (none) |
| Filings | SEC EDGAR | (none) |

### Appendix G: Key File Paths

| Purpose | Path |
|---------|------|
| Composite scoring | `src/analysis/scoring.py` |
| Fundamental analysis | `src/analysis/fundamental.py` |
| Valuation models | `src/analysis/valuation.py` |
| Technical analysis | `src/analysis/technical.py` |
| Sentiment analysis | `src/analysis/sentiment.py` |
| Risk analysis | `src/analysis/risk.py` |
| Moat analysis | `src/analysis/moat.py` |
| Report generator | `src/reports/generator.py` |
| Configuration | `configs/settings.yaml` |
| Moat universe | `configs/ai_moat_universe.yaml` |
| Data cache | `src/utils/cache.py` |
| Main CLI entry point | `main.py` |

### Appendix H: Checklist Summary (Tear-Off)

**Pre-Analysis (all must be checked):**
- [ ] Data sources responsive
- [ ] Market data current
- [ ] Correct ticker
- [ ] Fiscal year understood
- [ ] No pending corporate actions
- [ ] Peer group appropriate
- [ ] Cache state known

**Post-Analysis (all must be checked):**
- [ ] Composite score manually verified
- [ ] All sub-scores in [0, 100]
- [ ] Recommendation matches threshold
- [ ] Financial data matches filings
- [ ] 2-3 ratios spot-checked
- [ ] DCF assumptions reasonable
- [ ] Peers are comparable
- [ ] Risk lookback period correct
- [ ] Sentiment data fresh
- [ ] No internal contradictions
- [ ] All output fields populated
- [ ] Fallback scores flagged

---

*This SOP is a living document. Submit proposed changes via pull request with justification. All changes require review and approval before taking effect.*

*Last reviewed: 2026-02-09*
