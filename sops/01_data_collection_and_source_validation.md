# SOP-001: Data Collection & Source Validation

**Document ID:** SOP-001
**Version:** 1.0
**Effective Date:** 2026-02-09
**Applies To:** All data ingestion activities within the FE-Analyst platform
**Review Cycle:** Quarterly, or upon addition of new data sources

---

## 1. Purpose

Every downstream output of the FE-Analyst platform -- valuations, risk scores, sentiment signals, composite rankings -- is only as reliable as the data feeding it. The principle is simple and unforgiving: **garbage in, garbage out**. A single misconfigured currency field, a stale earnings figure, or an undetected stock split can silently corrupt an entire analysis pipeline, producing confident-looking results that are fundamentally wrong.

This SOP codifies the exact procedures, validation checks, and quality gates that must be followed for all data collection activities. It exists to ensure that:

1. **Data provenance is always known.** Every data point must be traceable to a specific source, retrieval timestamp, and cache state.
2. **Cross-source discrepancies are detected, not hidden.** When yfinance and Finnhub disagree on a P/E ratio, that disagreement is a signal, not a nuisance.
3. **Staleness is treated as a first-class risk.** A 90-day-old SEC filing cached as "current" can lead to decisions based on superseded information.
4. **AI supply chain specifics are accounted for.** Our universe includes Japanese semiconductor equipment makers (March fiscal years, .T tickers), Taiwanese foundries (.TW tickers), Korean memory companies (.KS tickers), and Dutch lithography monopolies -- each with unique data collection challenges.

This document is written to be actionable. Follow it literally.

---

## 2. Scope

This SOP governs **all data ingestion** into the FE-Analyst platform, including:

- **Price and market data** (OHLCV, quotes, market cap, volume)
- **Fundamental data** (financial statements, ratios, company profiles)
- **SEC regulatory filings** (10-K, 10-Q, 8-K, proxy statements, Form 4)
- **Technical indicator inputs** (derived from price/volume data via pandas-ta)
- **News and sentiment data** (Finnhub news, FinBERT scores)
- **Alternative data** (Reddit sentiment via PRAW, insider trades, institutional holdings, analyst estimates)
- **Macroeconomic data** (FRED series, Treasury yields, World Bank indicators)
- **Screening data** (Finviz screener results)

It does **not** cover analysis logic (covered in SOP-002), report generation (SOP-003), or model training/inference (SOP-004).

---

## 3. Data Source Hierarchy & Priority

Sources are organized into four tiers based on authoritativeness, reliability, and data quality. When sources at different tiers conflict, the higher tier takes precedence unless there is a documented reason to prefer the lower-tier source.

### Tier 1 -- Primary / Authoritative Sources

These are the ground truth. When available, they supersede all other sources.

| Source | Data Type | Why Authoritative | Access Method |
|--------|-----------|-------------------|---------------|
| **SEC EDGAR** (data.sec.gov) | 10-K, 10-Q, 8-K, XBRL financials, Form 4, proxy statements | Legally mandated filings; companies face penalties for misstatement | `edgartools` library, direct EDGAR API |
| **FRED** (Federal Reserve) | GDP, CPI, unemployment, fed funds rate, Treasury yields | Official US government economic data | `fredapi` library |
| **US Treasury** (api.fiscaldata.treasury.gov) | Yield curves, auction results, debt data | Official Treasury data | Direct REST API |
| **Company Investor Relations** | Earnings releases, guidance, presentations | Direct from the company | Manual / web scraping |
| **Exchange data** (NYSE, NASDAQ, TSE, TWSE, KRX) | Official listing data, corporate actions | Exchange of record | Via data providers |

**Key rule:** For any US-listed company's financial statements, the SEC filing is the definitive version. If yfinance shows revenue of $50.2B and the 10-K says $50.3B, the 10-K is correct.

### Tier 2 -- Reliable Aggregators

These aggregate and normalize data from authoritative sources. Generally reliable but may have transformation errors, delays, or gaps.

| Source | Data Type | Strengths | Weaknesses |
|--------|-----------|-----------|------------|
| **yfinance** | Prices, OHLCV, fundamentals, analyst estimates, institutional holders | Excellent breadth; most popular; batch-friendly | Unofficial (scrapes Yahoo); may break; 15-min delayed quotes; occasional data gaps |
| **SimFin** | Financial statements (quarterly/annual), share prices | High-quality fundamentals; Pandas-native; bulk download | Limited to ~5,000 US stocks; >5yr data requires paid plan |
| **Finnhub** | Real-time quotes, fundamentals, news, insider trades, analyst data | Best free API tier (60 calls/min); broad coverage | Some fundamental data less granular than SEC XBRL |
| **Alpaca** | Real-time/historical US prices, news | IEX real-time feed; designed for trading | US equities only; requires account |

**Key rule:** Always cross-reference at least two Tier 2 sources for any metric used in a final score or recommendation.

### Tier 3 -- Supplementary Sources

Useful for screening, discovery, and directional signals. Not reliable enough to be sole data inputs for analysis.

| Source | Data Type | Best Use Case | Caveats |
|--------|-----------|---------------|---------|
| **Finviz** (via `finvizfinance`) | Stock screening, overview metrics | Initial universe filtering; quick scans | Scraped data; 15-20 min delay; can break |
| **Reddit** (via PRAW) | Retail sentiment, discussion trends | Sentiment signals; attention indicators | Noisy; bot contamination; requires heavy filtering |
| **Finnhub News** | Company/market news | News-driven sentiment analysis | Coverage varies by company; may miss niche stories |
| **FinBERT** (local model) | Sentiment classification | NLP-based sentiment scoring | Model accuracy ~85-90%; can misclassify sarcasm/irony |
| **Alpha Vantage** | Technical indicators, prices | Gap-filling when yfinance fails | Extremely limited free tier (25/day) |

### Tier 4 -- Cross-Reference Only

Never use as a sole data source. Only for cross-referencing or qualitative context.

| Source | Use Case |
|--------|----------|
| Blog posts, Substack newsletters | Thesis validation, qualitative insight |
| Twitter/X financial accounts | Attention signals, breaking news awareness |
| YouTube earnings analysis | Alternative perspectives |
| Wikipedia page views | Retail attention proxy |
| Unattributed data in forums | Never use for quantitative analysis |

**Key rule for Tier 4:** If a Tier 4 source contradicts a Tier 1 or Tier 2 source, the Tier 4 source is wrong until proven otherwise with primary documentation.

---

## 4. Procedures

### 4.1 Price & Market Data Collection

**Primary source:** yfinance (`MarketDataClient.get_price_history`)
**Fallback:** Finnhub (`MarketDataClient.get_quote`)
**Cache TTL:** 1 hour for daily prices, 24 hours for historical

#### 4.1.1 Always Use Adjusted Close Prices

For any historical price analysis (returns, technical indicators, backtesting), **always use adjusted close prices**. Unadjusted prices contain discontinuities from stock splits and dividends that will produce incorrect calculations.

```python
# CORRECT: yfinance .history() returns adjusted data by default
df = stock.history(period="2y")  # 'Close' column is adjusted

# WRONG: Using unadjusted close for return calculations
# Some sources provide both -- always verify which you are using
```

**Exception:** Use unadjusted prices only when analyzing intraday data or when specifically studying the price impact of a corporate action.

#### 4.1.2 Verify Data Completeness

After retrieving price data, perform these checks before proceeding:

1. **Gap detection:** Check for missing trading days (weekends/holidays are expected gaps; mid-week gaps are not).
   ```python
   # Detect unexpected gaps (>3 calendar days between trading days)
   date_diffs = df.index.to_series().diff()
   suspicious_gaps = date_diffs[date_diffs > pd.Timedelta(days=4)]
   ```

2. **Split detection:** Look for single-day price changes exceeding 40% that are not accompanied by corresponding news. These often indicate an unprocessed split.
   ```python
   daily_returns = df['Close'].pct_change()
   potential_splits = daily_returns[abs(daily_returns) > 0.40]
   ```

3. **Volume anomalies:** Zero-volume days on normally liquid stocks indicate data quality issues.
   ```python
   zero_volume = df[df['Volume'] == 0]
   if len(zero_volume) > 0 and ticker not in KNOWN_LOW_VOLUME:
       logger.warning("Zero-volume days detected: %s for %s", len(zero_volume), ticker)
   ```

#### 4.1.3 International Ticker Handling

Our AI supply chain universe includes companies across multiple exchanges. Tickers require exchange-specific suffixes in yfinance:

| Exchange | Suffix | Example Tickers | Notes |
|----------|--------|-----------------|-------|
| Tokyo Stock Exchange | `.T` | `8035.T` (Tokyo Electron), `6920.T` (Lasertec), `6857.T` (Advantest) | Most Japanese companies in our universe |
| Taiwan Stock Exchange | `.TW` | `2330.TW` (TSMC), `3037.TW` (Unimicron) | TSMC also trades as ADR `TSM` |
| Korea Exchange | `.KS` | `000660.KS` (SK Hynix) | Note leading zeros in ticker |
| Euronext Amsterdam | `.AS` | `ASML.AS` (ASML Holding) | ASML also trades as ADR `ASML` on NASDAQ |
| US exchanges | (none) | `LRCX`, `AMAT`, `SNPS`, `CDNS` | No suffix needed |

**ADR vs Local Share Reconciliation:**

Many companies in our universe trade both on their home exchange and as ADRs in the US. When collecting data:

- Use the **local ticker** (e.g., `8035.T`) for the most complete fundamental data in the company's reporting currency.
- Use the **ADR ticker** (e.g., `TOELY` for Tokyo Electron) when comparing to US-listed peers or when USD-denominated analysis is needed.
- **Always document which ticker was used** for any given data pull.
- Be aware of **ADR ratios** -- one ADR share may represent a fractional or multiple local shares, which affects per-share metrics (EPS, book value per share, dividend per share).

Example ADR mappings from our universe (`configs/ai_moat_universe.yaml`):

| Company | Local Ticker | ADR Ticker | ADR Ratio Impact |
|---------|-------------|------------|------------------|
| Tokyo Electron | 8035.T | TOELY | Per-share metrics differ |
| Advantest | 6857.T | ATEYY | Per-share metrics differ |
| Shin-Etsu Chemical | 4063.T | SHECY | Per-share metrics differ |
| TSMC | 2330.TW | TSM | 1 ADR = 5 local shares |
| SK Hynix | 000660.KS | HXSCL | Per-share metrics differ |
| Murata Manufacturing | 6981.T | MRAAY | Per-share metrics differ |

#### 4.1.4 Currency Considerations

- **Always record the currency alongside any financial figure.** A revenue of "50,000" means nothing without knowing if it is millions of JPY, USD, or TWD.
- Japanese companies report in JPY (often in units of millions of yen).
- Taiwanese companies report in TWD.
- Korean companies report in KRW.
- When comparing companies across currencies, convert to a single base currency (USD) using exchange rates from the **same date** as the financial data.
- For the `get_current_price()` method, note that `fast_info.currency` returns the trading currency -- use this field.

#### 4.1.5 Minimum Data Requirements

| Analysis Type | Minimum History | Recommended History |
|---------------|----------------|---------------------|
| Technical analysis (indicators) | 1 year daily | 2 years daily |
| Trend analysis | 2 years daily | 5 years daily |
| Fundamental trend analysis | 3 years (12 quarters) | 5 years (20 quarters) |
| Cyclical analysis (semiconductor cycle) | 5 years | 10 years |
| Volatility modeling | 1 year (252 trading days) | 2 years |
| Correlation/beta calculation | 2 years daily | 3 years daily |

**Semiconductor cycle note:** The semiconductor industry has pronounced cyclical patterns (typically 3-5 year cycles). For companies in our `semiconductor_equipment`, `chemicals_materials`, `foundry_memory`, and `packaging_substrates` categories, always collect at least one full cycle of data to avoid drawing trend conclusions from a single up-cycle or down-cycle.

#### 4.1.6 Cross-Reference Protocol

For any ticker used in a final analysis output, compare yfinance and Finnhub data:

```
Step 1: Pull current quote from yfinance (MarketDataClient.get_current_price)
Step 2: Pull current quote from Finnhub (MarketDataClient.get_quote)
Step 3: Compare prices -- they should be within 1% during market hours
Step 4: If variance > 1%, flag for manual review before proceeding
Step 5: Log the comparison result regardless of outcome
```

### 4.2 Fundamental Data Collection

**Primary source:** SEC EDGAR via `edgartools` (`SECFilingsClient`)
**Secondary sources:** yfinance (`FundamentalsClient`), SimFin, Finnhub
**Cache TTL:** 24 hours for fundamentals, 30 days (720 hours) for SEC filings

#### 4.2.1 SEC Filings Are the Gold Standard

For any US-listed company (or foreign private issuer filing with the SEC), the SEC filing is the authoritative source. This means:

- **10-K** (annual report): Definitive source for annual financial statements, risk factors, business description, and management discussion.
- **10-Q** (quarterly report): Definitive source for quarterly financial statements.
- **8-K** (current report): Material events -- earnings releases, executive changes, M&A, material agreements.
- **20-F / 40-F**: Annual reports for foreign private issuers (relevant for ASML, TSMC ADR, etc.).
- **6-K**: Interim reports from foreign private issuers.
- **DEF 14A** (proxy statement): Executive compensation, board composition, shareholder proposals.

**XBRL data** from SEC filings provides machine-readable, structured financial data. Prefer XBRL extraction (via `SECFilingsClient.get_financials_xbrl`) over scraped data when available.

#### 4.2.2 Financial Statement Consistency Checks

After pulling financial statements, validate internal consistency:

**Balance Sheet Identity (must hold exactly):**
```
Total Assets = Total Liabilities + Total Stockholders' Equity
```

If this equation does not balance, the data is corrupted. Do not proceed -- re-fetch from the primary source.

**Income Statement Checks:**
```
Gross Profit = Revenue - Cost of Goods Sold
Operating Income = Gross Profit - Operating Expenses
Net Income = Operating Income + Non-operating Items - Tax
```

Allow for rounding differences of up to 0.1% of the largest line item.

**Cash Flow Statement Check:**
```
Change in Cash = Operating Cash Flow + Investing Cash Flow + Financing Cash Flow
```

Verify that the beginning and ending cash balances are consistent with the reported change.

**Cross-Statement Consistency:**
- Net income on the income statement should match net income on the cash flow statement (starting point for operating cash flow under indirect method).
- Retained earnings change on the balance sheet should approximately equal net income minus dividends.

#### 4.2.3 Restatements and Amended Filings

- Always check for **10-K/A** or **10-Q/A** filings (the "/A" suffix indicates an amendment).
- If an amended filing exists, use it instead of the original.
- Log any restatements as material events -- they may indicate accounting issues.
- Our `SECFilingsClient.get_recent_filings()` should be called with both the base form type and the amended version:
  ```
  get_recent_filings(ticker, form_type="10-K")   # original filings
  get_recent_filings(ticker, form_type="10-K/A")  # amendments
  ```

#### 4.2.4 Fiscal Year vs Calendar Year

This is a critical consideration for our AI supply chain universe. Many Japanese companies operate on non-standard fiscal years:

| Company | Fiscal Year End | Implication |
|---------|----------------|-------------|
| Tokyo Electron (8035.T) | March 31 | "FY2025" = April 2024 - March 2025 |
| Lasertec (6920.T) | June 30 | Unusual even for Japan |
| Advantest (6857.T) | March 31 | Standard Japanese FY |
| Shin-Etsu Chemical (4063.T) | March 31 | Standard Japanese FY |
| ASML (ASML) | December 31 | Calendar year |
| TSMC (2330.TW) | December 31 | Calendar year |
| US companies (LRCX, AMAT, etc.) | Varies | AMAT: October; LRCX: June; KLAC: June |

**Alignment rules:**
- When comparing companies with different fiscal year ends, align by **calendar quarter** rather than fiscal quarter.
- Always label data with the actual date range, not just "Q1 2025" (which is ambiguous across fiscal years).
- Example: Tokyo Electron's "Q3 FY2025" is October-December 2024 in calendar terms. ASML's "Q4 2024" covers the same calendar period. These should be aligned for comparison.

#### 4.2.5 Non-GAAP vs GAAP Metrics

Many technology companies report both GAAP and non-GAAP (adjusted) figures. Rules:

1. **Always collect GAAP figures first.** These are required by SEC and are comparable across companies.
2. **Record non-GAAP figures separately** when available, with clear labeling.
3. **Common non-GAAP adjustments** in our universe:
   - Stock-based compensation (SBC) -- often excluded from non-GAAP EPS by tech companies
   - Amortization of acquired intangibles (relevant for acquisitive companies like Broadcom, Synopsys)
   - Restructuring charges
   - One-time legal settlements
4. **Never mix GAAP and non-GAAP** in the same comparison. If comparing Synopsys to Cadence on operating margin, use GAAP for both or non-GAAP for both.

#### 4.2.6 Revenue Recognition Awareness

For semiconductor equipment companies in particular, revenue recognition can vary significantly:

- **Percentage of completion:** Some recognize revenue as equipment is built (common for large custom systems).
- **Upon delivery/acceptance:** Revenue recognized when the customer accepts the equipment.
- **ASC 606 impacts:** Multiple performance obligations may be split across delivery, installation, and warranty.

When comparing revenue growth rates across semiconductor equipment companies, be aware that changes in accounting policy can create apparent growth or decline that does not reflect actual business performance.

#### 4.2.7 Multi-Year Data Alignment

When building time-series datasets across multiple years:

1. Ensure all periods use the **same accounting standards** (check for IFRS-to-GAAP transitions or vice versa).
2. Adjust for **M&A activity** -- a company that acquired a $5B revenue business will show discontinuous growth that is not organic.
3. Adjust for **spin-offs** -- the historical data may include a now-separate business.
4. Flag any **segment reclassifications** (companies sometimes reorganize reporting segments, making year-over-year comparison misleading).

### 4.3 Alternative Data Collection

#### 4.3.1 Sentiment Data Freshness Requirements

| Data Type | Maximum Age for Use | Rationale |
|-----------|-------------------|-----------|
| Breaking company news | < 4 hours | Market reacts quickly to material news |
| Company news (non-breaking) | < 24 hours | Stale news creates false signals |
| Reddit/social sentiment | < 7 days | Social trends shift rapidly |
| Analyst estimate revisions | < 7 days | Revisions are time-sensitive signals |
| Insider trading filings | < 14 days | Form 4 must be filed within 2 business days of the trade |
| Institutional ownership (13-F) | < 90 days | Filed quarterly with 45-day delay |

#### 4.3.2 Reddit Data Quality Filtering

Reddit data (via `AlternativeDataClient.get_reddit_sentiment`) is inherently noisy. Apply these filters:

**Pre-processing filters (before analysis):**
- **Minimum post score:** Only include posts with `score >= 5` (filters out low-quality/bot content).
- **Minimum comments:** Posts with `num_comments >= 3` are more likely substantive discussions.
- **Upvote ratio:** Filter for `upvote_ratio >= 0.6` to exclude highly controversial or trolling posts.
- **Account age/karma:** Where accessible, prefer posts from accounts older than 90 days.
- **Subreddit selection:** Use purpose-appropriate subreddits:
  - `r/wallstreetbets` -- retail sentiment, meme-stock signals, YOLO plays
  - `r/stocks` -- more measured discussion, fundamental analysis
  - `r/investing` -- long-term perspective, dividend/value focus
  - `r/semiconductors` -- directly relevant to our universe
  - `r/options` -- options flow sentiment

**Bot detection heuristics:**
- Posts with identical or near-identical text across multiple subreddits
- Accounts posting more than 20 times per day about financial topics
- Posts containing only a ticker symbol with no substantive commentary
- Sudden volume spikes from new accounts (< 7 days old)

**Weighting by relevance:**
- Posts that specifically mention companies in our AI supply chain universe should receive higher weight.
- Generic market commentary (e.g., "stocks go up") should receive minimal weight.
- Posts that reference specific financial metrics, earnings, or supply chain dynamics should receive highest weight.

#### 4.3.3 Analyst Consensus Data

When collecting analyst estimates via Finnhub or yfinance:

- **Track revision direction, not just current target.** An analyst raising their price target from $200 to $220 is a different signal than a $220 target that has been unchanged for 6 months.
- **Count the number of analysts.** A consensus of 2 analysts is far less meaningful than a consensus of 15.
- **Record the date of each estimate.** Estimates from before the most recent earnings report are stale and may not reflect updated information.
- **Track the spread.** A stock with analyst targets ranging from $100 to $400 has high uncertainty; one with targets from $180 to $220 has strong consensus.
- **Separate buy-side vs sell-side** when possible. Sell-side estimates (from investment bank analysts) are publicly available; buy-side estimates (from mutual fund/hedge fund analysts) are not.

#### 4.3.4 Insider Trading Data

Via `AlternativeDataClient.get_insider_trades` (Finnhub source):

**Distinguish between trade types:**
- **10b5-1 planned sales:** Executives set up automatic selling plans. These are often routine and less informative. Look for the `10b5-1` flag.
- **Discretionary purchases:** Officers/directors buying with their own money on the open market. **These are highly informative** -- insiders rarely buy unless they believe the stock is undervalued.
- **Option exercises:** Often followed by immediate sale (cashless exercise). Less informative than open-market purchases.
- **RSU vesting + sale:** Automatic for tax purposes. Low signal value.

**Aggregation rules:**
- Look for **cluster buying** (multiple insiders buying within a 30-day window) -- stronger signal than a single insider.
- Weight by **seniority** (CEO/CFO purchases > VP purchases > director purchases).
- Track **dollar amounts**, not just share counts. A $5M CEO purchase is a much stronger signal than a $50K director purchase.
- Always cross-reference with SEC Form 4 filings (Tier 1 source) to confirm Finnhub data accuracy.

### 4.4 Macroeconomic Data Collection

**Primary source:** FRED via `fredapi` (`MacroDataClient`)
**Secondary source:** World Bank (via `wbdata`)
**Cache TTL:** 24 hours

#### 4.4.1 Essential FRED Series

These series are configured in `MacroDataClient.get_economic_indicators()` and `get_treasury_yields()`:

| Series ID | Name | Frequency | Relevance to AI Supply Chain |
|-----------|------|-----------|------------------------------|
| `A191RL1Q225SBEA` | Real GDP Growth (quarterly) | Quarterly | Broad economic backdrop |
| `UNRATE` | Unemployment Rate | Monthly | Labor market / consumer spending proxy |
| `CPIAUCSL` | Consumer Price Index | Monthly | Inflation environment |
| `FEDFUNDS` | Federal Funds Rate | Daily | Interest rate environment, discount rate input for DCF |
| `DGS3MO` | 3-Month Treasury Yield | Daily | Short end of yield curve |
| `DGS2` | 2-Year Treasury Yield | Daily | Rate expectations |
| `DGS5` | 5-Year Treasury Yield | Daily | Medium-term rates |
| `DGS10` | 10-Year Treasury Yield | Daily | Risk-free rate proxy (used in CAPM/DCF) |
| `DGS30` | 30-Year Treasury Yield | Daily | Long-term rate environment |
| `SP500` | S&P 500 Index | Daily | Market benchmark |
| `VIXCLS` | VIX (Volatility Index) | Daily | Market fear gauge |
| `T10Y2Y` | 10Y-2Y Treasury Spread | Daily | Yield curve inversion signal (recession indicator) |
| `DTWEXBGS` | Trade-Weighted US Dollar Index | Daily | USD strength (impacts international revenues) |

**Additional series relevant to semiconductor/AI cycle:**
| Series ID | Name | Relevance |
|-----------|------|-----------|
| `AMTMNO` | New Orders: Durable Goods | Leading indicator for equipment demand |
| `NEWORDER` | Manufacturers' New Orders | Capex cycle indicator |
| `INDPRO` | Industrial Production Index | Manufacturing activity |
| `PCE` | Personal Consumption Expenditures | Consumer demand backdrop |

#### 4.4.2 Treasury Yield Curve Construction

The yield curve is critical for valuation (discount rates) and recession signaling.

**Required maturities:** 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y
**Inversion signal:** When `DGS2 > DGS10` (2-year yield exceeds 10-year yield), this has historically preceded recessions with an 12-18 month lead time.

**For DCF valuations:**
- Risk-free rate = 10-Year Treasury Yield (from `MacroDataClient.get_risk_free_rate()`)
- Fallback: 4.0% if FRED data is unavailable (configured in `macro_data.py`)
- Market risk premium = 6.0% (configured in `configs/settings.yaml` as `market_premium: 0.06`)

#### 4.4.3 Leading vs Lagging Indicators

Classify every macro indicator you use:

| Leading (predictive) | Coincident (current) | Lagging (confirmatory) |
|----------------------|---------------------|----------------------|
| Yield curve slope | Industrial production | Unemployment rate |
| New orders (durable goods) | Real GDP | CPI (inflation) |
| Building permits | Personal income | Average duration of unemployment |
| Stock market (S&P 500) | Manufacturing sales | Consumer credit |
| ISM PMI | | Commercial/industrial loans |
| Consumer expectations | | Labor cost per unit of output |

**Rule:** Never use lagging indicators to predict future performance. Use them only to confirm what leading indicators are suggesting.

#### 4.4.4 Data Release Schedule Awareness

Economic data is released on a set schedule. Be aware of:

- **Employment Situation** (BLS): First Friday of each month at 8:30 AM ET
- **CPI**: ~12th-14th of each month at 8:30 AM ET
- **GDP**: Advanced estimate ~30 days after quarter end; revised twice
- **FOMC Rate Decision**: 8 meetings per year (schedule published annually)
- **PCE**: Last day of each month

**Why this matters:** Pulling FRED data immediately after a release gives you the freshest picture. Pulling 3 weeks after a release means you may be analyzing with data that has already been priced in.

---

## 5. Validation Checks (Critical)

Every data retrieval must pass through the validation framework before entering the analysis pipeline. The five checks below are mandatory and non-negotiable.

### 5.1 Completeness Check

**Objective:** Ensure no missing data points that would corrupt analysis.

| Data Type | Completeness Standard | Action if Failed |
|-----------|----------------------|------------------|
| Daily OHLCV | No gaps > 4 calendar days (excluding known market closures) | Re-fetch from fallback source; if still incomplete, document gaps and exclude affected date ranges |
| Quarterly financials | No missing quarters in requested range | Check for M&A, IPO date, or de-listing; fall back to SEC filings |
| Annual financials | All fiscal years in range present | Same as above |
| FRED series | No gaps in daily series; monthly series may have natural gaps | Verify against FRED release schedule; forward-fill only for daily series with 1-2 day gaps |
| News/sentiment | Minimum 5 news items per company per 30-day window | If fewer, flag as "low news coverage" but do not fabricate data |

**Code-level implementation:**
```python
# Example: checking for price data completeness
def validate_price_completeness(df: pd.DataFrame, ticker: str) -> dict:
    """Return validation result for price data completeness."""
    if df.empty:
        return {"valid": False, "reason": "Empty DataFrame", "ticker": ticker}

    expected_trading_days = pd.bdate_range(df.index.min(), df.index.max())
    missing = expected_trading_days.difference(df.index)
    # Allow for holidays (~10 per year for US markets)
    completeness_ratio = len(df) / len(expected_trading_days)

    return {
        "valid": completeness_ratio >= 0.95,
        "completeness_ratio": round(completeness_ratio, 4),
        "missing_days": len(missing),
        "ticker": ticker,
    }
```

### 5.2 Consistency Check (Cross-Source Validation)

**Objective:** Detect data corruption or transformation errors by comparing the same metric across sources.

**When to cross-reference:**
- Always for metrics used in final scoring or recommendations
- Always for any metric that seems unusually high or low
- Always when a data source was recently updated or had known issues

**Acceptable variance thresholds:**

| Metric | Maximum Acceptable Variance | Sources to Compare |
|--------|---------------------------|-------------------|
| Current stock price | 1% (during market hours) | yfinance vs Finnhub |
| Market cap | 2% | yfinance vs Finnhub |
| Trailing P/E ratio | 5% | yfinance vs Finnhub vs SimFin |
| Revenue (annual) | 0.5% | SEC XBRL vs yfinance vs SimFin |
| EPS | 2% | SEC filing vs yfinance |
| Dividend yield | 5% | yfinance vs Finnhub |
| 52-week high/low | 1% | yfinance vs Finnhub |

**Investigation protocol when variance exceeds threshold:**
1. Identify which source was updated most recently.
2. Check for stock splits, dividends, or corporate actions that may not have propagated to all sources.
3. Check if one source is using GAAP and the other non-GAAP.
4. Check for currency differences (a common issue with international stocks).
5. If the discrepancy cannot be resolved, use the Tier 1 source (SEC filing) as truth, or the most recently updated Tier 2 source.
6. **Always log the discrepancy** with both values, both sources, and the resolution.

### 5.3 Timeliness Check (Staleness Detection)

**Objective:** Ensure data is fresh enough for its intended use.

The cache system (`DataCache` in `src/utils/cache.py`) enforces TTL at the storage level, but the analysis layer must also check staleness.

**Configured TTL values (from `configs/settings.yaml`):**

| Data Category | Cache TTL | Rationale |
|---------------|-----------|-----------|
| `price_daily` | 1 hour | Prices change continuously during market hours |
| `price_historical` | 24 hours | Historical data does not change (except for adjustments) |
| `fundamentals` | 168 hours (7 days) | Financial statements update quarterly |
| `sec_filings` | 720 hours (30 days) | SEC filings are stable once published (except amendments) |
| `macro_data` | 24 hours | Economic indicators update per release schedule |
| `news` | 1 hour | News loses relevance rapidly |

**Staleness overrides:**
- During **earnings season** (January, April, July, October), reduce `fundamentals` TTL to 24 hours to capture newly filed 10-Qs.
- After a **material event** (8-K filing, earnings miss, M&A announcement), immediately invalidate all cached data for the affected ticker.
- For **real-time analysis** (intraday), bypass the cache entirely and call APIs directly.

### 5.4 Reasonableness Check (Sanity Bounds)

**Objective:** Catch obviously erroneous data before it corrupts analysis.

**Automated sanity bounds:**

| Metric | Reasonable Range | Action if Out of Range |
|--------|-----------------|----------------------|
| Stock price | > $0 (or equivalent in local currency) | Reject -- likely delisted or error |
| Trailing P/E | -1000 to +1000 | Flag for review; negative P/E means losses; > 200 common for high-growth tech |
| Forward P/E | 1 to 500 | Values > 200 need manual confirmation |
| P/B ratio | 0 to 200 | Negative book value is possible but should be flagged |
| Revenue | >= 0 | Negative revenue is almost always an error (exception: certain financial companies) |
| Market cap | > $10M for our universe | Our universe is mid-to-mega cap; anything < $10M is likely an error |
| Debt-to-equity | -5 to 50 | Extremely leveraged companies exist but flag for review |
| Dividend yield | 0% to 25% | Yields > 15% usually signal distress or error |
| Revenue growth (YoY) | -80% to +500% | Semiconductor companies can have volatile growth, but extremes need verification |
| Shares outstanding | > 0 | Zero or negative is always an error |
| Employee count | > 0 | Should be positive for operating companies |

**Semiconductor-specific bounds:**

| Metric | Expected Range for Semi Equipment | Notes |
|--------|----------------------------------|-------|
| Gross margin | 35% - 70% | Semi equipment tends to have high gross margins |
| Operating margin | 15% - 45% | Highly profitable niche |
| R&D as % of revenue | 10% - 25% | Heavy R&D spenders |
| Capex as % of revenue | 3% - 15% | Asset-light relative to foundries |
| Inventory days | 60 - 300 | Long production cycles for equipment |
| Revenue cyclicality | -30% to +50% YoY | Normal range for cyclical companies |

### 5.5 Currency and Unit Verification

**Objective:** Ensure all numbers are in the expected unit and currency.

**Common pitfalls:**
- **Millions vs billions:** yfinance returns market cap in raw numbers (e.g., 250000000000 for $250B), while some reports use "in millions" or "in billions." Always verify the unit.
- **JPY vs USD:** Japanese company financials from yfinance may be in JPY. A "revenue" of 2,000,000 could be 2,000,000 million JPY (2 trillion JPY ~ $14B) or 2,000,000 JPY ($14K) depending on the unit convention.
- **Per-share vs aggregate:** EPS is per-share; net income is aggregate. Mixing these up produces nonsensical ratios.
- **Percentage vs decimal:** Some APIs return margins as 0.15 (15%); others return 15.0. Standardize to decimal (0.15) for calculations and percentage (15%) for display.

**Verification procedure:**
```
For every data retrieval involving financial amounts:
1. Record the currency from the API response
2. Record the unit (raw, thousands, millions, billions)
3. Convert to a standard internal format: USD, raw numbers
4. Log the conversion factor applied
5. Spot-check by comparing to a known reference (e.g., check that TSMC revenue is ~$80B, not $80K or $80T)
```

---

## 6. Data Freshness Requirements Table

This table is the definitive reference for data freshness across the platform. It should be consulted whenever data is retrieved or served to an analysis module.

| Data Type | Maximum Staleness | Cache TTL | Source Priority | Fallback Chain |
|-----------|------------------|-----------|-----------------|----------------|
| Real-time quotes | 15 minutes | 1 hour | yfinance > Finnhub | Alpaca > stale cache |
| Daily OHLCV | End of trading day | 1 hour | yfinance | Finnhub > Alpaca |
| Historical OHLCV | Stable (EOD adj.) | 24 hours | yfinance | SimFin |
| Financial statements (annual) | Quarterly (upon 10-K filing) | 7 days (168 hr) | SEC EDGAR > SimFin > yfinance | Finnhub |
| Financial statements (quarterly) | Quarterly (upon 10-Q filing) | 7 days (168 hr) | SEC EDGAR > SimFin > yfinance | Finnhub |
| SEC filings (10-K, 10-Q, 8-K) | As filed | 30 days (720 hr) | SEC EDGAR (`edgartools`) | Direct EDGAR API |
| Key financial ratios | Weekly | 24 hours | yfinance > Finnhub | SimFin |
| Company profile | Monthly | 7 days | yfinance | Finnhub |
| News headlines | Current day | 1 hour | Finnhub News | Alpaca News |
| News sentiment (FinBERT) | Current day | 4 hours | Local FinBERT model | FinVADER (fast fallback) |
| Social sentiment (Reddit) | Current week | 12 hours | PRAW (Reddit API) | ApeWisdom (cross-ref only) |
| Analyst estimates/targets | Weekly | 24 hours | Finnhub > yfinance | Manual (IR page) |
| Analyst recommendations | Weekly | 24 hours | yfinance > Finnhub | N/A |
| Insider trading (Form 4) | Within 14 days of trade | 24 hours | Finnhub > SEC EDGAR | OpenInsider (cross-ref) |
| Institutional ownership (13-F) | Quarterly (45-day delay) | 7 days | yfinance | SEC EDGAR |
| Macro indicators (GDP, CPI) | Per release schedule | 24 hours | FRED (`fredapi`) | BLS / World Bank |
| Treasury yields | Daily | 24 hours | FRED | US Treasury API |
| Fed funds rate | Per FOMC meeting | 24 hours | FRED | Federal Reserve website |
| Finviz screening data | Intraday (15-20 min delay) | 4 hours | `finvizfinance` | Manual screening |
| World Bank indicators | Annual | 30 days | `wbdata` | Direct API |
| Stock peer list | Monthly | 7 days | Finnhub | Manual curation |

---

## 7. Quality Gates

Data must pass **ALL** quality gates before entering the analysis pipeline. A failure at any gate halts processing for that data element and triggers the documented remediation.

### Gate 1: Schema Validation

**Check:** All expected fields are present in the returned data structure.

```
For price data (DataFrame):
  Required columns: Open, High, Low, Close, Volume
  Required index: DatetimeIndex (timezone-aware preferred)

For financial ratios (dict from FundamentalsClient.get_key_ratios):
  Required keys: ticker, pe_trailing, pe_forward, profit_margin, roe, debt_to_equity
  Optional keys: peg_ratio, pb_ratio, ps_ratio, ev_ebitda (may be None for some companies)

For SEC filings (list of dicts from SECFilingsClient.get_recent_filings):
  Required keys per item: form, date, accession_number
  Optional keys: description

For news (list of dicts from NewsSentimentClient.get_company_news):
  Required keys: headline, datetime
  Optional keys: summary, source, url, category
```

**Remediation:** If required fields are missing, log the error with the source and ticker, attempt the fallback source. If all sources fail, mark the data element as unavailable (NaN) rather than fabricating a value.

### Gate 2: Type Checking

**Check:** Numeric fields contain numeric values; date fields contain valid dates.

```
Prices: float or int, > 0
Volume: int, >= 0
Dates: valid datetime (no "N/A", no "null" strings, no dates before company IPO)
Ratios: float or None (not "NaN" as a string, not "N/A" as a string)
Ticker symbols: non-empty string, matching expected pattern (e.g., 1-5 chars for US, 4 digits + .T for Japan)
```

**Remediation:** Cast types where safe (e.g., string "15.3" to float 15.3). Reject where unsafe (e.g., "N/A" to float). Replace invalid values with `None` or `np.nan`.

### Gate 3: Range Validation

**Check:** Values fall within the sanity bounds defined in Section 5.4.

Apply the complete sanity bound table. For each metric, if the value falls outside the stated range:
1. Log a warning with the metric name, value, expected range, ticker, and source.
2. Attempt to retrieve the same metric from an alternative source.
3. If the alternative source confirms the value (within 5% of the original), accept it as valid (the company may genuinely have an extreme metric).
4. If the alternative source gives a different value within the expected range, use the alternative.
5. If no alternative is available, flag the metric with a `LOW_CONFIDENCE` marker that downstream analysis modules must handle.

### Gate 4: Temporal Consistency

**Check:** Date ordering is correct and no future-dated data exists.

```
Rules:
- Price data dates must be in ascending chronological order
- No date should be in the future (relative to the current date)
- For quarterly financials, periods should be sequential (Q1, Q2, Q3, Q4 or in fiscal order)
- Filing dates must be after the reporting period end date
  (e.g., a 10-K for FY2024 should have a filing_date in 2025, not 2024)
- Earnings dates should align with the fiscal calendar
```

**Look-ahead bias prevention:**
- When constructing time-series for analysis, only include data that was **actually available** at each point in time.
- Example: A 10-K filed on 2025-02-28 reporting FY2024 results should not be used for any analysis pretending to be conducted before 2025-02-28.
- SEC filings have a `filing_date` field -- use this as the availability date, not the reporting period end date.

### Gate 5: Cross-Source Reconciliation

**Check:** The same metric from different sources agrees within the tolerance defined in Section 5.2.

```
Protocol:
1. For each metric in the final analysis output, pull from at least 2 sources
2. Compute variance = |source1 - source2| / max(|source1|, |source2|)
3. If variance <= threshold (see Section 5.2 table): PASS
4. If variance > threshold: INVESTIGATE per the protocol in Section 5.2
5. Record the reconciliation result (pass/fail, variance, sources, resolution)
```

**Minimum reconciliation requirements:**
- All companies in the final ranking/scoring must pass Gate 5 for: price, market cap, revenue, and net income.
- Companies failing reconciliation for secondary metrics (margins, growth rates) may proceed with a `RECONCILIATION_WARNING` flag.

---

## 8. Common Pitfalls

This section documents errors that have been encountered in practice or are known failure modes for financial data analysis. All analysts and automated pipelines must account for these.

### 8.1 Survivorship Bias

**Problem:** Historical datasets only include companies that are currently active. Companies that went bankrupt, were acquired, or were delisted are absent, making historical performance look better than it actually was.

**In our context:** If we analyze "semiconductor equipment companies over the past 10 years" using only companies that exist today, we miss companies that failed during the 2019 or 2022-2023 downturns. This makes the sector look more resilient than it is.

**Mitigation:**
- When possible, use datasets that include delisted companies.
- When analyzing historical cohorts, fix the membership list as of the start date, not the end date.
- Document any survivorship bias limitations in analysis outputs.

### 8.2 Look-Ahead Bias

**Problem:** Using information in historical analysis that was not actually available at the time. This makes backtests look unrealistically good.

**Examples:**
- Using a 10-K filing date of 2025-02-15 to inform a simulated investment decision on 2025-01-31.
- Using revised GDP figures for a period when only the advance estimate was available.
- Using current sector classifications for historical data when the company's sector was reclassified.

**Mitigation:**
- Always use `filing_date` (not period end date) for SEC data availability.
- For FRED data, use `realtime_start` and `realtime_end` parameters to get point-in-time data.
- Maintain awareness of the ~45-day delay in 10-Q filings and ~60-90-day delay in 10-K filings.

### 8.3 Split-Adjusted vs Unadjusted Price Confusion

**Problem:** Mixing adjusted and unadjusted prices in the same analysis produces incorrect returns, incorrect technical indicator signals, and incorrect volatility estimates.

**Example:** A stock trading at $300 does a 3:1 split. Post-split price is $100. Unadjusted data shows a 67% "decline" on the split day. Adjusted data shows no change.

**Mitigation:**
- yfinance `.history()` returns adjusted prices by default. Use this.
- If combining data from multiple sources, verify that all sources are using the same adjustment basis.
- When analyzing dividends or dividend yields, be aware that adjusted prices implicitly account for dividend payments.

### 8.4 Japanese Company Fiscal Years

**Problem:** Most Japanese companies in our universe (Tokyo Electron, Advantest, Shin-Etsu, Lasertec, Disco, Screen, Murata, TDK, etc.) have fiscal years ending March 31. This means their "FY2025" runs from April 2024 to March 2025.

**Impact:**
- Direct comparison of "FY2025 revenue" between Tokyo Electron (April 2024 - March 2025) and Applied Materials (November 2024 - October 2025) is comparing different time periods.
- Quarterly data requires careful alignment: Tokyo Electron's Q1 (April-June) corresponds to AMAT's Q3 (May-July) approximately.

**Mitigation:**
- Always align by calendar quarter for cross-company comparison.
- Label all financial data with the actual date range, not just "FY" or "Q" notation.
- The `configs/ai_moat_universe.yaml` file lists country codes; use these to look up fiscal year conventions.

### 8.5 ADR Ratio Differences

**Problem:** Per-share metrics (EPS, book value per share, dividend per share) differ between local shares and ADRs because of ADR ratios.

**Example:** If TSMC local shares (2330.TW) trade at 1000 TWD and the ADR ratio is 1:5 (1 ADR = 5 local shares), the ADR (TSM) should trade at approximately 5000 TWD / exchange rate. Per-share metrics on the ADR are 5x the local share values.

**Mitigation:**
- Always document whether per-share metrics are based on local shares or ADR shares.
- When comparing companies, use aggregate metrics (total revenue, total net income, total assets) rather than per-share metrics where possible.
- If per-share metrics are required, normalize by converting to a common share basis.

### 8.6 Weekend/Holiday Gaps in Price Data

**Problem:** Price data has natural gaps on weekends, US holidays, and local market holidays (Japanese Golden Week, Chinese New Year, etc.). Naive gap detection may generate false alarms.

**Mitigation:**
- Maintain a calendar of exchange holidays for each market in our universe (TSE, TWSE, KRX, NYSE, NASDAQ, Euronext).
- When checking for gaps, compare against **expected trading days**, not calendar days.
- For multi-market analysis, be aware that different exchanges may be closed on different days.

### 8.7 After-Hours vs Regular Session Data

**Problem:** yfinance and some other sources include pre-market and after-hours trading data by default in some configurations. This can affect OHLCV calculations.

**Mitigation:**
- Use regular session data only for technical analysis (standard OHLCV).
- After-hours data is useful only for: earnings reaction analysis, gap analysis, and real-time monitoring.
- The `yfinance` `.history()` method returns regular session data by default; verify this has not changed with library updates.

### 8.8 Currency Conversion Timing

**Problem:** When converting financial figures from JPY/TWD/KRW to USD, the exchange rate used must match the date of the financial data. Using today's exchange rate with last quarter's financials introduces distortion.

**Mitigation:**
- For balance sheet items: use the exchange rate on the balance sheet date.
- For income statement items: use the average exchange rate for the reporting period.
- For stock prices: use the same-day exchange rate.
- Source exchange rates from a reliable provider (FRED has `DEXJPUS` for JPY/USD, for example).

### 8.9 Index Reconstitution

**Problem:** Major indices (S&P 500, NASDAQ-100) periodically add and remove constituents. Historical analysis of "the index" may use current constituents retroactively, introducing survivorship bias.

**Mitigation:**
- Document the date of any index membership check.
- For historical analysis, use point-in-time index membership where available.

### 8.10 Data Provider API Changes

**Problem:** yfinance is an unofficial library that scrapes Yahoo Finance. It can and does break when Yahoo changes their site structure. Similar risks exist with Finviz scraping.

**Mitigation:**
- Always have a fallback source configured (per `configs/settings.yaml` fallback chains).
- Monitor for library updates and breaking changes.
- The fallback chain in our configuration: `market_data: primary: yfinance, fallback: [finnhub, alpaca]`.
- Test data retrieval for critical tickers after any library update.

---

## 9. Error Handling

### 9.1 Missing Data

**Rule:** Use `NaN` (numpy/pandas null), never impute without documentation.

```
If a metric is unavailable:
  1. Set the value to NaN / None
  2. Log: "{ticker} - {metric} unavailable from {source} at {timestamp}"
  3. Attempt fallback source per the priority chain
  4. If all sources fail, the metric remains NaN
  5. Downstream analysis modules MUST handle NaN gracefully (skip, exclude, or use conservative defaults)
```

**Never do this:**
- Fill missing revenue with 0 (it will look like the company has no revenue)
- Fill missing P/E with the sector average (it will bias the analysis toward the mean)
- Interpolate missing quarterly data (you are fabricating earnings reports)
- Forward-fill fundamental data across quarters without labeling it as "prior quarter value"

**Exception:** Forward-filling daily price data for 1-2 day gaps (holidays) is acceptable for technical indicators that require continuous series. Document the fill.

### 9.2 API Failures

**Fallback chain protocol:**

```
Step 1: Attempt primary source
Step 2: If primary fails (HTTP error, timeout, empty response):
  - Log the failure: "{source} failed for {ticker}: {error_type} at {timestamp}"
  - Wait 2 seconds (basic backoff)
  - Retry once
Step 3: If retry fails:
  - Move to fallback source (per configs/settings.yaml)
  - Log: "Falling back from {primary} to {fallback} for {ticker}"
Step 4: If all sources fail:
  - Check cache (even if expired)
  - If cached data exists within 2x TTL, use it with a STALE_DATA flag
  - If no cache: return NaN and log "ALL SOURCES FAILED for {ticker}.{metric}"
Step 5: Aggregate failures for monitoring
  - If the same source fails for >3 consecutive tickers, mark the source as DOWN
  - When a source is DOWN, skip directly to fallback for all subsequent requests in the session
```

### 9.3 Rate Limits

**Configured limits for our data sources:**

| Source | Rate Limit | Implementation |
|--------|-----------|----------------|
| yfinance | ~2,000 calls/day | Batch requests where possible; use `get_multiple()` |
| Finnhub | 60 calls/minute | `RateLimiter(calls_per_minute=60)` |
| SEC EDGAR | 10 requests/second | `RateLimiter(calls_per_minute=600)` with `User-Agent` header |
| FRED | 120 requests/minute | `RateLimiter(calls_per_minute=120)` |
| SimFin | 2 calls/second | `RateLimiter(calls_per_minute=120)` |
| Reddit (PRAW) | 60 requests/minute (OAuth) | Handled by PRAW internally |
| Finviz | Undocumented (be respectful) | Max 1 request per 2 seconds |

**Exponential backoff on rate limit errors (HTTP 429):**
```
Attempt 1: Wait 1 second
Attempt 2: Wait 2 seconds
Attempt 3: Wait 4 seconds
Attempt 4: Wait 8 seconds
Attempt 5: Wait 16 seconds
After 5 attempts: Move to fallback source
```

The `RateLimiter` class in `src/utils/rate_limiter.py` implements token-bucket rate limiting. Ensure it is used for all API calls.

### 9.4 Partial Data

**Rule:** Flag and document, proceed with available data if completeness exceeds 80%.

```
Completeness assessment:
  >= 95% complete: PASS -- proceed normally
  80% - 94% complete: PROCEED WITH WARNING -- flag as PARTIAL_DATA
  50% - 79% complete: PROCEED WITH CAUTION -- flag as DEGRADED_DATA; exclude from ranking/scoring
  < 50% complete: FAIL -- exclude from analysis entirely; log as INSUFFICIENT_DATA
```

**Example:** If we request 20 quarters of financial data for Lasertec (6920.T) and receive only 16 (due to data source coverage starting in 2021), that is 80% completeness. Proceed with a `PARTIAL_DATA` flag and note the coverage gap.

---

## 10. Implementation Reference

### 10.1 Data Source to Module Mapping

This maps each data type to its implementing module in the codebase:

| Data Type | Module | Class | Key Methods |
|-----------|--------|-------|-------------|
| Price / OHLCV / Quotes | `src/data_sources/market_data.py` | `MarketDataClient` | `get_price_history()`, `get_current_price()`, `get_quote()`, `get_multiple()` |
| Fundamentals / Ratios | `src/data_sources/fundamentals.py` | `FundamentalsClient` | `get_income_statement()`, `get_balance_sheet()`, `get_cash_flow()`, `get_key_ratios()`, `get_company_profile()`, `get_peers()` |
| SEC Filings / XBRL | `src/data_sources/sec_filings.py` | `SECFilingsClient` | `get_recent_filings()`, `get_financials_xbrl()`, `search_filings()` |
| News / Sentiment | `src/data_sources/news_sentiment.py` | `NewsSentimentClient` | `get_company_news()`, `get_market_news()`, `analyze_sentiment()`, `get_news_with_sentiment()` |
| Macro / Economic | `src/data_sources/macro_data.py` | `MacroDataClient` | `get_fred_series()`, `get_treasury_yields()`, `get_risk_free_rate()`, `get_economic_indicators()`, `get_world_bank_indicator()` |
| Alternative Data | `src/data_sources/alternative_data.py` | `AlternativeDataClient` | `get_reddit_sentiment()`, `get_insider_trades()`, `get_institutional_ownership()`, `get_analyst_recommendations()` |
| Stock Screening | `src/data_sources/screener.py` | `StockScreener` | `screen()`, `value_stocks()`, `growth_stocks()`, `momentum_stocks()`, `dividend_stocks()` |

### 10.2 Configuration Files

| File | Purpose |
|------|---------|
| `configs/settings.yaml` | Cache TTL, analysis defaults, source priorities, indicator lists |
| `configs/ai_moat_universe.yaml` | Complete AI supply chain company universe with tickers, ADR mappings, moat scores, and category assignments |
| `.env` (not committed) | API keys for Finnhub, FRED, SimFin, Reddit, SEC User-Agent, etc. |
| `src/config.py` | Central configuration loader; `Keys` class (API keys), `Paths` class (directory paths), `SETTINGS` dict |

### 10.3 Cache Architecture

The `DataCache` class (`src/utils/cache.py`) provides:
- **File-based storage** in `data/cache/{category}/` directories
- **TTL-based expiry** configured per category in `settings.yaml`
- **Parquet format** for DataFrames (via `get_df` / `set_df`) -- preserves types and is compact
- **JSON format** for dict data (via `get` / `set`)
- **MD5-hashed filenames** derived from cache keys

**Cache key conventions:**
```
Price data:      "{ticker}_{period}_{interval}"     e.g., "ASML_1y_1d"
Income stmt:     "income_{ticker}_{q|a}"            e.g., "income_LRCX_q"
Balance sheet:   "balance_{ticker}_{q|a}"           e.g., "balance_8035.T_a"
Cash flow:       "cashflow_{ticker}_{q|a}"          e.g., "cashflow_TSM_a"
FRED series:     "fred_{series_id}_{start}"         e.g., "fred_DGS10_2015-01-01"
```

### 10.4 Required API Keys

These must be set in the `.env` file (see `src/config.py` `Keys` class):

| Environment Variable | Source | Required For |
|---------------------|--------|-------------|
| `FINNHUB_API_KEY` | finnhub.io | Quotes, fundamentals, news, insider trades, peers |
| `FRED_API_KEY` | fred.stlouisfed.org | All macroeconomic data |
| `SIMFIN_API_KEY` | simfin.com | Fundamental data (financial statements) |
| `REDDIT_CLIENT_ID` | reddit.com/prefs/apps | Reddit sentiment data |
| `REDDIT_CLIENT_SECRET` | reddit.com/prefs/apps | Reddit sentiment data |
| `REDDIT_USER_AGENT` | (self-defined) | Reddit API identification |
| `SEC_USER_AGENT` | (self-defined, format: "Name email@example.com") | SEC EDGAR access (required header) |
| `FMP_API_KEY` | financialmodelingprep.com | Supplementary fundamental data |
| `ALPACA_API_KEY` | alpaca.markets | Fallback price data |
| `ALPACA_SECRET_KEY` | alpaca.markets | Fallback price data |

---

## 11. Checklist: Before Starting Any Analysis

Use this checklist before running any analysis pipeline. Every item must be confirmed.

```
[ ] 1. API keys are configured and tested (run a smoke test for each source)
[ ] 2. Cache directory exists and has appropriate disk space
[ ] 3. For each target ticker:
    [ ] a. Price data retrieved with sufficient history (per Section 4.1.5)
    [ ] b. Price data completeness validated (per Section 5.1)
    [ ] c. Correct ticker format used for the exchange (per Section 4.1.3)
    [ ] d. Currency identified and documented (per Section 4.1.4)
[ ] 4. Fundamental data retrieved from SEC filings where available
[ ] 5. Balance sheet identity verified (A = L + E)
[ ] 6. Fiscal year alignment documented for cross-company comparisons
[ ] 7. GAAP vs non-GAAP treatment is consistent across compared companies
[ ] 8. Macro indicators are current (check against release schedule)
[ ] 9. Sentiment data is within freshness requirements (per Section 4.3.1)
[ ] 10. All data has passed the five quality gates (Section 7)
[ ] 11. Any data warnings (PARTIAL_DATA, STALE_DATA, LOW_CONFIDENCE) are documented
[ ] 12. Cross-source reconciliation completed for key metrics
```

---

## 12. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-09 | FE-Analyst Team | Initial release |

---

*This SOP is a living document. It should be updated whenever new data sources are added, existing source behavior changes, or new failure modes are discovered. Proposed changes should be reviewed before incorporation.*
