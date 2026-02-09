# SOP-006: Technical Analysis

**Document ID:** SOP-006
**Version:** 1.0
**Effective Date:** 2026-02-09
**Applies To:** All technical analysis activities within the FE-Analyst platform
**Module:** `src/analysis/technical.py`
**Config:** `configs/settings.yaml` (section: `analysis.technical`)
**Review Cycle:** Quarterly, or upon addition of new indicators
**Status:** Active

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Theoretical Foundation -- What Technical Analysis Is and Is Not](#2-theoretical-foundation----what-technical-analysis-is-and-is-not)
3. [Data Requirements and Preprocessing](#3-data-requirements-and-preprocessing)
4. [Technical Indicators -- Deep Dive](#4-technical-indicators----deep-dive)
   - 4.1 [Simple Moving Average (SMA)](#41-simple-moving-average-sma)
   - 4.2 [Exponential Moving Average (EMA)](#42-exponential-moving-average-ema)
   - 4.3 [Relative Strength Index (RSI)](#43-relative-strength-index-rsi)
   - 4.4 [Moving Average Convergence Divergence (MACD)](#44-moving-average-convergence-divergence-macd)
   - 4.5 [Bollinger Bands](#45-bollinger-bands)
   - 4.6 [Average True Range (ATR)](#46-average-true-range-atr)
   - 4.7 [On-Balance Volume (OBV)](#47-on-balance-volume-obv)
   - 4.8 [Stochastic RSI](#48-stochastic-rsi)
5. [Signal Generation Rules](#5-signal-generation-rules)
6. [Signal Aggregation and Scoring](#6-signal-aggregation-and-scoring)
7. [Timeframe Selection and Multi-Timeframe Analysis](#7-timeframe-selection-and-multi-timeframe-analysis)
8. [Support, Resistance, and Chart Pattern Recognition](#8-support-resistance-and-chart-pattern-recognition)
9. [Integration with the Analysis Pipeline](#9-integration-with-the-analysis-pipeline)
10. [Configuration Reference](#10-configuration-reference)
11. [Example Workflows](#11-example-workflows)
12. [Limitations and Caveats](#12-limitations-and-caveats)
13. [Troubleshooting Common Issues](#13-troubleshooting-common-issues)
14. [Appendix A -- Indicator Quick Reference](#appendix-a----indicator-quick-reference)
15. [Appendix B -- Signal Decision Trees](#appendix-b----signal-decision-trees)
16. [Appendix C -- Recommended Reading Periods by Analysis Goal](#appendix-c----recommended-reading-periods-by-analysis-goal)

---

## 1. Purpose and Scope

### Why This Analysis Exists

Technical analysis examines historical price and volume data to identify patterns, trends, and statistical signals that inform trading decisions. Within the FE-Analyst platform, the technical analysis module provides the **timing dimension** that other analysis types cannot. Fundamental analysis answers "What is the company worth?" Valuation analysis answers "Is the price attractive relative to intrinsic value?" Technical analysis answers a different and complementary question: **"What is the price doing right now, and what does the current trajectory suggest about near-term direction?"**

For the AI chip supply chain universe tracked by FE-Analyst, technical analysis serves several critical purposes:

1. **Entry and exit timing.** A fundamentally sound stock (high composite score, WIDE MOAT) can still be a poor near-term purchase if it is overextended, overbought, or breaking down from a major support level. Technical analysis provides the timing overlay that prevents buying into short-term weakness or selling into short-term strength.

2. **Trend confirmation.** When fundamental analysis says a company is improving and technical analysis confirms an uptrend, conviction increases. When the two disagree, it is a signal to investigate further.

3. **Risk management.** Technical indicators like ATR (Average True Range) quantify volatility and help set appropriate position sizes and stop-loss levels. Bollinger Bands identify when a stock is at statistical extremes.

4. **Signal generation for the composite score.** The technical analysis score contributes **20% weight** to the platform's composite stock score (as configured in `configs/settings.yaml`). This makes it the third-highest weighted component after Fundamental (25-30%) and Valuation (20-25%).

### Scope

This SOP covers:

- **What:** The full set of technical indicators computed by `TechnicalAnalyzer.compute_indicators()`, the signal generation logic in `TechnicalAnalyzer.get_signals()`, the support/resistance detection in `TechnicalAnalyzer.get_support_resistance()`, and the pipeline integration via `TechnicalAnalyzerPlugin`.
- **Who:** All stocks processed through the FE-Analyst pipeline, including the 60+ AI supply chain companies and any ad-hoc tickers analyzed via `main.py analyze`.
- **How:** Using the Python `ta` (Technical Analysis) library for indicator computation, with `pandas` DataFrames as the data structure and `yfinance` as the primary price data source.
- **Why:** To provide an objective, reproducible, quantitative assessment of a stock's price-based momentum and trend characteristics.

### Relationship to Other Analyses

| Analysis Module | Primary Question | Timeframe Focus | Weight in Composite |
|---|---|---|---|
| Fundamental (`SOP-002`) | "Is this a healthy, growing business?" | 3-5 years | 25-30% |
| Valuation (`SOP-003`) | "Is the stock priced below intrinsic value?" | 1-3 years | 20-25% |
| **Technical (`this SOP`)** | **"What is the price trend and momentum?"** | **Days to months** | **20%** |
| Risk (`SOP-004`) | "How volatile and risky is this stock?" | 1 year | 15% |
| Sentiment | "What is market sentiment saying?" | Days to weeks | 10% |
| Moat (`SOP-005`) | "Is the competitive advantage durable?" | 5-10 years | Parallel overlay |

Technical analysis is most valuable when combined with other dimensions. A stock that scores highly on fundamentals and valuation but poorly on technicals may be a "value trap" -- cheap for a reason that the market is pricing in through persistent selling. Conversely, a stock that scores well on technicals but poorly on fundamentals may be a momentum trade with limited staying power.

---

## 2. Theoretical Foundation -- What Technical Analysis Is and Is Not

### 2.1 Core Assumptions

Technical analysis rests on three assumptions. Understanding these assumptions -- and their limitations -- is essential for using the output correctly.

**Assumption 1: Market action discounts everything.**
The current price reflects all known information -- fundamentals, sentiment, macroeconomics, insider knowledge. Price is the ultimate arbiter. We do not need to know *why* a stock is moving; the movement itself contains information.

**Assumption 2: Prices move in trends.**
Stocks in motion tend to stay in motion. Uptrends persist because buyers continue to appear at progressively higher prices. Downtrends persist because sellers continue to accept progressively lower prices. The goal of technical analysis is to identify trends early and ride them until evidence of reversal appears.

**Assumption 3: History tends to repeat.**
Market participants respond to similar price patterns in similar ways because human psychology -- fear, greed, hope, regret -- does not change. Patterns that worked in the past have a statistical edge in the future, though the edge is probabilistic, not deterministic.

### 2.2 What Technical Analysis Can Tell You

- **Trend direction:** Is the stock in an uptrend, downtrend, or consolidation?
- **Momentum strength:** Is the trend accelerating or decelerating?
- **Overbought/oversold conditions:** Has the price moved too far too fast?
- **Support and resistance levels:** Where are the price levels that buyers and sellers have historically concentrated?
- **Volatility regime:** Is the stock in a high-volatility or low-volatility phase?
- **Volume confirmation:** Is the price movement supported by conviction (volume)?

### 2.3 What Technical Analysis Cannot Tell You

- **Intrinsic value.** Technical analysis says nothing about what a stock is worth. A stock can be overbought and still undervalued, or oversold and still overvalued.
- **Fundamental health.** A perfect uptrend with strong momentum tells you nothing about the company's balance sheet, revenue growth, or competitive position.
- **Black swan events.** Technical analysis cannot predict earnings surprises, regulatory actions, geopolitical events, or other sudden exogenous shocks.
- **Long-term direction with certainty.** All signals are probabilistic. A BUY signal means the statistical edge favors upward movement, not that upward movement will definitely occur.
- **Causation.** Technical analysis identifies correlations and patterns. It does not explain why prices are moving in a particular direction.

### 2.4 Appropriate Use Within FE-Analyst

Technical analysis should be used as **one input among many**, never as the sole basis for an investment decision. Its appropriate uses within our platform include:

- **Confirming or challenging** conclusions from fundamental and valuation analysis
- **Timing** entries and exits for positions that have already been justified on fundamental grounds
- **Identifying** potential trend changes that warrant investigation into underlying causes
- **Quantifying** the near-term momentum component of the composite stock score
- **Setting** risk management parameters (stop-loss levels, position sizes)

It should **never** be used to:
- Override a strong fundamental thesis with a contradictory short-term signal
- Make high-conviction long-term investment decisions on technical signals alone
- Predict specific future prices or price targets
- Replace the due diligence process with pattern matching

---

## 3. Data Requirements and Preprocessing

### 3.1 Input Data Format

The `TechnicalAnalyzer.compute_indicators()` method expects a pandas DataFrame with the following schema:

```python
# Required columns
columns = ["Open", "High", "Low", "Close", "Volume"]

# Required index
index_type = pd.DatetimeIndex  # Sorted ascending by date

# Data type expectations
# Open, High, Low, Close: float64 (adjusted prices)
# Volume: int64 or float64
```

This format matches the output of `yfinance` `Ticker.history()` and `MarketDataClient.get_price_history()`.

### 3.2 Minimum Data Requirements

Each technical indicator requires a minimum amount of historical data to produce its first valid value. The indicator with the longest lookback period determines the minimum data requirement for the full suite.

| Indicator | Lookback Required | First Valid Value At |
|---|---|---|
| SMA(20) | 20 trading days | Day 20 |
| SMA(50) | 50 trading days | Day 50 |
| SMA(200) | 200 trading days | Day 200 |
| EMA(12) | ~26 trading days (for convergence) | Day 12 (approximate earlier) |
| EMA(26) | ~52 trading days (for convergence) | Day 26 (approximate earlier) |
| RSI(14) | 15 trading days | Day 15 |
| MACD(12,26,9) | 35 trading days (26 + 9) | Day 35 |
| Bollinger Bands(20,2) | 20 trading days | Day 20 |
| ATR(14) | 15 trading days | Day 15 |
| OBV | 1 trading day | Day 1 |

**Minimum practical requirement:** Because the SMA(200) requires 200 trading days (approximately 10 months), and because the MACD and other indicators need additional data for convergence, the platform default is **1 year of daily data** (`analysis.technical.default_period: "1y"` in `settings.yaml`). This provides approximately 252 trading days.

**Recommended data:** For reliable SMA(200) signals and smooth MACD readings, **2 years of daily data** is recommended. The `main.py analyze --profile deep_dive` profile fetches 2 years by default.

### 3.3 Data Quality Prerequisites

Before passing data to `TechnicalAnalyzer`, ensure the following (per SOP-001):

1. **Adjusted close prices.** All prices must be split-adjusted and dividend-adjusted. The `ta` library computes indicators from the values provided; unadjusted prices will produce incorrect signals.

2. **No missing trading days.** Gaps in the date index (excluding weekends and holidays) will distort rolling calculations. Forward-fill gaps of 1-2 days; flag and investigate gaps of 3+ days.

3. **Positive volume.** Zero-volume days should be flagged. The OBV indicator accumulates volume directionally; zero-volume days produce flat OBV readings that may create false consolidation signals.

4. **Chronological ordering.** The DataFrame index must be sorted in ascending date order. The `ta` library processes data sequentially; reverse ordering will produce nonsensical results.

5. **No future data.** Ensure the DataFrame does not contain data points from the future (look-ahead bias). The `iloc[-1]` access pattern in `get_signals()` relies on the last row being the most recent data point.

### 3.4 Data Source Configuration

The price data source is configured in `settings.yaml`:

```yaml
data_sources:
  market_data:
    primary: yfinance
    fallback: [finnhub, alpaca]

analysis:
  technical:
    default_period: "1y"
    indicators: [sma, ema, rsi, macd, bbands, atr, obv]
```

The `default_period` parameter controls how much history `MarketDataClient.get_price_history()` fetches. Valid values follow `yfinance` period conventions: `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `max`.

---

## 4. Technical Indicators -- Deep Dive

The `TechnicalAnalyzer.compute_indicators()` method adds the following columns to the OHLCV DataFrame. Each indicator is computed using the `ta` (Technical Analysis) library.

### 4.1 Simple Moving Average (SMA)

#### What It Measures

The SMA calculates the arithmetic mean of closing prices over a specified window. It smooths out short-term fluctuations and reveals the underlying trend direction.

#### Implementation

```python
from ta.trend import SMAIndicator

result["SMA_20"]  = SMAIndicator(close, window=20).sma_indicator()
result["SMA_50"]  = SMAIndicator(close, window=50).sma_indicator()
result["SMA_200"] = SMAIndicator(close, window=200).sma_indicator()
```

#### Windows and Their Meaning

| Window | Column | Purpose | Timeframe |
|---|---|---|---|
| 20 | `SMA_20` | Short-term trend; approximates 1 month of trading | Swing trading (days to weeks) |
| 50 | `SMA_50` | Medium-term trend; approximates 1 quarter of trading | Position trading (weeks to months) |
| 200 | `SMA_200` | Long-term trend; approximates 1 year of trading | Secular trend identification |

#### Interpretation Rules

1. **Price relative to SMA:** When the price is above the SMA, the trend is bullish for that timeframe. When below, bearish.

2. **SMA slope:** A rising SMA indicates an uptrend; a falling SMA indicates a downtrend. The slope matters more than the current position.

3. **SMA crossovers:**
   - **Golden Cross:** SMA(50) crosses above SMA(200). This is a major bullish signal indicating a potential long-term trend reversal from bearish to bullish.
   - **Death Cross:** SMA(50) crosses below SMA(200). Major bearish signal.
   - **Short-term cross:** SMA(20) crossing above or below SMA(50) provides a faster but noisier signal.

4. **SMA as dynamic support/resistance:** In uptrends, the SMA(50) and SMA(200) often act as support levels where buyers step in. In downtrends, they act as resistance levels where sellers appear.

#### Semiconductor-Specific Considerations

Semiconductor stocks exhibit pronounced cyclicality (typically 3-5 year cycles). The SMA(200) is particularly useful for identifying the secular trend within a cycle:

- **Cyclical upturn:** Price crosses above and stays above the SMA(200). Equipment makers (TEL, LRCX, AMAT) and memory companies (SK Hynix, Micron) tend to show this pattern 6-12 months before earnings inflect upward.
- **Cyclical downturn:** Price crosses below and stays below the SMA(200). This often precedes 12-18 months of deteriorating fundamentals.

The SMA(200) for cyclical semiconductor stocks should be interpreted in the context of the semiconductor cycle, not treated as a standalone signal.

---

### 4.2 Exponential Moving Average (EMA)

#### What It Measures

The EMA gives more weight to recent prices, making it more responsive to new information than the SMA. The weighting follows an exponential decay: the most recent price has the highest weight, with each prior day's weight decreasing exponentially.

#### Implementation

```python
from ta.trend import EMAIndicator

result["EMA_12"] = EMAIndicator(close, window=12).ema_indicator()
result["EMA_26"] = EMAIndicator(close, window=26).ema_indicator()
```

#### Windows and Their Meaning

| Window | Column | Purpose |
|---|---|---|
| 12 | `EMA_12` | Fast EMA; responds quickly to price changes; used as MACD fast line |
| 26 | `EMA_26` | Slow EMA; smoother trend indicator; used as MACD slow line |

#### EMA vs SMA

| Characteristic | SMA | EMA |
|---|---|---|
| Weighting | Equal weight to all periods | Exponential decay (recent > older) |
| Responsiveness | Slower to react | Faster to react |
| Lag | More lag | Less lag |
| Whipsaws | Fewer false signals | More false signals |
| Best use case | Trend identification | Momentum detection, MACD input |

#### When to Prefer EMA Over SMA

- **Fast-moving stocks:** High-beta semiconductor stocks (NVDA, AMD, ASML) benefit from EMA's responsiveness because significant moves happen quickly and the SMA lags too much to be useful for timing.
- **MACD calculation:** The MACD indicator (Section 4.4) is defined as the difference between the EMA(12) and EMA(26). These EMAs serve as the fast and slow components.
- **Short-term trading signals:** For timeframes of days to weeks, EMAs provide earlier signals than SMAs.

---

### 4.3 Relative Strength Index (RSI)

#### What It Measures

The RSI measures the speed and magnitude of recent price changes on a scale of 0 to 100. It identifies overbought and oversold conditions by comparing the average gain to the average loss over a lookback period.

#### Implementation

```python
from ta.momentum import RSIIndicator

result["RSI_14"] = RSIIndicator(close, window=14).rsi()
```

#### Calculation

The RSI formula uses a 14-period lookback (industry standard):

```
Average Gain = Average of upward price changes over 14 periods
Average Loss = Average of downward price changes over 14 periods
RS = Average Gain / Average Loss
RSI = 100 - (100 / (1 + RS))
```

#### Signal Generation (as implemented in `get_signals()`)

```python
if rsi < 30:
    signals["rsi"] = {"signal": "BUY", "value": round(rsi, 2), "reason": "Oversold"}
elif rsi > 70:
    signals["rsi"] = {"signal": "SELL", "value": round(rsi, 2), "reason": "Overbought"}
else:
    signals["rsi"] = {"signal": "HOLD", "value": round(rsi, 2), "reason": "Neutral"}
```

#### RSI Threshold Decision Tree

```
RSI Value Assessment:

  RSI < 20  --> Extremely oversold. Strong BUY signal. Rare occurrence;
                suggests panic selling or capitulation.
                Action: BUY signal. Investigate for catalysts.

  RSI 20-30 --> Oversold. BUY signal. Stock has been sold heavily;
                a bounce is statistically likely.
                Action: BUY signal. Look for confirmation from other indicators.

  RSI 30-50 --> Below midpoint but not oversold. Mild bearish lean.
                Action: HOLD signal. No strong directional edge.

  RSI 50    --> Neutral. Exactly balanced between buying and selling pressure.
                Action: HOLD signal.

  RSI 50-70 --> Above midpoint but not overbought. Mild bullish lean.
                Action: HOLD signal. Trend is modestly positive.

  RSI 70-80 --> Overbought. SELL signal. Stock has been bought heavily;
                a pullback is statistically likely.
                Action: SELL signal. Consider reducing exposure.

  RSI > 80  --> Extremely overbought. Strong SELL signal. Rare;
                suggests euphoria or momentum blow-off.
                Action: SELL signal. High probability of mean reversion.
```

#### RSI Divergences (Advanced Pattern)

RSI divergences are among the most reliable technical signals. They occur when price and RSI move in opposite directions:

- **Bullish divergence:** Price makes a lower low, but RSI makes a higher low. This indicates that selling pressure is weakening even as price declines, suggesting an impending reversal to the upside.
- **Bearish divergence:** Price makes a higher high, but RSI makes a lower high. This indicates that buying pressure is weakening even as price rises, suggesting an impending reversal to the downside.

**Note:** The current `get_signals()` implementation does not detect RSI divergences. It uses only the current RSI value relative to the 30/70 thresholds. Divergence detection is a candidate for future enhancement.

#### RSI for Semiconductor Stocks

Semiconductor stocks, particularly equipment and foundry companies, can sustain RSI readings above 70 for extended periods during the up-cycle of the semiconductor cycle. An RSI of 75 for ASML during a strong capex cycle does not necessarily mean "sell" -- it means "the trend is very strong." Context from the cycle position (available from fundamental and macro analysis) should be used to interpret RSI readings for cyclical companies.

Conversely, during a semiconductor downturn, RSI can stay below 30 for weeks as the market reprices expectations downward. An RSI of 25 for a memory company in a downturn may be an accurate reflection of deteriorating fundamentals rather than a buying opportunity.

---

### 4.4 Moving Average Convergence Divergence (MACD)

#### What It Measures

The MACD measures the relationship between two EMAs and provides both trend direction and momentum information. It consists of three components:

1. **MACD Line:** EMA(12) minus EMA(26). Represents momentum.
2. **Signal Line:** EMA(9) of the MACD Line. Represents the smoothed trend of momentum.
3. **Histogram:** MACD Line minus Signal Line. Represents the acceleration of momentum.

#### Implementation

```python
from ta.trend import MACD

macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
result["MACD"]        = macd.macd()           # MACD line
result["MACD_signal"] = macd.macd_signal()     # Signal line
result["MACD_hist"]   = macd.macd_diff()       # Histogram
```

#### Signal Generation (as implemented in `get_signals()`)

```python
if macd_val > macd_signal:
    signals["macd"] = {"signal": "BUY", "reason": "MACD above signal"}
else:
    signals["macd"] = {"signal": "SELL", "reason": "MACD below signal"}
```

The current implementation uses a simple crossover: MACD above signal = BUY, MACD below signal = SELL. There is no HOLD state for MACD because the MACD line is always either above or below (or exactly equal to) the signal line.

#### MACD Signal Interpretation

| Condition | Meaning | Signal |
|---|---|---|
| MACD crosses above signal line | Bullish crossover; momentum turning positive | BUY |
| MACD crosses below signal line | Bearish crossover; momentum turning negative | SELL |
| MACD and signal both above zero | Uptrend with positive momentum | Trend confirmation (bullish) |
| MACD and signal both below zero | Downtrend with negative momentum | Trend confirmation (bearish) |
| Histogram expanding (positive) | Bullish momentum accelerating | Strong BUY |
| Histogram contracting (positive) | Bullish momentum decelerating | Potential trend weakening |
| Histogram expanding (negative) | Bearish momentum accelerating | Strong SELL |
| Histogram contracting (negative) | Bearish momentum decelerating | Potential bottom forming |

#### MACD Divergences

Like RSI divergences, MACD divergences signal weakening momentum:

- **Bullish MACD divergence:** Price makes a new low, but MACD makes a higher low. The selling momentum is fading.
- **Bearish MACD divergence:** Price makes a new high, but MACD makes a lower high. The buying momentum is fading.

MACD divergences, especially when combined with RSI divergences, are among the strongest reversal signals in technical analysis.

#### MACD for Trend-Following vs Range-Bound Markets

MACD works best in **trending markets**. In range-bound or choppy markets, the MACD will produce frequent whipsaw signals (rapid alternation between BUY and SELL) that generate false signals. When other indicators suggest a stock is range-bound (e.g., Bollinger Band width is narrow, ATR is low), MACD signals should be given reduced weight.

---

### 4.5 Bollinger Bands

#### What It Measures

Bollinger Bands measure volatility by placing bands at a fixed number of standard deviations above and below a moving average. They identify statistical extremes in price -- when a stock is trading at unusually high or low levels relative to its recent behavior.

#### Implementation

```python
from ta.volatility import BollingerBands

bb = BollingerBands(close, window=20, window_dev=2)
result["BB_upper"] = bb.bollinger_hband()     # Upper band (SMA + 2 std)
result["BB_lower"] = bb.bollinger_lband()     # Lower band (SMA - 2 std)
result["BB_mid"]   = bb.bollinger_mavg()      # Middle band (SMA 20)
```

#### Parameters

| Parameter | Value | Meaning |
|---|---|---|
| `window` | 20 | Lookback period for both the SMA and standard deviation calculation |
| `window_dev` | 2 | Number of standard deviations for band width |

With a 2-standard-deviation setting, approximately 95% of price action should fall within the bands under a normal distribution assumption.

#### Signal Generation (as implemented in `get_signals()`)

```python
if price < bb_lower:
    signals["bbands"] = {"signal": "BUY", "reason": "Below lower band"}
elif price > bb_upper:
    signals["bbands"] = {"signal": "SELL", "reason": "Above upper band"}
else:
    signals["bbands"] = {"signal": "HOLD", "reason": "Within bands"}
```

#### Bollinger Band Interpretation

| Condition | Meaning | Signal |
|---|---|---|
| Price touches/crosses below lower band | Stock at 2 std below mean; statistically oversold | BUY |
| Price touches/crosses above upper band | Stock at 2 std above mean; statistically overbought | SELL |
| Price within bands | Normal price action | HOLD |
| Bands narrowing ("squeeze") | Volatility contracting; big move likely imminent | Prepare for breakout |
| Bands widening | Volatility expanding; trending market | Trend following appropriate |
| Price "walking the band" (touching repeatedly) | Very strong trend; band contact is not mean-reverting | Do NOT fade the trend |

#### The Bollinger Band Squeeze

When the bands contract to unusually narrow width, it indicates a period of low volatility. Markets alternate between periods of low and high volatility, so a squeeze often precedes a significant move. The direction of the breakout (above the upper band or below the lower band) determines whether the signal is bullish or bearish.

**Warning:** The current implementation does not explicitly detect squeezes. It only evaluates the current price position relative to the bands. Squeeze detection is a candidate for future enhancement.

#### Bollinger Bands for Volatile Semiconductor Stocks

Semiconductor stocks, particularly equipment makers and memory companies, exhibit higher volatility than the broader market. This means:

- Band touches are **more frequent** than for low-volatility defensive stocks. A semiconductor stock touching the lower band is a weaker signal than a utility stock touching the lower band.
- **Band walking** is common during strong semiconductor cycle moves. ASML during a capex upcycle can trade at or above the upper band for weeks. Interpreting this as "sell" would be premature; it indicates trend strength, not exhaustion.
- The **squeeze setup** is particularly useful for semiconductor stocks because these stocks often consolidate before reporting earnings or before major industry events (SEMICON trade shows, customer capex announcements).

---

### 4.6 Average True Range (ATR)

#### What It Measures

The ATR measures volatility by calculating the average of "true ranges" over a lookback period. The true range for each day is the greatest of:

1. Current High minus Current Low
2. Absolute value of (Current High minus Previous Close)
3. Absolute value of (Current Low minus Previous Close)

This accounts for gaps (overnight price changes) that the simple High-Low range would miss.

#### Implementation

```python
from ta.volatility import AverageTrueRange

result["ATR_14"] = AverageTrueRange(high, low, close, window=14).average_true_range()
```

#### Use Cases

ATR is **not used directly for signal generation** in the current `get_signals()` implementation. Instead, it serves as a **volatility measure** for:

1. **Stop-loss placement:** A common approach is to set a stop-loss at 2x ATR below the entry price. This accounts for normal volatility and prevents stops from being triggered by routine price fluctuations.

   ```
   Stop-Loss Level = Entry Price - (2 x ATR_14)
   ```

2. **Position sizing:** Higher ATR means higher volatility, which means a smaller position is appropriate for the same dollar risk:

   ```
   Position Size (shares) = Dollar Risk / (ATR_14 x Multiplier)
   ```

3. **Volatility regime identification:** When ATR is rising, the stock is becoming more volatile. When ATR is falling, volatility is contracting. This context is useful for interpreting other signals -- signals are less reliable in high-volatility regimes.

4. **Support/resistance buffer:** Support and resistance levels identified by `get_support_resistance()` can be given a buffer zone equal to 1x ATR to account for normal noise around those levels.

#### ATR Values in Context

ATR is expressed in the same units as the stock price (dollars, yen, etc.), so it must be interpreted relative to the stock price. A $5 ATR for a $50 stock (10% of price) is very different from a $5 ATR for a $500 stock (1% of price).

**Normalized ATR (ATR / Close)** provides a comparable volatility measure across different price levels:

| Normalized ATR | Volatility Regime | Implication |
|---|---|---|
| < 1.5% | Low volatility | Tight stops feasible; breakout potential |
| 1.5% - 3.0% | Normal volatility | Standard risk management |
| 3.0% - 5.0% | Elevated volatility | Wider stops needed; reduce position size |
| > 5.0% | High volatility | Caution; consider reducing exposure |

---

### 4.7 On-Balance Volume (OBV)

#### What It Measures

OBV is a cumulative volume indicator that adds volume on up days and subtracts volume on down days. It measures buying and selling pressure and provides volume-based confirmation (or divergence) of price trends.

#### Implementation

```python
from ta.volume import OnBalanceVolumeIndicator

result["OBV"] = OnBalanceVolumeIndicator(close, volume).on_balance_volume()
```

#### Calculation

```
If Close > Previous Close: OBV = Previous OBV + Volume
If Close < Previous Close: OBV = Previous OBV - Volume
If Close = Previous Close: OBV = Previous OBV
```

#### Interpretation

OBV is **not used directly for signal generation** in the current `get_signals()` implementation. It is included in `compute_indicators()` as a supplementary measure for manual analysis and reporting. Its primary value is in confirming or diverging from price trends:

| Condition | Meaning |
|---|---|
| Price rising + OBV rising | Confirmed uptrend; volume supports the price move |
| Price rising + OBV flat/falling | Unconfirmed uptrend; price rise may lack conviction |
| Price falling + OBV falling | Confirmed downtrend; volume supports the decline |
| Price falling + OBV flat/rising | Unconfirmed downtrend; selling pressure may be exhausting |
| OBV breaking to new high before price | Accumulation; smart money buying before price catches up |
| OBV breaking to new low before price | Distribution; selling pressure building before price reflects it |

#### Volume Analysis for AI Supply Chain Stocks

Volume patterns for AI supply chain stocks have specific characteristics worth noting:

- **Japanese-listed stocks** (8035.T, 6920.T, 6857.T) trade during Tokyo hours and may have very different volume profiles than their ADR counterparts. Use the listing with the most representative volume for analysis.
- **ADR volume** can be thin for some companies (TOELY, SHECY), making volume-based indicators less reliable. Prefer the local-exchange listing for volume analysis when possible.
- **Earnings-driven volume spikes** are pronounced for semiconductor equipment companies because their earnings are heavily watched as indicators of the semiconductor capex cycle. Volume on earnings day can be 5-10x normal.

---

### 4.8 Stochastic RSI

#### What It Measures

The Stochastic RSI applies the Stochastic oscillator formula to RSI values rather than raw prices. This makes it more sensitive than regular RSI and better at identifying short-term overbought/oversold conditions.

#### Implementation

```python
from ta.momentum import StochRSIIndicator
```

**Note:** While `StochRSIIndicator` is imported in `technical.py`, it is not currently used in `compute_indicators()` or `get_signals()`. It is available for future use and for custom analysis workflows. Its inclusion in the import list signals intent to integrate it into the standard indicator suite.

---

## 5. Signal Generation Rules

### 5.1 Signal Types

The `TechnicalAnalyzer.get_signals()` method generates signals for each indicator as a dictionary with the following structure:

```python
{
    "signal": "BUY" | "SELL" | "HOLD",
    "reason": "Human-readable explanation",
    "value": <numeric value if applicable>   # present for RSI
}
```

### 5.2 Complete Signal Rules Table

| Indicator | BUY Condition | SELL Condition | HOLD Condition |
|---|---|---|---|
| **RSI** | RSI < 30 (Oversold) | RSI > 70 (Overbought) | 30 <= RSI <= 70 (Neutral) |
| **MA Crossover** | SMA(20) > SMA(50) AND Price > SMA(20) | SMA(20) < SMA(50) AND Price < SMA(20) | Mixed signals (SMA crossing but price not confirming) |
| **MACD** | MACD Line > Signal Line | MACD Line < Signal Line | *(no HOLD state)* |
| **Bollinger Bands** | Price < Lower Band | Price > Upper Band | Price within bands |

### 5.3 Signal Priority and Reliability

Not all signals are equally reliable. Based on backtesting patterns and technical analysis literature, the signals can be ranked by reliability:

| Rank | Signal | Reliability | Best Market Condition |
|---|---|---|---|
| 1 | MACD crossover confirmed by volume | High | Trending markets |
| 2 | RSI divergence with price | High | All conditions |
| 3 | MA crossover (SMA 20/50) | Medium-High | Trending markets |
| 4 | Bollinger Band mean reversion | Medium | Range-bound markets |
| 5 | RSI overbought/oversold | Medium | Range-bound markets |
| 6 | Single indicator in isolation | Low | Context-dependent |

**Key principle:** Signals from multiple independent indicators confirming the same direction are significantly more reliable than any single indicator signal.

### 5.4 Signal Conflict Resolution

When indicators disagree (e.g., RSI says BUY but MACD says SELL), the aggregation logic in the scoring system handles this naturally by counting BUY signals as a proportion of total signals. However, analysts should understand the common conflict patterns:

| Conflict Pattern | Typical Cause | Resolution |
|---|---|---|
| RSI=BUY, MACD=SELL | Stock in downtrend but oversold; bouncing within downtrend | Favor MACD (trend) over RSI (mean-reversion) |
| RSI=SELL, MACD=BUY | Stock in uptrend but overbought; pullback likely within uptrend | Short-term pullback likely; wait for RSI to normalize |
| MA=BUY, BBands=SELL | Price above MAs and above upper Bollinger Band; strong momentum | Strong trend; BBands SELL may be premature |
| MA=SELL, BBands=BUY | Price below MAs and below lower Bollinger Band; strong selling | Catch-a-falling-knife risk; wait for MA confirmation |
| All indicators agree | Rare; strong conviction when it occurs | High-confidence signal |

---

## 6. Signal Aggregation and Scoring

### 6.1 Current Scoring Algorithm

The `TechnicalAnalyzerPlugin.analyze()` method converts individual signals into a single technical score (0-100):

```python
def analyze(self, ticker, ctx):
    df = ctx.price_data.get(ticker)
    if df is None or df.empty:
        return {"error": "No price data", "score": 50}
    signals = self._analyzer.get_signals(df)
    support_res = self._analyzer.get_support_resistance(df)
    buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
    total = max(len(signals), 1)
    score = (buy_count / total) * 100
    return {"signals": signals, "support_resistance": support_res, "score": round(score, 1)}
```

#### How the Score Is Computed

1. All four indicator signals are generated (RSI, MA Crossover, MACD, Bollinger Bands).
2. Count the number of BUY signals.
3. Divide by the total number of signals.
4. Multiply by 100 to get a 0-100 score.

#### Score Interpretation

| Score | BUY Count / Total | Interpretation |
|---|---|---|
| 100.0 | 4/4 | All indicators bullish; very strong technical picture |
| 75.0 | 3/4 | Most indicators bullish; positive technical outlook |
| 50.0 | 2/4 | Split signals; neutral/mixed technical picture |
| 25.0 | 1/4 | Most indicators bearish; negative technical outlook |
| 0.0 | 0/4 | All indicators bearish; very weak technical picture |

**Important note:** HOLD signals are treated the same as SELL signals in this scoring model. Only BUY signals contribute positively to the score. This means a stock with 2 BUY signals, 1 HOLD, and 1 SELL scores the same (50.0) as a stock with 2 BUY and 2 SELL. This is a design choice that errs on the conservative side -- a HOLD is not bullish confirmation.

### 6.2 Fallback Behavior

If price data is unavailable (`df is None or df.empty`), the plugin returns a neutral score of 50:

```python
return {"error": "No price data", "score": 50}
```

This ensures that the composite scoring system continues to function even when technical analysis cannot be computed. A score of 50 is intentionally neutral -- it neither helps nor hurts the composite score.

### 6.3 How the Technical Score Feeds Into the Composite

The composite scoring system (`StockScorer` in `src/analysis/scoring.py`) weights the technical score at **20%** of the total:

```python
WEIGHTS = {
    "fundamental": 0.30,
    "valuation":   0.25,
    "technical":   0.20,
    "sentiment":   0.10,
    "risk":        0.15,
}
```

The composite score is a weighted sum:

```
Composite = (Fundamental x 0.30) + (Valuation x 0.25) + (Technical x 0.20)
          + (Risk x 0.15) + (Sentiment x 0.10)
```

The composite then maps to a recommendation:

| Composite Score | Recommendation |
|---|---|
| >= 75 | STRONG BUY |
| 60-74 | BUY |
| 45-59 | HOLD |
| 30-44 | SELL |
| < 30 | STRONG SELL |

A technical score of 100 (all BUY) contributes 20 points (100 x 0.20) to the composite. A technical score of 0 (all bearish) contributes 0 points. The difference between the best and worst technical score is therefore 20 points on the composite scale -- enough to move a borderline stock from HOLD to BUY, or from BUY to HOLD.

---

## 7. Timeframe Selection and Multi-Timeframe Analysis

### 7.1 Default Timeframe

The platform default is **1 year of daily data** (`analysis.technical.default_period: "1y"` in `settings.yaml`). This provides approximately 252 trading days, which is sufficient for all indicators including the SMA(200).

### 7.2 Timeframe Options

| Period | Trading Days | Best For | SMA(200) Valid? |
|---|---|---|---|
| `1mo` | ~22 | Ultra-short-term momentum only | No |
| `3mo` | ~63 | Short-term swing analysis | No |
| `6mo` | ~126 | Medium-term trend analysis | No |
| `1y` | ~252 | Standard analysis (platform default) | Yes (from ~day 200) |
| `2y` | ~504 | Deep analysis; reliable long-term indicators | Yes (full coverage) |
| `5y` | ~1260 | Secular trend analysis; full cycle view | Yes |

### 7.3 Multi-Timeframe Analysis Approach

The most reliable technical signals occur when multiple timeframes agree. The recommended multi-timeframe workflow for FE-Analyst is:

**Step 1: Identify the long-term trend (2-year daily chart).**
- Is the stock above or below the SMA(200)?
- What is the direction of the SMA(200)?
- This sets the strategic bias: bullish, bearish, or neutral.

**Step 2: Identify the medium-term momentum (1-year daily chart).**
- What are the MACD and RSI readings?
- Are the SMA(20) and SMA(50) aligned with the long-term trend?
- This sets the tactical bias.

**Step 3: Identify the short-term entry/exit point (3-6 month chart).**
- Where is the price relative to the Bollinger Bands?
- Are there short-term support or resistance levels nearby?
- This determines the timing.

**Confluence principle:** When all three timeframes agree (long-term bullish, medium-term bullish, short-term at a buying opportunity), the signal has the highest probability of success.

### 7.4 Timeframe by Analysis Profile

The FE-Analyst profiles (configured in `configs/profiles.yaml`) use different timeframes:

| Profile | Period | Rationale |
|---|---|---|
| `quick` | `1y` | Standard analysis; sufficient for all indicators |
| `full` | `1y` | Comprehensive analysis; standard timeframe |
| `deep_dive` | `2y` | Extended analysis; full indicator convergence and cycle context |
| `screening` | `6mo` | Fast scan; SMA(200) not available but SMA(20/50) and momentum indicators work |

---

## 8. Support, Resistance, and Chart Pattern Recognition

### 8.1 Support and Resistance Detection

The `TechnicalAnalyzer.get_support_resistance()` method identifies support and resistance levels using rolling windows:

```python
def get_support_resistance(self, df: pd.DataFrame, window: int = 20) -> dict:
    """Identify support and resistance levels."""
    highs = df["High"].rolling(window=window).max()
    lows = df["Low"].rolling(window=window).min()
    return {
        "resistance": float(highs.iloc[-1]),
        "support": float(lows.iloc[-1]),
        "current": float(df["Close"].iloc[-1]),
    }
```

#### How It Works

- **Resistance:** The highest high over the most recent 20 trading days (approximately 1 month). This represents the price ceiling that sellers have defended.
- **Support:** The lowest low over the most recent 20 trading days. This represents the price floor where buyers have stepped in.
- **Current:** The most recent closing price.

#### Interpretation

| Current Price Position | Meaning | Implication |
|---|---|---|
| Near resistance (within 2% of resistance) | Price testing ceiling; breakout or rejection imminent | Watch for breakout with volume confirmation |
| Near support (within 2% of support) | Price testing floor; bounce or breakdown imminent | Watch for bounce with volume confirmation |
| Mid-range | Normal price action; no immediate level test | Wait for approach to a level |
| Above resistance | Breakout; former resistance becomes new support | Bullish; confirms uptrend |
| Below support | Breakdown; former support becomes new resistance | Bearish; confirms downtrend |

#### Support/Resistance Window Selection

The default window of 20 provides short-term levels. For different analytical needs, the window parameter can be adjusted by calling `get_support_resistance()` directly:

| Window | Timeframe | Level Significance |
|---|---|---|
| 10 | ~2 weeks | Short-term micro levels |
| 20 | ~1 month (default) | Near-term trading levels |
| 50 | ~2.5 months | Medium-term levels |
| 100 | ~5 months | Significant trend levels |
| 200 | ~10 months | Major long-term levels |

Longer windows produce more significant levels. A support level that has held for 200 trading days is much stronger than one that has held for 20 trading days.

### 8.2 Chart Pattern Recognition Concepts

While the current implementation provides basic support/resistance detection, analysts using the platform should be aware of common chart patterns that can be visually identified from the technical data:

#### Trend Patterns

| Pattern | Description | Signal |
|---|---|---|
| Higher highs + higher lows | Price making progressively higher peaks and troughs | Uptrend confirmed |
| Lower highs + lower lows | Price making progressively lower peaks and troughs | Downtrend confirmed |
| Flat highs + flat lows | Price oscillating within a range | Consolidation/range-bound |

#### Reversal Patterns

| Pattern | Description | Signal |
|---|---|---|
| Double bottom | Price tests support twice and bounces; forms a "W" shape | Bullish reversal |
| Double top | Price tests resistance twice and rejects; forms an "M" shape | Bearish reversal |
| Head and shoulders | Three peaks with middle highest; two equal "shoulders" | Bearish reversal |
| Inverse head and shoulders | Three troughs with middle lowest; two equal "shoulders" | Bullish reversal |

#### Continuation Patterns

| Pattern | Description | Signal |
|---|---|---|
| Flag/pennant | Brief consolidation after a strong move; volume declines | Continuation of prior trend |
| Ascending triangle | Flat resistance + rising support | Bullish (usually breaks up) |
| Descending triangle | Falling resistance + flat support | Bearish (usually breaks down) |

**Note:** Automated chart pattern recognition is not implemented in the current codebase. These patterns must be identified manually by examining the price data and indicator output. Automated pattern detection is a candidate for future development.

---

## 9. Integration with the Analysis Pipeline

### 9.1 Plugin Architecture

The technical analysis module integrates with the FE-Analyst pipeline through the **plugin system**. The plugin system uses the `BaseAnalyzer` abstract class defined in `src/analysis/base.py`:

```python
class BaseAnalyzer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name used as key in registry and context."""

    @abstractmethod
    def analyze(self, ticker: str, ctx: PipelineContext) -> dict:
        """Run analysis. MUST include a 'score' key (0-100)."""

    @property
    def default_weight(self) -> float:
        """Default weight in composite scoring (0.0 - 1.0)."""
        return 0.10
```

### 9.2 TechnicalAnalyzerPlugin

The `TechnicalAnalyzerPlugin` class adapts `TechnicalAnalyzer` for the pipeline:

```python
class TechnicalAnalyzerPlugin(_BaseAnalyzer):
    name = "technical"
    default_weight = 0.20

    def __init__(self):
        self._analyzer = TechnicalAnalyzer()

    def analyze(self, ticker, ctx):
        df = ctx.price_data.get(ticker)
        if df is None or df.empty:
            return {"error": "No price data", "score": 50}
        signals = self._analyzer.get_signals(df)
        support_res = self._analyzer.get_support_resistance(df)
        buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
        total = max(len(signals), 1)
        score = (buy_count / total) * 100
        return {
            "signals": signals,
            "support_resistance": support_res,
            "score": round(score, 1),
        }
```

#### Key Design Decisions

1. **`name = "technical"`**: This string is the key used in the registry, the context, and the scoring system. It must match the key in `settings.yaml` under `analysis.registry.technical`.

2. **`default_weight = 0.20`**: The technical analysis contributes 20% to the composite score. This can be overridden in `settings.yaml` via `analysis.registry.technical.weight`.

3. **`ctx.price_data.get(ticker)`**: The plugin depends on price data being pre-fetched by an earlier pipeline step (`fetch_price_data`). The pipeline context (`PipelineContext`) stores price data as a dictionary mapping ticker strings to DataFrames.

4. **Fallback score of 50**: When price data is unavailable, the plugin returns a neutral score rather than failing. This allows the pipeline to continue processing other analysis modules.

### 9.3 Pipeline Registration

The plugin is registered in `configs/settings.yaml`:

```yaml
analysis:
  registry:
    technical:
      module: src.analysis.technical
      class: TechnicalAnalyzerPlugin
      weight: 0.20
      enabled: true
```

The pipeline engine (`PipelineEngine`) reads this registry and dynamically imports and instantiates the plugin class. This means:

- **No hard-coded imports** in the pipeline engine. Adding or removing analyzers is a configuration change, not a code change.
- **Weight is configurable.** Changing the technical analysis weight from 0.20 to 0.15 requires only editing `settings.yaml`.
- **Disabling is simple.** Setting `enabled: false` removes technical analysis from the pipeline without any code changes.

### 9.4 Pipeline Execution Flow

```
1. User runs: python main.py analyze ASML --profile full
2. main.py resolves "ASML" to ticker, selects "full" profile
3. PipelineEngine builds step sequence from profile config
4. Step: fetch_price_data
   - MarketDataClient.get_price_history("ASML", period="1y")
   - Stores DataFrame in ctx.price_data["ASML"]
5. Step: run_registered_analyzers
   - Iterates over enabled analyzers from registry
   - For "technical": TechnicalAnalyzerPlugin.analyze("ASML", ctx)
     - Retrieves ctx.price_data["ASML"]
     - Calls TechnicalAnalyzer.get_signals(df)
     - Calls TechnicalAnalyzer.get_support_resistance(df)
     - Computes score from BUY signal count
     - Returns {"signals": {...}, "support_resistance": {...}, "score": 75.0}
6. Step: compute_scores
   - Aggregates all analyzer scores using configured weights
   - Produces composite_score and recommendation
7. Step: render_report
   - Generates markdown/HTML report from template
   - Technical section shows individual signals, support/resistance, and score
8. Report saved to reports/output/
```

### 9.5 Standalone Usage (Outside Pipeline)

The `TechnicalAnalyzer` class can be used independently of the pipeline for ad-hoc analysis:

```python
from src.analysis.technical import TechnicalAnalyzer
from src.data_sources.market_data import MarketDataClient

client = MarketDataClient()
df = client.get_price_history("ASML", period="1y")

analyzer = TechnicalAnalyzer()

# Get DataFrame with all indicator columns added
df_with_indicators = analyzer.compute_indicators(df)

# Get signal summary for the latest data point
signals = analyzer.get_signals(df)

# Get support/resistance levels
levels = analyzer.get_support_resistance(df)
```

This is the pattern used by `scripts/ai_deep_dive.py`, `src/analysis/scoring.py` (`StockScorer`), and any Jupyter notebook analysis.

---

## 10. Configuration Reference

### 10.1 Settings in `configs/settings.yaml`

The technical analysis module reads the following configuration:

```yaml
analysis:
  registry:
    technical:
      module: src.analysis.technical     # Python import path
      class: TechnicalAnalyzerPlugin     # Class name to instantiate
      weight: 0.20                        # Weight in composite score (0.0 - 1.0)
      enabled: true                       # Whether to include in pipeline

  technical:
    default_period: "1y"                  # History period for price data
    indicators: [sma, ema, rsi, macd, bbands, atr, obv]  # Enabled indicators
```

### 10.2 Configurable Parameters

| Parameter | Location | Default | Valid Values | Effect |
|---|---|---|---|---|
| `weight` | `analysis.registry.technical.weight` | `0.20` | 0.0 - 1.0 | Proportion of composite score from technical analysis |
| `enabled` | `analysis.registry.technical.enabled` | `true` | true/false | Whether technical analysis runs in the pipeline |
| `default_period` | `analysis.technical.default_period` | `"1y"` | `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `max` | How much price history to fetch |
| `indicators` | `analysis.technical.indicators` | Full list | Subset of: `sma`, `ema`, `rsi`, `macd`, `bbands`, `atr`, `obv` | Which indicators to compute |

### 10.3 Indicator Parameter Defaults (Hard-Coded)

The following parameters are currently hard-coded in `TechnicalAnalyzer.compute_indicators()`. To change them, you must modify the source code:

| Indicator | Parameter | Default Value | Typical Alternatives |
|---|---|---|---|
| SMA | Windows | 20, 50, 200 | 10, 30, 100 |
| EMA | Windows | 12, 26 | 9, 21, 50 |
| RSI | Window | 14 | 7, 21 |
| MACD | Fast, Slow, Signal | 12, 26, 9 | 8, 17, 9 (faster) |
| Bollinger Bands | Window, Std Dev | 20, 2 | 20, 1.5 or 20, 2.5 |
| ATR | Window | 14 | 7, 21 |
| Support/Resistance | Window | 20 | 10, 50, 100, 200 |

### 10.4 RSI Signal Thresholds (Hard-Coded)

| Threshold | Current Value | Conservative Alternative | Aggressive Alternative |
|---|---|---|---|
| Oversold (BUY) | < 30 | < 25 | < 35 |
| Overbought (SELL) | > 70 | > 75 | > 65 |

**When to consider alternatives:**

- **Conservative thresholds (25/75):** Use for highly volatile stocks where RSI extremes are more meaningful. Semiconductor stocks during earnings volatility may benefit from tighter thresholds to reduce false signals.
- **Aggressive thresholds (35/65):** Use for low-volatility stocks or when you want earlier signals at the cost of more false positives.

### 10.5 Modifying the Configuration

**Changing the weight:**

Edit `configs/settings.yaml`:
```yaml
analysis:
  registry:
    technical:
      weight: 0.15  # Reduced from 0.20
```

No code changes needed. The pipeline engine reads this value at runtime.

**Changing the data period:**

Edit `configs/settings.yaml`:
```yaml
analysis:
  technical:
    default_period: "2y"  # Extended from 1y
```

This affects all pipeline runs. Individual scripts (`ai_deep_dive.py`) may override this with their own period parameter.

**Disabling technical analysis:**

Edit `configs/settings.yaml`:
```yaml
analysis:
  registry:
    technical:
      enabled: false
```

The pipeline will skip technical analysis entirely. The composite score will be computed from the remaining enabled analyzers with their weights renormalized.

---

## 11. Example Workflows

### 11.1 Basic Single-Stock Technical Analysis via CLI

**Goal:** Run a full analysis of ASML including technical indicators and signals.

```bash
cd /Users/xia/Desktop/FE-analyst
python main.py analyze ASML --profile full
```

**What happens:**
1. `main.py` resolves "ASML" via `TickerResolver`
2. The `full` profile fetches 1 year of price data
3. `TechnicalAnalyzerPlugin.analyze()` computes all indicators and generates signals
4. The composite score includes the technical score at 20% weight
5. A report is generated at `reports/output/` with a Technical Analysis section

**Expected output (technical section of report):**

```
TECHNICAL ANALYSIS
==================
Technical Score: 75.0 / 100

Signals:
  RSI (14):           HOLD  (RSI = 58.3, Neutral)
  MA Crossover:       BUY   (Price above rising MAs)
  MACD:               BUY   (MACD above signal)
  Bollinger Bands:    BUY   (Within bands -- near lower band)

Support/Resistance:
  Resistance:  $785.20
  Support:     $712.50
  Current:     $748.30
```

### 11.2 Comparative Technical Analysis

**Goal:** Compare technical signals across semiconductor equipment peers.

```bash
python main.py compare ASML LRCX AMAT KLAC
```

**What happens:**
1. All four tickers are resolved and analyzed
2. Technical signals are generated independently for each
3. The comparison report shows side-by-side technical scores

This is useful for identifying which stocks in a peer group have the strongest or weakest technical setups.

### 11.3 Sector Scan for Technical Signals

**Goal:** Scan all semiconductor equipment companies for technical buy signals.

```bash
python main.py scan --category semiconductor_equipment
```

**What happens:**
1. All tickers in the `semiconductor_equipment` category are loaded from `configs/ai_moat_universe.yaml`
2. Each ticker is analyzed through the pipeline
3. The screening report ranks companies by composite score, which includes the technical component
4. Companies with strong technical scores (75-100) are potential near-term opportunities

### 11.4 Standalone Python Analysis

**Goal:** Deep-dive technical analysis with custom parameters.

```python
from src.analysis.technical import TechnicalAnalyzer
from src.data_sources.market_data import MarketDataClient

client = MarketDataClient()
analyzer = TechnicalAnalyzer()

# Fetch 2 years of data for more reliable SMA(200)
df = client.get_price_history("8035.T", period="2y")

# Compute all indicators
df_ind = analyzer.compute_indicators(df)

# Get signals
signals = analyzer.get_signals(df)
print("Signals:", signals)

# Get support/resistance at multiple timeframes
sr_short = analyzer.get_support_resistance(df, window=20)
sr_medium = analyzer.get_support_resistance(df, window=50)
sr_long = analyzer.get_support_resistance(df, window=200)

print(f"Short-term S/R:  Support={sr_short['support']:.0f}, "
      f"Resistance={sr_short['resistance']:.0f}")
print(f"Medium-term S/R: Support={sr_medium['support']:.0f}, "
      f"Resistance={sr_medium['resistance']:.0f}")
print(f"Long-term S/R:   Support={sr_long['support']:.0f}, "
      f"Resistance={sr_long['resistance']:.0f}")

# Check trend: price vs SMAs
latest = df_ind.iloc[-1]
print(f"\nPrice: {latest['Close']:.2f}")
print(f"SMA(20):  {latest['SMA_20']:.2f} -- "
      f"{'Above' if latest['Close'] > latest['SMA_20'] else 'Below'}")
print(f"SMA(50):  {latest['SMA_50']:.2f} -- "
      f"{'Above' if latest['Close'] > latest['SMA_50'] else 'Below'}")
print(f"SMA(200): {latest['SMA_200']:.2f} -- "
      f"{'Above' if latest['Close'] > latest['SMA_200'] else 'Below'}")

# Check momentum
print(f"\nRSI(14):  {latest['RSI_14']:.1f}")
print(f"MACD:     {latest['MACD']:.4f}")
print(f"MACD Sig: {latest['MACD_signal']:.4f}")
print(f"MACD Hist:{latest['MACD_hist']:.4f}")

# Check volatility
print(f"\nATR(14):  {latest['ATR_14']:.2f}")
print(f"BB Upper: {latest['BB_upper']:.2f}")
print(f"BB Lower: {latest['BB_lower']:.2f}")
```

### 11.5 Deep Dive Script with Technical Section

**Goal:** Generate a full investment memo including detailed technical analysis.

```bash
python scripts/ai_deep_dive.py ASML --peers LRCX AMAT KLAC
```

The `ai_deep_dive.py` script creates a comprehensive report that includes:
- Company overview and moat analysis
- Financial statement analysis
- **Technical analysis and price action** (uses `TechnicalAnalyzer` directly)
- Valuation (DCF and comparables)
- Risk assessment
- News sentiment
- Investment thesis

The technical section in the deep dive report provides more detail than the standard pipeline output, including historical indicator plots and trend analysis.

### 11.6 Multi-Ticker Batch Analysis

**Goal:** Analyze all companies in the AI universe watchlist.

```bash
python main.py scan --watchlist japan_champions
```

Or scan the entire AI universe:

```bash
python scripts/ai_universe_scanner.py --top 20
```

These commands run the full pipeline (including technical analysis) for each ticker in the watchlist or universe, producing a ranked output sorted by composite score.

---

## 12. Limitations and Caveats

### 12.1 Fundamental Limitations of Technical Analysis

**No predictive certainty.** Technical analysis provides probabilistic signals, not predictions. A BUY signal from all four indicators does not guarantee the stock will go up. It means that, historically, stocks in similar technical configurations have been more likely to rise than fall. The edge is statistical, not deterministic.

**Self-fulfilling and self-defeating.** Popular technical levels (round numbers, widely-watched SMA levels) can become self-fulfilling as many traders act on the same signal. Conversely, this popularity can also cause level failures (stop-hunting, false breakouts) as sophisticated traders exploit the crowded positioning.

**Does not work in isolation.** Technical analysis applied without fundamental context is pattern-matching without understanding. A stock can have a perfect technical setup and still decline 50% on an earnings miss or regulatory action. Always use technical analysis in conjunction with fundamental, valuation, and risk analysis.

### 12.2 Platform-Specific Limitations

**Simple aggregation model.** The current scoring algorithm counts BUY signals as a proportion of total signals and assigns equal weight to each indicator. This means:
- An RSI BUY signal (potentially mean-reverting in a downtrend) counts the same as a MACD BUY signal (trend-following) even though they have different reliability profiles.
- A marginal signal (RSI at 29.5, just barely BUY) counts the same as an extreme signal (RSI at 15, deeply oversold).
- Future enhancement: weighted signal aggregation based on indicator reliability and signal strength.

**No divergence detection.** The current implementation does not detect RSI or MACD divergences, which are among the most reliable reversal signals. Divergences require comparing current and previous swing points, which is more complex than single-point analysis.

**No volume-confirmed signals.** Signals from MACD and MA crossovers are not confirmed by volume analysis. A breakout on low volume is less reliable than one on high volume, but the current system treats them identically.

**No pattern recognition.** Chart patterns (double tops, head and shoulders, flags, wedges) are not detected programmatically. These patterns require visual inspection or more sophisticated pattern-matching algorithms.

**Single timeframe.** The pipeline processes only one timeframe per run (determined by `default_period`). Multi-timeframe confluence analysis requires running separate analyses with different periods and comparing the results manually.

**Lagging nature of indicators.** All indicators used in the platform are lagging indicators -- they are computed from historical data and confirm what has already happened. None of the indicators predict future price moves. The MACD and EMA are slightly less lagging than the SMA, but all are backward-looking.

### 12.3 Data-Related Limitations

**yfinance data quality.** yfinance is an unofficial library that scrapes Yahoo Finance. It can:
- Return incorrect data after stock splits if the adjustment has not propagated
- Have gaps in international stock data (especially Japanese and Korean stocks)
- Break unexpectedly when Yahoo changes their website structure
- Return stale data during periods of high API load

**Adjusted price sensitivity.** Dividend adjustments can significantly alter historical prices, which affects indicator calculations. A stock that paid a large special dividend will show a discontinuity in unadjusted prices. The `ta` library does not know about these events; it trusts the data it receives. If adjustments are incorrect, all downstream indicator calculations will be wrong.

**International market hours.** For stocks traded on multiple exchanges (e.g., ASML on Euronext and as an ADR on NASDAQ), the closing price depends on which exchange's data is used. The Euronext close (5:30 PM CET) and the NASDAQ close (4:00 PM ET) can differ, producing different signal outputs for the same company.

**Weekend and holiday effects.** The `ta` library treats each row as one period regardless of the actual time elapsed. A 3-day weekend followed by a trading day is treated the same as a normal overnight gap. This can occasionally produce artifacts in volatility-based indicators (ATR, Bollinger Bands) during periods with extended closures.

### 12.4 Behavioral and Interpretive Caveats

**Confirmation bias risk.** Analysts may unconsciously look for technical signals that confirm their pre-existing view. If you believe a stock is a buy based on fundamentals, you are more likely to interpret ambiguous technical signals as bullish. Guard against this by documenting the technical assessment before incorporating other analysis dimensions.

**Overfitting to historical patterns.** The specific parameter values (RSI window=14, MACD 12/26/9, BB window=20) were developed for the broad US equity market decades ago. They may not be optimal for:
- Japanese semiconductor equipment stocks with different volatility profiles
- Semiconductor stocks during the current AI super-cycle
- Low-liquidity ADRs with thin trading volume

**Signal frequency is not confidence.** Generating more signals (by adding more indicators) does not necessarily improve the analysis. Additional indicators often provide redundant information (e.g., RSI and Stochastic RSI measure similar things). Signal quality and independence matter more than signal quantity.

---

## 13. Troubleshooting Common Issues

### 13.1 NaN Values in Indicators

**Symptom:** Indicator columns contain NaN values, especially at the beginning of the DataFrame.

**Cause:** Each indicator requires a minimum lookback period. The first N rows will be NaN where N is the indicator's window.

**Resolution:** This is expected behavior. Ensure your DataFrame has sufficient history (at least 200 trading days for SMA_200). The `get_signals()` method uses `iloc[-1]` (the last row) which should have valid values if the DataFrame has enough data.

### 13.2 All Signals Return HOLD

**Symptom:** Every signal is HOLD, resulting in a score of 0 (no BUY signals).

**Cause:** This can happen when:
- RSI is between 30 and 70 (HOLD)
- SMA signals are mixed (HOLD)
- Price is within Bollinger Bands (HOLD)
- MACD is the only non-HOLD indicator (BUY or SELL)

**Resolution:** This is not an error -- it correctly reflects a neutral technical environment. A score of 25.0 (1 BUY out of 4) is common in sideways markets.

### 13.3 Empty Price Data

**Symptom:** `TechnicalAnalyzerPlugin.analyze()` returns `{"error": "No price data", "score": 50}`.

**Cause:** `ctx.price_data.get(ticker)` returned `None` or an empty DataFrame. This occurs when:
- The ticker symbol is invalid
- The yfinance API failed (rate limit, network error, site change)
- The `fetch_price_data` pipeline step was not included before `run_registered_analyzers`

**Resolution:**
1. Verify the ticker is valid: `python main.py quote TICKER`
2. Check the logs for API errors: look for `MarketDataClient` or `yfinance` error messages
3. Ensure the profile includes `fetch_price_data` in its steps
4. Try the fallback sources: configure Finnhub or Alpaca as fallbacks in `settings.yaml`

### 13.4 Stale Signals

**Symptom:** Signals do not reflect recent price action.

**Cause:** The price data may be cached and stale. The default cache TTL for daily prices is 1 hour.

**Resolution:**
1. Check the cache directory: `data/cache/` for the cached file
2. Clear the cache for the specific ticker
3. Reduce the cache TTL in `settings.yaml` if more frequent updates are needed:
   ```yaml
   cache:
     ttl_hours:
       price_daily: 0.5  # 30 minutes
   ```

### 13.5 Inconsistent Signals Between Pipeline and Standalone

**Symptom:** Running `TechnicalAnalyzer` standalone produces different signals than the pipeline output.

**Cause:** The standalone analysis may use a different data period, or the data may have been fetched at a different time (and thus have a different "latest" data point).

**Resolution:** Ensure both analyses use the same:
- Data period (`1y`, `2y`, etc.)
- Data retrieval time (the latest close may differ between runs)
- Ticker format (e.g., `ASML` vs `ASML.AS`)

---

## Appendix A -- Indicator Quick Reference

### Computed Columns Summary

| Column Name | Indicator | Type | Signal Generation? |
|---|---|---|---|
| `SMA_20` | 20-period Simple Moving Average | Trend | Yes (MA crossover) |
| `SMA_50` | 50-period Simple Moving Average | Trend | Yes (MA crossover) |
| `SMA_200` | 200-period Simple Moving Average | Trend | No (informational) |
| `EMA_12` | 12-period Exponential Moving Average | Trend | No (MACD component) |
| `EMA_26` | 26-period Exponential Moving Average | Trend | No (MACD component) |
| `RSI_14` | 14-period Relative Strength Index | Momentum | Yes |
| `MACD` | MACD Line (EMA12 - EMA26) | Momentum | Yes |
| `MACD_signal` | MACD Signal Line (EMA9 of MACD) | Momentum | Yes |
| `MACD_hist` | MACD Histogram (MACD - Signal) | Momentum | No (informational) |
| `BB_upper` | Upper Bollinger Band (SMA20 + 2 std) | Volatility | Yes |
| `BB_lower` | Lower Bollinger Band (SMA20 - 2 std) | Volatility | Yes |
| `BB_mid` | Middle Bollinger Band (SMA20) | Volatility | No (same as SMA_20) |
| `ATR_14` | 14-period Average True Range | Volatility | No (risk management) |
| `OBV` | On-Balance Volume | Volume | No (confirmation) |

### Library Dependencies

| Library | Import Path | Version Requirement | Purpose |
|---|---|---|---|
| `ta` | `ta.trend`, `ta.momentum`, `ta.volatility`, `ta.volume` | >= 0.10.0 | Indicator computation |
| `pandas` | `pandas` | >= 1.5.0 | Data structure (DataFrame) |
| `yfinance` | `yfinance` (via `MarketDataClient`) | >= 0.2.0 | Price data retrieval |

---

## Appendix B -- Signal Decision Trees

### Overall Technical Assessment Decision Tree

```
START: Fetch OHLCV data for ticker
  |
  |-- Data available?
  |     |
  |     NO --> Return score=50 (neutral fallback)
  |     |
  |     YES --> Compute all indicators
  |               |
  |               |-- Generate RSI signal
  |               |     RSI < 30? --> BUY
  |               |     RSI > 70? --> SELL
  |               |     Else     --> HOLD
  |               |
  |               |-- Generate MA Crossover signal
  |               |     SMA20 > SMA50 AND Price > SMA20? --> BUY
  |               |     SMA20 < SMA50 AND Price < SMA20? --> SELL
  |               |     Else                             --> HOLD
  |               |
  |               |-- Generate MACD signal
  |               |     MACD > Signal? --> BUY
  |               |     MACD < Signal? --> SELL
  |               |
  |               |-- Generate Bollinger Band signal
  |               |     Price < Lower Band? --> BUY
  |               |     Price > Upper Band? --> SELL
  |               |     Else               --> HOLD
  |               |
  |               |-- Count BUY signals
  |               |     Score = (BUY count / Total signals) x 100
  |               |
  |               |-- Compute Support/Resistance
  |               |     Resistance = 20-day rolling high
  |               |     Support    = 20-day rolling low
  |               |
  |               |-- Return {signals, support_resistance, score}
```

### Composite Score Integration Decision Tree

```
START: All analyzer scores computed
  |
  |-- Technical Score (weight: 0.20)
  |     0-25   (All/most bearish)   --> Drags composite down by up to 20 pts
  |     25-50  (Slightly bearish)   --> Mild negative contribution
  |     50     (Neutral / fallback) --> No net contribution
  |     50-75  (Slightly bullish)   --> Mild positive contribution
  |     75-100 (All/most bullish)   --> Boosts composite by up to 20 pts
  |
  |-- Combined with other scores:
  |     Composite >= 75 --> STRONG BUY
  |     Composite 60-74 --> BUY
  |     Composite 45-59 --> HOLD
  |     Composite 30-44 --> SELL
  |     Composite < 30  --> STRONG SELL
```

### When to Override Technical Signals Decision Tree

```
Technical Signal Assessment:
  |
  |-- Technical says BUY, Fundamentals say SELL
  |     |
  |     Possible explanations:
  |     (a) Dead cat bounce (price rally in a fundamentally deteriorating stock)
  |     (b) Market has not yet priced in the fundamental deterioration
  |     (c) Fundamental deterioration is temporary and the market is forward-looking
  |     |
  |     Action: Investigate. Do NOT blindly follow the technical BUY.
  |             If fundamentals are clearly deteriorating, the technical
  |             signal is likely a trap.
  |
  |-- Technical says SELL, Fundamentals say BUY
  |     |
  |     Possible explanations:
  |     (a) Sector rotation causing temporary selling in a sound stock
  |     (b) Market is pricing in a risk that fundamental analysis has not captured
  |     (c) Profit-taking after a strong run
  |     |
  |     Action: Investigate. If the fundamental case is strong and the
  |             technical weakness is minor (mild overbought), this may
  |             be a buying opportunity. If the technical weakness is
  |             severe (breaking key support), exercise caution.
  |
  |-- Technical says HOLD, Fundamentals say BUY/SELL
  |     |
  |     Action: Wait for technical confirmation. The fundamentals set
  |             the direction; the technicals set the timing.
```

---

## Appendix C -- Recommended Reading Periods by Analysis Goal

| Analysis Goal | Recommended Period | Indicators to Focus On | Notes |
|---|---|---|---|
| Day-trade / swing-trade timing | `3mo` (daily) | RSI, MACD, BB | SMA(200) not available |
| Entry/exit timing for existing position | `6mo` to `1y` (daily) | All indicators | Standard analysis |
| Trend identification | `1y` to `2y` (daily) | SMA(50), SMA(200), MACD | Golden/Death Cross requires full SMA(200) |
| Semiconductor cycle positioning | `2y` to `5y` (daily) | SMA(200), OBV, long-term support/resistance | Need full cycle context |
| Screening / quick scan | `6mo` (daily) | RSI, MACD | Fast computation; skip SMA(200) |
| Earnings setup analysis | `3mo` (daily) | BB (squeeze), ATR, RSI | Pre-earnings volatility compression |
| Post-earnings reaction | `1mo` (daily) | Gap analysis, volume, RSI | Short-term momentum after news |

---

## Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-02-09 | FE-Analyst Team | Initial release |

---

*This SOP is a living document. It should be updated whenever new indicators are added to the `TechnicalAnalyzer`, signal generation logic changes, or new integration points with the pipeline are created. Proposed changes should be reviewed before incorporation to ensure consistency with the platform's analytical framework.*
