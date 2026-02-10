"""Hedge fund-grade backtesting framework for FE-Analyst.

Provides signal backtesting, walk-forward validation, full strategy simulation,
statistical significance testing, and benchmark comparison utilities.

This is a standalone utility module -- not a pipeline analyzer plugin.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional, List, Dict, Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("backtesting")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TRADING_DAYS_PER_YEAR = 252
DEFAULT_FORWARD_PERIODS: List[int] = [1, 5, 10, 21]

# Suppress numpy / pandas warnings during vectorised ops
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ===================================================================
# Data class: StrategyResult  (the "tearsheet")
# ===================================================================

@dataclass
class StrategyResult:
    """Full performance tearsheet for a backtested strategy."""

    # --- Equity & returns ---
    equity_curve: List[float] = field(default_factory=list)
    positions: List[int] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)

    # --- Summary metrics ---
    cumulative_return: float = 0.0
    benchmark_cumulative_return: float = 0.0
    annual_return: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0

    # --- Trade statistics ---
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    win_loss_ratio: float = 0.0
    num_trades: int = 0
    avg_holding_period: float = 0.0

    # --- Monthly / rolling ---
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    rolling_12m_sharpe: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a fully JSON-serializable dictionary."""
        return _jsonify(asdict(self))


# ===================================================================
# Helper: ensure JSON-serialisability
# ===================================================================

def _jsonify(obj: Any) -> Any:
    """Recursively convert numpy/pandas types to native Python types."""
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [_jsonify(v) for v in obj.tolist()]
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return 0.0
    return obj


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Division that returns *default* when denominator is zero/nan."""
    if b == 0 or np.isnan(b):
        return default
    return float(a / b)


# ===================================================================
# SignalBacktester
# ===================================================================

class SignalBacktester:
    """Evaluate the predictive power of a trading signal function.

    A signal function accepts an OHLCV DataFrame and returns a
    ``pd.Series`` of integer signals: -1 (sell), 0 (flat), +1 (buy).
    """

    def __init__(self, market_data_client: Optional[MarketDataClient] = None) -> None:
        self._mdc = market_data_client or MarketDataClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def backtest_signal(
        self,
        ticker: str,
        signal_fn: Callable[[pd.DataFrame], pd.Series],
        lookback_period: str = "2y",
        forward_periods: Optional[List[int]] = None,
        entry_rule: Optional[Callable[[pd.DataFrame, int], bool]] = None,
        exit_rule: Optional[Callable[[pd.DataFrame, int, int], bool]] = None,
    ) -> Dict[str, Any]:
        """Backtest a signal function and compute forward-return statistics.

        Args:
            ticker: Stock symbol.
            signal_fn: Maps OHLCV DataFrame -> Series of {-1, 0, +1}.
            lookback_period: How much history to fetch (yfinance period str).
            forward_periods: List of forward horizons in trading days.
            entry_rule: Optional filter ``(df, idx) -> bool``.  If provided,
                a signal at row *idx* is only honoured when the function
                returns True.
            exit_rule: Optional early-exit ``(df, entry_idx, current_idx) -> bool``.
                Not used in hit-rate calculation but recorded in metadata.

        Returns:
            Dictionary with hit_rate, avg_return_by_direction,
            profit_factor, and per-horizon breakdown.
        """
        forward_periods = forward_periods or DEFAULT_FORWARD_PERIODS

        df = self._mdc.get_price_history(ticker, period=lookback_period)
        if df is None or df.empty or len(df) < max(forward_periods) + 10:
            logger.warning("Insufficient data for %s", ticker)
            return self._empty_signal_result(forward_periods)

        signals = signal_fn(df)
        if signals is None or signals.empty:
            logger.warning("Signal function returned empty series for %s", ticker)
            return self._empty_signal_result(forward_periods)

        # Align index
        signals = signals.reindex(df.index).fillna(0).astype(int)

        # Apply optional entry filter
        if entry_rule is not None:
            mask = pd.Series(False, index=df.index)
            for i in range(len(df)):
                if signals.iloc[i] != 0:
                    mask.iloc[i] = entry_rule(df, i)
            signals = signals.where(mask, other=0)

        close = df["Close"]

        horizon_results: Dict[str, Any] = {}
        all_correct = 0
        all_total = 0

        for fp in forward_periods:
            fwd_ret = close.pct_change(fp).shift(-fp)
            aligned = pd.DataFrame({"signal": signals, "fwd_ret": fwd_ret}).dropna()

            buy_mask = aligned["signal"] == 1
            sell_mask = aligned["signal"] == -1

            buy_returns = aligned.loc[buy_mask, "fwd_ret"]
            sell_returns = aligned.loc[sell_mask, "fwd_ret"]

            # For shorts the P/L is -1 * return
            buy_correct = int((buy_returns > 0).sum()) if len(buy_returns) else 0
            sell_correct = int((sell_returns < 0).sum()) if len(sell_returns) else 0
            total_signals = len(buy_returns) + len(sell_returns)

            hit_rate = _safe_div(buy_correct + sell_correct, total_signals)

            avg_buy = float(buy_returns.mean()) if len(buy_returns) else 0.0
            avg_sell = float(sell_returns.mean()) if len(sell_returns) else 0.0

            # Profit factor: gross profits / gross losses
            profits = float(buy_returns[buy_returns > 0].sum()) + float(
                (-sell_returns[sell_returns < 0]).sum()
            )
            losses = abs(float(buy_returns[buy_returns < 0].sum())) + abs(
                float(sell_returns[sell_returns > 0].sum())
            )
            profit_factor = _safe_div(profits, losses)

            all_correct += buy_correct + sell_correct
            all_total += total_signals

            horizon_results[f"{fp}d"] = _jsonify(
                {
                    "forward_days": fp,
                    "total_signals": total_signals,
                    "hit_rate": round(hit_rate, 4),
                    "avg_return_buy": round(avg_buy, 6),
                    "avg_return_sell": round(avg_sell, 6),
                    "profit_factor": round(profit_factor, 4),
                    "buy_signals": int(buy_mask.sum()),
                    "sell_signals": int(sell_mask.sum()),
                }
            )

        overall_hit = _safe_div(all_correct, all_total)

        return _jsonify(
            {
                "ticker": ticker,
                "lookback_period": lookback_period,
                "overall_hit_rate": round(overall_hit, 4),
                "horizons": horizon_results,
                "has_entry_rule": entry_rule is not None,
                "has_exit_rule": exit_rule is not None,
            }
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_signal_result(forward_periods: List[int]) -> Dict[str, Any]:
        horizons = {}
        for fp in forward_periods:
            horizons[f"{fp}d"] = {
                "forward_days": fp,
                "total_signals": 0,
                "hit_rate": 0.0,
                "avg_return_buy": 0.0,
                "avg_return_sell": 0.0,
                "profit_factor": 0.0,
                "buy_signals": 0,
                "sell_signals": 0,
            }
        return {
            "ticker": "",
            "lookback_period": "",
            "overall_hit_rate": 0.0,
            "horizons": horizons,
            "has_entry_rule": False,
            "has_exit_rule": False,
        }


# ===================================================================
# Walk-Forward Validator
# ===================================================================

class WalkForwardValidator:
    """Rolling walk-forward analysis with non-overlapping train/test windows."""

    def __init__(self, market_data_client: Optional[MarketDataClient] = None) -> None:
        self._mdc = market_data_client or MarketDataClient()

    def walk_forward(
        self,
        ticker: str,
        strategy_fn: Callable[[pd.DataFrame], pd.Series],
        train_window: int = 252,
        test_window: int = 63,
        n_splits: int = 4,
        period: str = "5y",
    ) -> Dict[str, Any]:
        """Perform rolling walk-forward validation.

        Args:
            ticker: Stock symbol.
            strategy_fn: Accepts a *training* DataFrame, returns a signal
                Series aligned to the **full** DataFrame index.  Signals
                outside the test window are ignored.
            train_window: Number of trading days for training.
            test_window: Number of trading days for out-of-sample testing.
            n_splits: Number of rolling splits.
            period: How much history to fetch.

        Returns:
            Dictionary with oos_returns, oos_sharpe, oos_hit_rate,
            stability_ratio, and per-split breakdown.
        """
        df = self._mdc.get_price_history(ticker, period=period)
        if df is None or df.empty:
            logger.warning("No data for walk-forward on %s", ticker)
            return self._empty_wf_result()

        required_len = train_window + test_window * n_splits
        if len(df) < required_len:
            available_splits = max(1, (len(df) - train_window) // test_window)
            n_splits = min(n_splits, available_splits)
            if n_splits == 0:
                logger.warning(
                    "History too short for walk-forward on %s (%d rows)", ticker, len(df)
                )
                return self._empty_wf_result()
            logger.info(
                "Reducing n_splits to %d for %s (only %d rows available)",
                n_splits, ticker, len(df),
            )

        close = df["Close"]
        daily_returns = close.pct_change().fillna(0.0)

        oos_returns_list: List[pd.Series] = []
        split_results: List[Dict[str, Any]] = []
        profitable_windows = 0

        # Walk forward from the end of the data backwards so that the most
        # recent window is always included.
        total_len = len(df)
        for i in range(n_splits):
            test_end = total_len - i * test_window
            test_start = test_end - test_window
            train_end = test_start
            train_start = max(0, train_end - train_window)

            if train_start >= train_end or test_start >= test_end or test_start < 0:
                continue

            train_df = df.iloc[train_start:train_end].copy()
            test_df = df.iloc[test_start:test_end].copy()

            # Generate signals from training data
            try:
                signals = strategy_fn(train_df)
            except Exception as exc:  # noqa: BLE001
                logger.error("strategy_fn failed on split %d: %s", i, exc)
                continue

            # Map signals onto the test window (forward-fill last training signal)
            if signals is None or signals.empty:
                test_signals = pd.Series(0, index=test_df.index)
            else:
                # The strategy may return signals indexed to train_df.  We
                # forward-fill the last known signal into the test period.
                last_signal = int(signals.iloc[-1]) if len(signals) else 0
                test_signals = pd.Series(last_signal, index=test_df.index)
                # If strategy_fn returns signals covering test range, use them
                overlap = signals.index.intersection(test_df.index)
                if len(overlap):
                    test_signals.loc[overlap] = signals.loc[overlap]

            test_daily = daily_returns.reindex(test_df.index).fillna(0.0)
            position_returns = test_signals * test_daily
            oos_returns_list.append(position_returns)

            window_return = float((1 + position_returns).prod() - 1)
            if window_return > 0:
                profitable_windows += 1

            split_results.append(
                {
                    "split": i,
                    "train_start": str(train_df.index[0].date()),
                    "train_end": str(train_df.index[-1].date()),
                    "test_start": str(test_df.index[0].date()),
                    "test_end": str(test_df.index[-1].date()),
                    "window_return": round(window_return, 6),
                    "window_hit_rate": round(
                        _safe_div(
                            float((position_returns > 0).sum()),
                            float((position_returns != 0).sum()),
                        ),
                        4,
                    ),
                }
            )

        if not oos_returns_list:
            return self._empty_wf_result()

        oos_returns = pd.concat(oos_returns_list).sort_index()
        oos_mean = float(oos_returns.mean())
        oos_std = float(oos_returns.std())
        oos_sharpe = _safe_div(oos_mean, oos_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
        oos_hit = _safe_div(float((oos_returns > 0).sum()), float((oos_returns != 0).sum()))
        stability = _safe_div(profitable_windows, len(split_results))

        return _jsonify(
            {
                "ticker": ticker,
                "n_splits": len(split_results),
                "train_window": train_window,
                "test_window": test_window,
                "oos_returns": oos_returns.tolist(),
                "oos_sharpe": round(float(oos_sharpe), 4),
                "oos_hit_rate": round(float(oos_hit), 4),
                "stability_ratio": round(float(stability), 4),
                "splits": split_results,
            }
        )

    @staticmethod
    def _empty_wf_result() -> Dict[str, Any]:
        return {
            "ticker": "",
            "n_splits": 0,
            "train_window": 0,
            "test_window": 0,
            "oos_returns": [],
            "oos_sharpe": 0.0,
            "oos_hit_rate": 0.0,
            "stability_ratio": 0.0,
            "splits": [],
        }


# ===================================================================
# StrategyBacktester
# ===================================================================

class StrategyBacktester:
    """Full event-driven strategy backtester with transaction-cost modelling."""

    def __init__(self, market_data_client: Optional[MarketDataClient] = None) -> None:
        self._mdc = market_data_client or MarketDataClient()

    def backtest_strategy(
        self,
        ticker: str,
        signal_series: pd.Series,
        prices: Optional[pd.Series] = None,
        initial_capital: float = 100_000.0,
        commission_bps: float = 10.0,
        benchmark_ticker: Optional[str] = None,
    ) -> StrategyResult:
        """Simulate a long/short strategy and produce a full tearsheet.

        Args:
            ticker: Identifier (used for logging and labelling).
            signal_series: Integer series {-1, 0, +1} aligned to price index.
            prices: Close-price series. If ``None``, fetched via
                ``MarketDataClient.get_price_history``.
            initial_capital: Starting equity.
            commission_bps: One-way commission in basis points.
            benchmark_ticker: Optional ticker for benchmark comparison
                (defaults to buy-and-hold of *ticker*).

        Returns:
            A fully populated ``StrategyResult``.
        """
        if prices is None:
            df = self._mdc.get_price_history(ticker, period="5y")
            if df is None or df.empty:
                logger.warning("No price data for %s", ticker)
                return StrategyResult()
            prices = df["Close"]

        # Align signals & prices
        common_idx = signal_series.index.intersection(prices.index)
        if len(common_idx) < 2:
            logger.warning("Not enough overlapping data for %s", ticker)
            return StrategyResult()

        prices = prices.loc[common_idx].copy()
        signals = signal_series.reindex(common_idx).fillna(0).astype(int).clip(-1, 1)

        daily_returns = prices.pct_change().fillna(0.0)
        commission_rate = commission_bps / 10_000.0

        # ---- Position tracking & cost application ----
        positions = signals.values.copy()
        position_changes = np.diff(positions, prepend=0)
        abs_changes = np.abs(position_changes)
        costs = abs_changes * commission_rate  # fraction of capital lost per trade

        strategy_gross = positions * daily_returns.values
        strategy_net = strategy_gross - costs

        # ---- Equity curve ----
        equity = initial_capital * np.cumprod(1 + strategy_net)
        equity_list = [round(float(e), 2) for e in equity]

        # ---- Benchmark (buy-and-hold) ----
        bench_equity = initial_capital * np.cumprod(1 + daily_returns.values)
        bench_cum = float(bench_equity[-1] / initial_capital - 1) if len(bench_equity) else 0.0

        # ---- Trade extraction ----
        trades = self._extract_trades(common_idx, positions, prices.values, strategy_net)

        # ---- Metrics ----
        cum_ret = float(equity[-1] / initial_capital - 1) if len(equity) else 0.0
        n_days = len(strategy_net)
        ann_factor = TRADING_DAYS_PER_YEAR

        ann_ret = float((1 + cum_ret) ** (ann_factor / max(n_days, 1)) - 1)
        ann_vol = float(np.std(strategy_net, ddof=1) * np.sqrt(ann_factor)) if n_days > 1 else 0.0
        sharpe = _safe_div(ann_ret, ann_vol)

        downside = strategy_net[strategy_net < 0]
        downside_std = float(np.std(downside, ddof=1) * np.sqrt(ann_factor)) if len(downside) > 1 else 0.0
        sortino = _safe_div(ann_ret, downside_std)

        # Max drawdown
        running_max = np.maximum.accumulate(equity)
        drawdowns = (equity - running_max) / running_max
        max_dd = float(np.min(drawdowns)) if len(drawdowns) else 0.0
        calmar = _safe_div(ann_ret, abs(max_dd))

        # Max drawdown duration (in trading days)
        dd_duration = self._max_dd_duration(equity)

        # Trade stats
        trade_pnls = [t["pnl_pct"] for t in trades]
        wins = [p for p in trade_pnls if p > 0]
        losses = [p for p in trade_pnls if p < 0]
        win_rate = _safe_div(len(wins), len(trade_pnls))
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        wl_ratio = _safe_div(avg_win, abs(avg_loss)) if avg_loss != 0.0 else 0.0
        gross_profit = float(np.sum(wins)) if wins else 0.0
        gross_loss = abs(float(np.sum(losses))) if losses else 0.0
        profit_factor = _safe_div(gross_profit, gross_loss)
        holding_periods = [t["holding_days"] for t in trades]
        avg_hold = float(np.mean(holding_periods)) if holding_periods else 0.0

        # Monthly returns table
        monthly_rets = self._monthly_returns(common_idx, strategy_net)

        # Rolling 12-month Sharpe
        rolling_sharpe = self._rolling_sharpe(strategy_net, window=ann_factor)

        return StrategyResult(
            equity_curve=equity_list,
            positions=[int(p) for p in positions],
            trades=trades,
            cumulative_return=round(float(cum_ret), 6),
            benchmark_cumulative_return=round(float(bench_cum), 6),
            annual_return=round(float(ann_ret), 6),
            annual_volatility=round(float(ann_vol), 6),
            sharpe_ratio=round(float(sharpe), 4),
            sortino_ratio=round(float(sortino), 4),
            calmar_ratio=round(float(calmar), 4),
            max_drawdown=round(float(max_dd), 6),
            max_drawdown_duration=int(dd_duration),
            win_rate=round(float(win_rate), 4),
            profit_factor=round(float(profit_factor), 4),
            average_win=round(float(avg_win), 6),
            average_loss=round(float(avg_loss), 6),
            win_loss_ratio=round(float(wl_ratio), 4),
            num_trades=len(trades),
            avg_holding_period=round(float(avg_hold), 2),
            monthly_returns=monthly_rets,
            rolling_12m_sharpe=rolling_sharpe,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_trades(
        index: pd.DatetimeIndex,
        positions: np.ndarray,
        prices: np.ndarray,
        net_returns: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """Walk through positions and extract individual round-trip trades."""
        trades: List[Dict[str, Any]] = []
        in_trade = False
        entry_idx = 0
        entry_price = 0.0
        direction = 0

        for i in range(len(positions)):
            pos = int(positions[i])
            if not in_trade and pos != 0:
                in_trade = True
                entry_idx = i
                entry_price = float(prices[i])
                direction = pos
            elif in_trade and pos != direction:
                # Close current trade
                exit_price = float(prices[i])
                pnl_pct = direction * (exit_price / entry_price - 1)
                trades.append(
                    {
                        "entry_date": str(index[entry_idx].date()),
                        "exit_date": str(index[i].date()),
                        "direction": "LONG" if direction == 1 else "SHORT",
                        "entry_price": round(entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "pnl_pct": round(float(pnl_pct), 6),
                        "holding_days": int(i - entry_idx),
                    }
                )
                # If new position opens immediately
                if pos != 0:
                    entry_idx = i
                    entry_price = float(prices[i])
                    direction = pos
                else:
                    in_trade = False

        # Close any open trade at the end
        if in_trade and len(positions) > 0:
            last_i = len(positions) - 1
            exit_price = float(prices[last_i])
            pnl_pct = direction * (exit_price / entry_price - 1)
            trades.append(
                {
                    "entry_date": str(index[entry_idx].date()),
                    "exit_date": str(index[last_i].date()),
                    "direction": "LONG" if direction == 1 else "SHORT",
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "pnl_pct": round(float(pnl_pct), 6),
                    "holding_days": int(last_i - entry_idx),
                }
            )

        return trades

    @staticmethod
    def _max_dd_duration(equity: np.ndarray) -> int:
        """Return the longest drawdown duration in trading days."""
        if len(equity) == 0:
            return 0
        running_max = np.maximum.accumulate(equity)
        in_dd = equity < running_max
        max_dur = 0
        current = 0
        for flag in in_dd:
            if flag:
                current += 1
                max_dur = max(max_dur, current)
            else:
                current = 0
        return max_dur

    @staticmethod
    def _monthly_returns(
        index: pd.DatetimeIndex, net_returns: np.ndarray
    ) -> Dict[str, float]:
        """Aggregate daily returns into monthly buckets."""
        s = pd.Series(net_returns, index=index)
        monthly = s.resample("ME").apply(lambda x: float((1 + x).prod() - 1))
        return {dt.strftime("%Y-%m"): round(float(v), 6) for dt, v in monthly.items()}

    @staticmethod
    def _rolling_sharpe(net_returns: np.ndarray, window: int = 252) -> List[float]:
        """Compute rolling annualised Sharpe ratio."""
        if len(net_returns) < window:
            return []
        s = pd.Series(net_returns)
        rolling_mean = s.rolling(window).mean()
        rolling_std = s.rolling(window).std(ddof=1)
        rolling_sr = (rolling_mean / rolling_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
        return [round(float(v), 4) if pd.notna(v) else 0.0 for v in rolling_sr.dropna()]


# ===================================================================
# Statistical Significance Testing
# ===================================================================

class SignificanceTester:
    """Statistical tests for strategy returns."""

    @staticmethod
    def test_significance(
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
        n_bootstrap: int = 1000,
        confidence: float = 0.95,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """Test whether strategy excess returns are statistically significant.

        Args:
            strategy_returns: Daily strategy returns.
            benchmark_returns: Daily benchmark returns.
            n_bootstrap: Number of bootstrap resamples for Sharpe CI.
            confidence: Confidence level for the interval.
            random_seed: Seed for reproducibility.

        Returns:
            Dictionary with t_statistic, p_value, sharpe_ci_lower,
            sharpe_ci_upper, and is_significant flag.
        """
        # Align
        common = strategy_returns.index.intersection(benchmark_returns.index)
        if len(common) < 10:
            logger.warning(
                "Too few overlapping observations (%d) for significance test", len(common)
            )
            return {
                "t_statistic": 0.0,
                "p_value": 1.0,
                "sharpe_ci_lower": 0.0,
                "sharpe_ci_upper": 0.0,
                "is_significant": False,
                "n_observations": int(len(common)),
            }

        strat = strategy_returns.loc[common].values.astype(float)
        bench = benchmark_returns.loc[common].values.astype(float)
        excess = strat - bench

        # --- T-test: H0 = mean excess return == 0 ---
        t_stat, p_val = sp_stats.ttest_1samp(excess, 0.0)
        t_stat = float(t_stat)
        p_val = float(p_val)

        # Handle NaN from constant arrays
        if np.isnan(t_stat):
            t_stat = 0.0
        if np.isnan(p_val):
            p_val = 1.0

        # --- Bootstrap Sharpe ratio confidence interval ---
        rng = np.random.RandomState(random_seed)
        boot_sharpes: List[float] = []
        n = len(excess)
        for _ in range(n_bootstrap):
            sample = rng.choice(excess, size=n, replace=True)
            sample_std = float(np.std(sample, ddof=1))
            if sample_std > 0:
                sr = float(np.mean(sample)) / sample_std * np.sqrt(TRADING_DAYS_PER_YEAR)
            else:
                sr = 0.0
            boot_sharpes.append(sr)

        alpha = 1 - confidence
        ci_lower = float(np.percentile(boot_sharpes, 100 * alpha / 2))
        ci_upper = float(np.percentile(boot_sharpes, 100 * (1 - alpha / 2)))

        return _jsonify(
            {
                "t_statistic": round(t_stat, 4),
                "p_value": round(p_val, 6),
                "sharpe_ci_lower": round(ci_lower, 4),
                "sharpe_ci_upper": round(ci_upper, 4),
                "is_significant": bool(p_val < 0.05),
                "n_observations": int(len(common)),
                "n_bootstrap": n_bootstrap,
            }
        )


# ===================================================================
# Benchmark Comparison
# ===================================================================

class BenchmarkComparator:
    """Compare strategy returns against a benchmark."""

    @staticmethod
    def compare_to_benchmark(
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> Dict[str, Any]:
        """Compute alpha, beta, tracking error, information ratio, and
        up/down capture ratios.

        Args:
            strategy_returns: Daily strategy returns.
            benchmark_returns: Daily benchmark returns.

        Returns:
            Dictionary with alpha, beta, tracking_error,
            information_ratio, up_capture, down_capture.
        """
        common = strategy_returns.index.intersection(benchmark_returns.index)
        if len(common) < 10:
            logger.warning("Too few overlapping observations for benchmark comparison")
            return {
                "alpha": 0.0,
                "beta": 0.0,
                "tracking_error": 0.0,
                "information_ratio": 0.0,
                "up_capture": 0.0,
                "down_capture": 0.0,
            }

        strat = strategy_returns.loc[common].values.astype(float)
        bench = benchmark_returns.loc[common].values.astype(float)

        # --- Alpha & Beta via OLS regression ---
        # strat = alpha + beta * bench + epsilon
        bench_with_const = np.column_stack([np.ones(len(bench)), bench])
        try:
            coeffs, _residuals, _rank, _sv = np.linalg.lstsq(bench_with_const, strat, rcond=None)
            daily_alpha = float(coeffs[0])
            beta = float(coeffs[1])
        except np.linalg.LinAlgError:
            daily_alpha = 0.0
            beta = 0.0

        # Annualise alpha
        alpha = daily_alpha * TRADING_DAYS_PER_YEAR

        # --- Tracking error & Information ratio ---
        excess = strat - bench
        tracking_error = float(np.std(excess, ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR)
        mean_excess_ann = float(np.mean(excess)) * TRADING_DAYS_PER_YEAR
        information_ratio = _safe_div(mean_excess_ann, tracking_error)

        # --- Up/Down capture ---
        up_days = bench > 0
        down_days = bench < 0

        if up_days.sum() > 0:
            up_capture = _safe_div(
                float(np.mean(strat[up_days])), float(np.mean(bench[up_days]))
            )
        else:
            up_capture = 0.0

        if down_days.sum() > 0:
            down_capture = _safe_div(
                float(np.mean(strat[down_days])), float(np.mean(bench[down_days]))
            )
        else:
            down_capture = 0.0

        return _jsonify(
            {
                "alpha": round(float(alpha), 6),
                "beta": round(float(beta), 4),
                "tracking_error": round(float(tracking_error), 6),
                "information_ratio": round(float(information_ratio), 4),
                "up_capture": round(float(up_capture), 4),
                "down_capture": round(float(down_capture), 4),
            }
        )


# ===================================================================
# Built-in Signal Functions
# ===================================================================

def rsi_signal(
    df: pd.DataFrame,
    oversold: float = 30.0,
    overbought: float = 70.0,
    window: int = 14,
) -> pd.Series:
    """Generate buy/sell signals from RSI levels.

    +1 when RSI crosses below *oversold*, -1 when above *overbought*, else 0.
    """
    close = df["Close"]
    rsi = RSIIndicator(close, window=window).rsi()
    signals = pd.Series(0, index=df.index, dtype=int)
    signals[rsi < oversold] = 1
    signals[rsi > overbought] = -1
    return signals


def ma_crossover_signal(
    df: pd.DataFrame,
    fast: int = 20,
    slow: int = 50,
) -> pd.Series:
    """Generate signals from moving-average crossover.

    +1 when fast SMA crosses above slow SMA, -1 when below.
    """
    close = df["Close"]
    sma_fast = SMAIndicator(close, window=fast).sma_indicator()
    sma_slow = SMAIndicator(close, window=slow).sma_indicator()

    signals = pd.Series(0, index=df.index, dtype=int)
    signals[sma_fast > sma_slow] = 1
    signals[sma_fast < sma_slow] = -1
    return signals


def macd_signal(df: pd.DataFrame) -> pd.Series:
    """Generate signals from MACD / signal-line crossover.

    +1 when MACD > signal line, -1 when MACD < signal line.
    """
    close = df["Close"]
    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd.macd()
    signal_line = macd.macd_signal()

    signals = pd.Series(0, index=df.index, dtype=int)
    signals[macd_line > signal_line] = 1
    signals[macd_line < signal_line] = -1
    return signals


def bollinger_signal(df: pd.DataFrame, window: int = 20, window_dev: int = 2) -> pd.Series:
    """Generate mean-reversion signals from Bollinger Bands.

    +1 when price closes below lower band (expect reversion up),
    -1 when price closes above upper band (expect reversion down).
    """
    close = df["Close"]
    bb = BollingerBands(close, window=window, window_dev=window_dev)
    upper = bb.bollinger_hband()
    lower = bb.bollinger_lband()

    signals = pd.Series(0, index=df.index, dtype=int)
    signals[close < lower] = 1
    signals[close > upper] = -1
    return signals


def composite_signal(df: pd.DataFrame) -> pd.Series:
    """Majority-vote ensemble of RSI, MA crossover, MACD, and Bollinger signals.

    Each sub-signal votes {-1, 0, +1}.  The composite is the sign of the
    sum; ties resolve to 0.
    """
    sig_rsi = rsi_signal(df)
    sig_ma = ma_crossover_signal(df)
    sig_macd = macd_signal(df)
    sig_bb = bollinger_signal(df)

    vote_sum = sig_rsi + sig_ma + sig_macd + sig_bb
    signals = pd.Series(0, index=df.index, dtype=int)
    signals[vote_sum > 0] = 1
    signals[vote_sum < 0] = -1
    return signals


# ===================================================================
# Convenience wrappers (top-level functions)
# ===================================================================

def backtest_signal(
    ticker: str,
    signal_fn: Callable[[pd.DataFrame], pd.Series],
    lookback_period: str = "2y",
    forward_periods: Optional[List[int]] = None,
    entry_rule: Optional[Callable[[pd.DataFrame, int], bool]] = None,
    exit_rule: Optional[Callable[[pd.DataFrame, int, int], bool]] = None,
    market_data_client: Optional[MarketDataClient] = None,
) -> Dict[str, Any]:
    """Module-level shortcut for :meth:`SignalBacktester.backtest_signal`."""
    bt = SignalBacktester(market_data_client)
    return bt.backtest_signal(
        ticker,
        signal_fn,
        lookback_period=lookback_period,
        forward_periods=forward_periods,
        entry_rule=entry_rule,
        exit_rule=exit_rule,
    )


def walk_forward(
    ticker: str,
    strategy_fn: Callable[[pd.DataFrame], pd.Series],
    train_window: int = 252,
    test_window: int = 63,
    n_splits: int = 4,
    period: str = "5y",
    market_data_client: Optional[MarketDataClient] = None,
) -> Dict[str, Any]:
    """Module-level shortcut for :meth:`WalkForwardValidator.walk_forward`."""
    wfv = WalkForwardValidator(market_data_client)
    return wfv.walk_forward(
        ticker, strategy_fn,
        train_window=train_window,
        test_window=test_window,
        n_splits=n_splits,
        period=period,
    )


def backtest_strategy(
    ticker: str,
    signal_series: pd.Series,
    prices: Optional[pd.Series] = None,
    initial_capital: float = 100_000.0,
    commission_bps: float = 10.0,
    benchmark_ticker: Optional[str] = None,
    market_data_client: Optional[MarketDataClient] = None,
) -> StrategyResult:
    """Module-level shortcut for :meth:`StrategyBacktester.backtest_strategy`."""
    sb = StrategyBacktester(market_data_client)
    return sb.backtest_strategy(
        ticker,
        signal_series,
        prices=prices,
        initial_capital=initial_capital,
        commission_bps=commission_bps,
        benchmark_ticker=benchmark_ticker,
    )


def test_significance(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Module-level shortcut for :meth:`SignificanceTester.test_significance`."""
    return SignificanceTester.test_significance(
        strategy_returns,
        benchmark_returns,
        n_bootstrap=n_bootstrap,
        confidence=confidence,
        random_seed=random_seed,
    )


def compare_to_benchmark(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> Dict[str, Any]:
    """Module-level shortcut for :meth:`BenchmarkComparator.compare_to_benchmark`."""
    return BenchmarkComparator.compare_to_benchmark(strategy_returns, benchmark_returns)
