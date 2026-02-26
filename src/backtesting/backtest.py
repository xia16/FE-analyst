"""Walk-forward backtest harness for scoring signal quality.

At each rebalance date, compute a **point-in-time** score using ONLY
data available up to that date, then measure actual forward returns to
assess whether higher scores predict higher returns.

IMPORTANT — Scoring limitations:
  - Technical & risk scores are truly point-in-time (computed from price
    history truncated at the rebalance date).
  - Fundamental / valuation / sentiment scores CANNOT be point-in-time
    via yfinance (it returns current snapshots only).  The backtest
    therefore uses a price-based composite (momentum + risk) which is
    free of look-ahead bias but narrower than the live scoring system.
  - To enable full point-in-time scoring, a historical fundamentals
    provider (e.g. Compustat, SimFin bulk) is required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("backtest")


@dataclass
class BacktestResult:
    """Container for a single rebalance-period result."""
    date: str
    ticker: str
    composite_score: float
    sub_scores: dict
    forward_1m: float | None = None
    forward_3m: float | None = None
    forward_6m: float | None = None
    transaction_cost_pct: float = 0.0


# ------------------------------------------------------------------
#  Point-in-time price-based scorer
# ------------------------------------------------------------------

def _point_in_time_score(prices: pd.DataFrame) -> tuple[float, dict]:
    """Compute a point-in-time composite score from price data only.

    Sub-scores (each 0-100):
      - momentum_1m:  1-month price return
      - momentum_3m:  3-month price return
      - momentum_6m:  6-month price return
      - rsi_14:       14-day RSI analog
      - ma_crossover: SMA50 vs SMA200 position
      - volatility:   lower annualized vol → higher score
      - drawdown:     shallower max drawdown → higher score
      - sharpe:       risk-adjusted return

    Returns (composite, sub_scores_dict).
    """
    sub = {}
    close = prices["Close"]
    n = len(close)

    # --- Momentum scores ---
    for label, days in [("momentum_1m", 21), ("momentum_3m", 63), ("momentum_6m", 126)]:
        if n > days:
            ret = (float(close.iloc[-1]) / float(close.iloc[-days]) - 1) * 100
            # Map: -30% → 0, 0% → 50, +30% → 100
            sub[label] = max(0, min(100, 50 + ret * (50 / 30)))
        else:
            sub[label] = 50.0

    # --- RSI-14 analog ---
    if n > 15:
        delta = close.diff().tail(14)
        gains = delta.clip(lower=0).mean()
        losses = (-delta.clip(upper=0)).mean()
        rs = gains / losses if losses > 0 else 100
        rsi = 100 - (100 / (1 + rs))
        # RSI → score: RSI 30 → 80 (oversold = buy), RSI 70 → 20 (overbought = caution)
        sub["rsi_14"] = max(0, min(100, 100 - rsi))
    else:
        sub["rsi_14"] = 50.0

    # --- MA crossover ---
    if n > 200:
        sma50 = float(close.tail(50).mean())
        sma200 = float(close.tail(200).mean())
        # Above SMA200 with golden cross → bullish
        ratio = sma50 / sma200 if sma200 > 0 else 1.0
        sub["ma_crossover"] = max(0, min(100, 50 + (ratio - 1) * 500))
    else:
        sub["ma_crossover"] = 50.0

    # --- Volatility (lower = better) ---
    if n > 60:
        returns = close.pct_change().dropna().tail(60)
        ann_vol = float(returns.std() * np.sqrt(252))
        # Map: vol 0% → 100, vol 60%+ → 0
        sub["volatility"] = max(0, min(100, (1 - ann_vol / 0.6) * 100))
    else:
        sub["volatility"] = 50.0

    # --- Max drawdown (shallower = better) ---
    if n > 60:
        trailing = close.tail(min(252, n))
        cummax = trailing.cummax()
        dd = ((trailing - cummax) / cummax).min()
        # Map: 0% DD → 100, -50% DD → 0
        sub["drawdown"] = max(0, min(100, (1 - abs(float(dd)) / 0.5) * 100))
    else:
        sub["drawdown"] = 50.0

    # --- Sharpe ratio ---
    if n > 60:
        returns = close.pct_change().dropna().tail(min(252, n - 1))
        rf_daily = 0.04 / 252
        excess = returns - rf_daily
        if excess.std() > 0:
            sharpe = float(excess.mean() / excess.std() * np.sqrt(252))
        else:
            sharpe = 0.0
        # Map: Sharpe -1 → 0, 0 → 30, 1 → 60, 2 → 100
        sub["sharpe"] = max(0, min(100, (sharpe + 1) / 3 * 100))
    else:
        sub["sharpe"] = 50.0

    # Composite: weighted average of sub-scores
    weights = {
        "momentum_1m": 0.10,
        "momentum_3m": 0.15,
        "momentum_6m": 0.10,
        "rsi_14": 0.10,
        "ma_crossover": 0.10,
        "volatility": 0.15,
        "drawdown": 0.15,
        "sharpe": 0.15,
    }
    composite = sum(sub[k] * weights[k] for k in weights)
    return round(composite, 2), {k: round(v, 1) for k, v in sub.items()}


# ------------------------------------------------------------------
#  Simple transaction cost estimator for backtest
# ------------------------------------------------------------------

# OTC ADR tickers known to have wide spreads
_OTC_ADRS = {"HTHIY", "SHECY", "TOELY", "ATEYY", "HOCPY", "LSRCY", "DSCSY", "FANUY"}


def _estimate_txn_cost(ticker: str, prices: pd.DataFrame) -> float:
    """Estimate round-trip transaction cost as a percentage.

    Uses a simplified Corwin-Schultz spread proxy + OTC ADR floor.
    Returns cost in percentage points (e.g. 0.5 means 0.5%).
    """
    try:
        if "High" not in prices.columns or "Low" not in prices.columns or len(prices) < 5:
            return 0.50 if ticker in _OTC_ADRS else 0.10

        h = prices["High"].values.astype(float)
        l = prices["Low"].values.astype(float)

        hl_log_sq = np.log(h / np.maximum(l, 1e-10)) ** 2
        beta = hl_log_sq[1:] + hl_log_sq[:-1]
        h2 = np.maximum(h[1:], h[:-1])
        l2 = np.minimum(l[1:], l[:-1])
        gamma = np.log(h2 / np.maximum(l2, 1e-10)) ** 2

        k = 3.0 - 2.0 * np.sqrt(2.0)
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
        alpha = np.maximum(alpha, 0.0)
        spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))

        tail = spread[-20:] if len(spread) >= 20 else spread
        avg_spread_pct = float(np.mean(tail)) * 100 if len(tail) > 0 else 0.10

        if ticker in _OTC_ADRS:
            avg_spread_pct = max(avg_spread_pct, 0.30)

        # Round-trip cost ≈ full spread (half-spread each way)
        return avg_spread_pct
    except Exception:
        return 0.50 if ticker in _OTC_ADRS else 0.10


class WalkForwardBacktest:
    """Walk-forward backtest that scores tickers at each rebalance date
    using ONLY data available up to that point (no look-ahead bias),
    then records actual forward returns.

    Usage::

        bt = WalkForwardBacktest(
            tickers=["TOELY", "NVDA", "ASML"],
            start_date="2024-01-01",
            end_date="2025-12-31",
            rebalance_freq="monthly",
            include_transaction_costs=True,
        )
        results = bt.run()
        print(bt.summary())
    """

    def __init__(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        rebalance_freq: str = "monthly",
        include_transaction_costs: bool = True,
    ):
        self.tickers = tickers
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.rebalance_freq = rebalance_freq
        self.include_transaction_costs = include_transaction_costs
        self.market = MarketDataClient()
        self.results: list[BacktestResult] = []

    def _rebalance_dates(self) -> list[pd.Timestamp]:
        """Generate rebalance dates between start and end."""
        freq_map = {
            "monthly": "MS",
            "quarterly": "QS",
            "weekly": "W-MON",
        }
        freq = freq_map.get(self.rebalance_freq, "MS")
        return list(pd.date_range(self.start_date, self.end_date, freq=freq))

    def _get_forward_return(self, price_df: pd.DataFrame, from_date: pd.Timestamp,
                            days: int) -> float | None:
        """Get forward return starting from a given date."""
        try:
            future = price_df[price_df.index >= from_date]
            if len(future) < 2:
                return None
            start_price = float(future["Close"].iloc[0])
            target_date = from_date + timedelta(days=days)
            end_prices = future[future.index <= target_date]
            if end_prices.empty:
                return None
            end_price = float(end_prices["Close"].iloc[-1])
            return (end_price / start_price - 1) * 100 if start_price > 0 else None
        except Exception:
            return None

    def run(self) -> list[BacktestResult]:
        """Execute the walk-forward backtest with point-in-time scoring."""
        logger.info("Starting walk-forward backtest: %d tickers, %s to %s",
                     len(self.tickers), self.start_date.date(), self.end_date.date())
        logger.info("Scoring method: point-in-time price-based (no look-ahead bias)")
        if self.include_transaction_costs:
            logger.info("Transaction costs: enabled (Corwin-Schultz spread + OTC ADR floor)")

        # Pre-fetch all price data (max history for point-in-time slicing)
        price_data: dict[str, pd.DataFrame] = {}
        for ticker in self.tickers:
            df = self.market.get_price_history(ticker, period="max")
            if not df.empty:
                price_data[ticker] = df

        rebalance_dates = self._rebalance_dates()
        logger.info("Rebalance dates: %d", len(rebalance_dates))

        self.results = []
        for rb_date in rebalance_dates:
            for ticker in self.tickers:
                try:
                    df = price_data.get(ticker)
                    if df is None or df.empty:
                        continue

                    # POINT-IN-TIME: slice data up to rebalance date only
                    historical = df[df.index < rb_date]
                    if len(historical) < 30:
                        continue  # Not enough history to score

                    # Score using only historical data — no look-ahead
                    composite, sub_scores = _point_in_time_score(historical)

                    # Estimate transaction costs from historical data
                    txn_cost = 0.0
                    if self.include_transaction_costs:
                        txn_cost = _estimate_txn_cost(ticker, historical)

                    # Get forward returns from FULL price data (these are actual outcomes)
                    fwd_1m = self._get_forward_return(df, rb_date, 30)
                    fwd_3m = self._get_forward_return(df, rb_date, 90)
                    fwd_6m = self._get_forward_return(df, rb_date, 180)

                    # Deduct transaction costs from forward returns
                    if self.include_transaction_costs and txn_cost > 0:
                        if fwd_1m is not None:
                            fwd_1m -= txn_cost
                        if fwd_3m is not None:
                            fwd_3m -= txn_cost
                        if fwd_6m is not None:
                            fwd_6m -= txn_cost

                    self.results.append(BacktestResult(
                        date=str(rb_date.date()),
                        ticker=ticker,
                        composite_score=composite,
                        sub_scores=sub_scores,
                        forward_1m=fwd_1m,
                        forward_3m=fwd_3m,
                        forward_6m=fwd_6m,
                        transaction_cost_pct=round(txn_cost, 3),
                    ))
                except Exception as e:
                    logger.warning("Scoring failed for %s on %s: %s", ticker, rb_date.date(), e)

        logger.info("Backtest complete: %d results", len(self.results))
        return self.results

    def summary(self) -> dict:
        """Compute summary statistics: quintile spread, hit rate, t-statistic."""
        if not self.results:
            return {"error": "No results. Run backtest first."}

        df = pd.DataFrame([
            {
                "date": r.date,
                "ticker": r.ticker,
                "score": r.composite_score,
                "fwd_1m": r.forward_1m,
                "fwd_3m": r.forward_3m,
                "fwd_6m": r.forward_6m,
                "txn_cost": r.transaction_cost_pct,
            }
            for r in self.results
        ])

        summary: dict = {
            "total_observations": len(df),
            "tickers": self.tickers,
            "date_range": f"{self.start_date.date()} to {self.end_date.date()}",
            "rebalance_freq": self.rebalance_freq,
            "scoring_method": "point-in-time price-based (no look-ahead bias)",
            "transaction_costs_included": self.include_transaction_costs,
            "avg_transaction_cost_pct": round(float(df["txn_cost"].mean()), 3),
        }

        for horizon, col in [("1m", "fwd_1m"), ("3m", "fwd_3m"), ("6m", "fwd_6m")]:
            valid = df.dropna(subset=[col])
            if len(valid) < 10:
                summary[f"{horizon}_quintile_spread"] = None
                continue

            # Quintile analysis
            valid = valid.copy()
            valid["quintile"] = pd.qcut(valid["score"], 5, labels=False, duplicates="drop")

            q_means = valid.groupby("quintile")[col].mean()
            top_q = q_means.iloc[-1] if len(q_means) >= 5 else q_means.max()
            bot_q = q_means.iloc[0] if len(q_means) >= 5 else q_means.min()
            spread = top_q - bot_q

            # Hit rate: % of top quintile with positive returns
            top_quintile = valid[valid["quintile"] == valid["quintile"].max()]
            hit_rate = (top_quintile[col] > 0).mean() if len(top_quintile) > 0 else None

            # t-statistic for spread significance
            from scipy import stats
            top_returns = valid[valid["quintile"] == valid["quintile"].max()][col]
            bot_returns = valid[valid["quintile"] == valid["quintile"].min()][col]
            if len(top_returns) > 2 and len(bot_returns) > 2:
                t_stat, p_value = stats.ttest_ind(top_returns, bot_returns)
            else:
                t_stat, p_value = None, None

            summary[f"{horizon}_quintile_spread"] = round(spread, 2) if pd.notna(spread) else None
            summary[f"{horizon}_top_quintile_avg"] = round(top_q, 2) if pd.notna(top_q) else None
            summary[f"{horizon}_bot_quintile_avg"] = round(bot_q, 2) if pd.notna(bot_q) else None
            summary[f"{horizon}_hit_rate"] = round(hit_rate, 3) if hit_rate is not None else None
            summary[f"{horizon}_t_statistic"] = round(t_stat, 3) if t_stat is not None else None
            summary[f"{horizon}_p_value"] = round(p_value, 4) if p_value is not None else None

        # Score-return correlation
        for horizon, col in [("1m", "fwd_1m"), ("3m", "fwd_3m"), ("6m", "fwd_6m")]:
            valid = df.dropna(subset=[col])
            if len(valid) >= 10:
                corr = valid["score"].corr(valid[col])
                summary[f"{horizon}_score_return_corr"] = round(corr, 4) if pd.notna(corr) else None

        return summary
