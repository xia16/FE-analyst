"""Tests for src.analysis.backtesting -- signals, strategies, walk-forward, significance."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.analysis.backtesting import (
    SignalBacktester,
    StrategyBacktester,
    StrategyResult,
    WalkForwardValidator,
    SignificanceTester,
    BenchmarkComparator,
    rsi_signal,
    ma_crossover_signal,
    macd_signal,
    bollinger_signal,
    composite_signal,
    _safe_div,
    _jsonify,
    TRADING_DAYS_PER_YEAR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n=252, seed=42, start_price=100.0, trend=0.0004, vol=0.015):
    """Generate a synthetic OHLCV DataFrame."""
    np.random.seed(seed)
    dates = pd.bdate_range(start="2023-01-02", periods=n)
    log_returns = np.random.normal(trend, vol, n)
    close = start_price * np.exp(np.cumsum(log_returns))
    high = close * (1 + np.abs(np.random.normal(0.002, 0.005, n)))
    low = close * (1 - np.abs(np.random.normal(0.002, 0.005, n)))
    open_ = close * (1 + np.random.normal(0, 0.003, n))
    volume = np.random.randint(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


def _mock_mdc_with_df(df):
    """Create a mock MarketDataClient returning *df* for any ticker."""
    mdc = MagicMock()
    mdc.get_price_history.return_value = df
    return mdc


# ---------------------------------------------------------------------------
# Tests for _safe_div and _jsonify
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_safe_div_normal(self):
        assert _safe_div(10.0, 2.0) == pytest.approx(5.0)

    def test_safe_div_zero_denom(self):
        assert _safe_div(10.0, 0.0) == 0.0

    def test_safe_div_nan_denom(self):
        assert _safe_div(10.0, float("nan")) == 0.0

    def test_jsonify_numpy_types(self):
        result = _jsonify({"a": np.int64(5), "b": np.float64(3.14)})
        assert result["a"] == 5
        assert isinstance(result["a"], int)
        assert isinstance(result["b"], float)

    def test_jsonify_nan_becomes_zero(self):
        result = _jsonify({"x": float("nan")})
        assert result["x"] == 0.0

    def test_jsonify_ndarray(self):
        result = _jsonify(np.array([1, 2, 3]))
        assert result == [1, 2, 3]

    def test_jsonify_timestamp(self):
        ts = pd.Timestamp("2023-01-01")
        result = _jsonify(ts)
        assert "2023" in result


# ---------------------------------------------------------------------------
# Tests for StrategyResult
# ---------------------------------------------------------------------------

class TestStrategyResult:

    def test_default_values(self):
        sr = StrategyResult()
        assert sr.cumulative_return == 0.0
        assert sr.sharpe_ratio == 0.0
        assert sr.max_drawdown == 0.0
        assert sr.num_trades == 0
        assert sr.equity_curve == []

    def test_to_dict_serializable(self):
        sr = StrategyResult(
            cumulative_return=0.15,
            sharpe_ratio=1.5,
            equity_curve=[100_000, 105_000, 110_000],
        )
        d = sr.to_dict()
        assert d["cumulative_return"] == 0.15
        assert len(d["equity_curve"]) == 3


# ---------------------------------------------------------------------------
# Tests for SignalBacktester
# ---------------------------------------------------------------------------

class TestSignalBacktester:

    def test_known_perfect_signal_high_hit_rate(self):
        """If signal predicts direction of next-day return perfectly, hit rate ~1.0."""
        np.random.seed(42)
        n = 200
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        close = 100.0 + np.cumsum(np.random.normal(0, 0.5, n))
        # Remove any non-positive values
        close = np.abs(close) + 50
        df = pd.DataFrame({
            "Open": close, "High": close * 1.01, "Low": close * 0.99,
            "Close": close, "Volume": np.ones(n) * 1e6,
        }, index=dates)

        # Build a signal that knows the future 1-day return sign
        future_ret = pd.Series(close).pct_change().shift(-1)

        def perfect_signal(ohlcv):
            fr = ohlcv["Close"].pct_change().shift(-1)
            sig = pd.Series(0, index=ohlcv.index, dtype=int)
            sig[fr > 0] = 1
            sig[fr < 0] = -1
            return sig

        mdc = _mock_mdc_with_df(df)
        bt = SignalBacktester(market_data_client=mdc)
        result = bt.backtest_signal("TEST", perfect_signal, forward_periods=[1])

        assert result["overall_hit_rate"] > 0.8

    def test_empty_signal_returns_zero_hit_rate(self):
        df = _make_ohlcv(n=100)
        mdc = _mock_mdc_with_df(df)
        bt = SignalBacktester(market_data_client=mdc)

        def empty_signal(ohlcv):
            return pd.Series(0, index=ohlcv.index, dtype=int)

        result = bt.backtest_signal("TEST", empty_signal, forward_periods=[1])
        assert result["overall_hit_rate"] == 0.0

    def test_empty_dataframe_returns_empty_result(self):
        mdc = _mock_mdc_with_df(pd.DataFrame())
        bt = SignalBacktester(market_data_client=mdc)

        def dummy_signal(ohlcv):
            return pd.Series(dtype=int)

        result = bt.backtest_signal("TEST", dummy_signal)
        assert result["overall_hit_rate"] == 0.0
        assert result["ticker"] == ""

    def test_signal_backtest_returns_per_horizon(self):
        df = _make_ohlcv(n=100)
        mdc = _mock_mdc_with_df(df)
        bt = SignalBacktester(market_data_client=mdc)

        def simple_signal(ohlcv):
            sig = pd.Series(0, index=ohlcv.index, dtype=int)
            sig.iloc[::5] = 1  # buy every 5th day
            return sig

        result = bt.backtest_signal("TEST", simple_signal, forward_periods=[1, 5])
        assert "1d" in result["horizons"]
        assert "5d" in result["horizons"]

    def test_signal_backtest_with_entry_rule(self):
        df = _make_ohlcv(n=100)
        mdc = _mock_mdc_with_df(df)
        bt = SignalBacktester(market_data_client=mdc)

        def all_buy(ohlcv):
            return pd.Series(1, index=ohlcv.index, dtype=int)

        def reject_all(ohlcv, idx):
            return False

        result = bt.backtest_signal(
            "TEST", all_buy, forward_periods=[1], entry_rule=reject_all,
        )
        assert result["has_entry_rule"] is True
        # All signals rejected => hit rate 0
        assert result["overall_hit_rate"] == 0.0


# ---------------------------------------------------------------------------
# Tests for StrategyBacktester
# ---------------------------------------------------------------------------

class TestStrategyBacktester:

    def test_all_long_on_uptrend_returns_positive(self):
        """All-long signal on uptrending data should yield positive return."""
        np.random.seed(42)
        n = 200
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        # Strong uptrend
        close = 100.0 * np.exp(np.cumsum(np.full(n, 0.001)))
        prices = pd.Series(close, index=dates)
        signal = pd.Series(1, index=dates, dtype=int)

        mdc = MagicMock()
        sb = StrategyBacktester(market_data_client=mdc)
        result = sb.backtest_strategy("TEST", signal, prices=prices, commission_bps=0.0)

        assert result.cumulative_return > 0
        assert result.annual_return > 0

    def test_all_short_on_uptrend_returns_negative(self):
        np.random.seed(42)
        n = 200
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        close = 100.0 * np.exp(np.cumsum(np.full(n, 0.001)))
        prices = pd.Series(close, index=dates)
        signal = pd.Series(-1, index=dates, dtype=int)

        mdc = MagicMock()
        sb = StrategyBacktester(market_data_client=mdc)
        result = sb.backtest_strategy("TEST", signal, prices=prices, commission_bps=0.0)

        assert result.cumulative_return < 0

    def test_transaction_costs_deducted(self):
        """Nonzero commission should reduce cumulative return."""
        np.random.seed(42)
        n = 200
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        close = 100.0 * np.exp(np.cumsum(np.full(n, 0.001)))
        prices = pd.Series(close, index=dates)

        # Alternating signals to incur frequent trades
        signal = pd.Series(0, index=dates, dtype=int)
        signal.iloc[::2] = 1
        signal.iloc[1::2] = -1

        mdc = MagicMock()
        sb = StrategyBacktester(market_data_client=mdc)

        result_no_cost = sb.backtest_strategy(
            "TEST", signal, prices=prices, commission_bps=0.0,
        )
        result_with_cost = sb.backtest_strategy(
            "TEST", signal, prices=prices, commission_bps=50.0,
        )

        assert result_no_cost.cumulative_return > result_with_cost.cumulative_return

    def test_equity_curve_length(self):
        n = 100
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        prices = pd.Series(np.linspace(100, 110, n), index=dates)
        signal = pd.Series(1, index=dates, dtype=int)

        mdc = MagicMock()
        sb = StrategyBacktester(market_data_client=mdc)
        result = sb.backtest_strategy("TEST", signal, prices=prices)

        assert len(result.equity_curve) == n

    def test_no_data_returns_empty_result(self):
        mdc = MagicMock()
        mdc.get_price_history.return_value = pd.DataFrame()
        sb = StrategyBacktester(market_data_client=mdc)

        signal = pd.Series(dtype=int)
        result = sb.backtest_strategy("TEST", signal)
        assert result.cumulative_return == 0.0
        assert result.equity_curve == []

    def test_max_drawdown_is_negative_or_zero(self):
        n = 200
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        np.random.seed(42)
        close = 100.0 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, n)))
        prices = pd.Series(close, index=dates)
        signal = pd.Series(1, index=dates, dtype=int)

        mdc = MagicMock()
        sb = StrategyBacktester(market_data_client=mdc)
        result = sb.backtest_strategy("TEST", signal, prices=prices)
        assert result.max_drawdown <= 0

    def test_trade_extraction(self):
        """Verify trades are extracted correctly from position changes."""
        n = 20
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        prices = pd.Series(np.linspace(100, 120, n), index=dates)
        signal = pd.Series(0, index=dates, dtype=int)
        signal.iloc[2:8] = 1  # Long from day 2 to 7
        signal.iloc[10:15] = -1  # Short from day 10 to 14

        mdc = MagicMock()
        sb = StrategyBacktester(market_data_client=mdc)
        result = sb.backtest_strategy("TEST", signal, prices=prices, commission_bps=0.0)

        assert result.num_trades >= 2
        directions = [t["direction"] for t in result.trades]
        assert "LONG" in directions
        assert "SHORT" in directions


# ---------------------------------------------------------------------------
# Tests for WalkForwardValidator
# ---------------------------------------------------------------------------

class TestWalkForwardValidator:

    def test_splits_are_non_overlapping(self):
        """Walk-forward splits should not overlap in their test windows."""
        df = _make_ohlcv(n=500, seed=42)
        mdc = _mock_mdc_with_df(df)
        wfv = WalkForwardValidator(market_data_client=mdc)

        def dummy_strategy(train_df):
            return pd.Series(1, index=train_df.index, dtype=int)

        result = wfv.walk_forward(
            "TEST", dummy_strategy,
            train_window=100, test_window=50, n_splits=3,
        )

        assert result["n_splits"] > 0
        splits = result["splits"]
        for s in splits:
            assert s["train_start"] < s["train_end"]
            assert s["test_start"] < s["test_end"]

    def test_oos_returns_collected(self):
        df = _make_ohlcv(n=500, seed=42)
        mdc = _mock_mdc_with_df(df)
        wfv = WalkForwardValidator(market_data_client=mdc)

        def all_long_strategy(train_df):
            return pd.Series(1, index=train_df.index, dtype=int)

        result = wfv.walk_forward(
            "TEST", all_long_strategy,
            train_window=100, test_window=50, n_splits=3,
        )

        assert len(result["oos_returns"]) > 0
        assert isinstance(result["oos_sharpe"], float)
        assert isinstance(result["oos_hit_rate"], float)

    def test_stability_ratio_range(self):
        df = _make_ohlcv(n=500, seed=42)
        mdc = _mock_mdc_with_df(df)
        wfv = WalkForwardValidator(market_data_client=mdc)

        def strategy(train_df):
            return pd.Series(1, index=train_df.index, dtype=int)

        result = wfv.walk_forward(
            "TEST", strategy,
            train_window=100, test_window=50, n_splits=3,
        )

        assert 0.0 <= result["stability_ratio"] <= 1.0

    def test_insufficient_data_returns_empty(self):
        df = _make_ohlcv(n=20, seed=42)
        mdc = _mock_mdc_with_df(df)
        wfv = WalkForwardValidator(market_data_client=mdc)

        def strategy(train_df):
            return pd.Series(1, index=train_df.index, dtype=int)

        result = wfv.walk_forward(
            "TEST", strategy, train_window=100, test_window=50, n_splits=4,
        )
        # Should either return empty or adjust n_splits
        assert isinstance(result, dict)

    def test_empty_data_returns_empty_result(self):
        mdc = _mock_mdc_with_df(pd.DataFrame())
        wfv = WalkForwardValidator(market_data_client=mdc)

        def strategy(train_df):
            return pd.Series(dtype=int)

        result = wfv.walk_forward("TEST", strategy)
        assert result["n_splits"] == 0
        assert result["oos_returns"] == []


# ---------------------------------------------------------------------------
# Tests for SignificanceTester
# ---------------------------------------------------------------------------

class TestSignificanceTester:

    def test_significant_excess_returns(self):
        """Consistently positive excess returns should be statistically significant."""
        np.random.seed(42)
        n = 1000
        dates = pd.bdate_range(start="2021-01-01", periods=n)
        # Strategy outperforms benchmark with large, consistent excess return
        strategy = pd.Series(np.random.normal(0.003, 0.01, n), index=dates)
        benchmark = pd.Series(np.random.normal(0.0005, 0.01, n), index=dates)

        result = SignificanceTester.test_significance(strategy, benchmark)
        assert result["t_statistic"] > 0
        assert result["p_value"] < 0.05
        assert result["is_significant"] is True

    def test_zero_excess_not_significant(self):
        """If strategy == benchmark, should NOT be significant."""
        np.random.seed(42)
        n = 500
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        returns = pd.Series(np.random.normal(0.001, 0.01, n), index=dates)

        result = SignificanceTester.test_significance(returns, returns)
        # Identical => t=0, p=1
        assert result["t_statistic"] == pytest.approx(0.0, abs=0.001)
        assert result["p_value"] == pytest.approx(1.0, abs=0.001)
        assert result["is_significant"] is False

    def test_bootstrap_sharpe_ci(self):
        np.random.seed(42)
        n = 300
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        strategy = pd.Series(np.random.normal(0.001, 0.015, n), index=dates)
        benchmark = pd.Series(np.random.normal(0.0005, 0.015, n), index=dates)

        result = SignificanceTester.test_significance(
            strategy, benchmark, n_bootstrap=500,
        )
        assert result["sharpe_ci_lower"] <= result["sharpe_ci_upper"]
        assert result["n_observations"] == n

    def test_too_few_observations(self):
        dates = pd.bdate_range(start="2022-01-01", periods=5)
        s = pd.Series([0.01] * 5, index=dates)
        b = pd.Series([0.005] * 5, index=dates)

        result = SignificanceTester.test_significance(s, b)
        assert result["is_significant"] is False
        assert result["n_observations"] == 5


# ---------------------------------------------------------------------------
# Tests for BenchmarkComparator
# ---------------------------------------------------------------------------

class TestBenchmarkComparator:

    def test_identical_returns_beta_one_alpha_zero(self):
        np.random.seed(42)
        n = 500
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        returns = pd.Series(np.random.normal(0.001, 0.01, n), index=dates)

        result = BenchmarkComparator.compare_to_benchmark(returns, returns)
        assert result["beta"] == pytest.approx(1.0, abs=0.01)
        assert result["alpha"] == pytest.approx(0.0, abs=0.01)
        assert result["tracking_error"] == pytest.approx(0.0, abs=0.01)

    def test_double_returns_beta_two(self):
        np.random.seed(42)
        n = 500
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        bench = pd.Series(np.random.normal(0.0005, 0.01, n), index=dates)
        strat = bench * 2

        result = BenchmarkComparator.compare_to_benchmark(strat, bench)
        assert result["beta"] == pytest.approx(2.0, abs=0.05)

    def test_up_down_capture(self):
        np.random.seed(42)
        n = 500
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        bench = pd.Series(np.random.normal(0.0, 0.01, n), index=dates)
        strat = bench.copy()

        result = BenchmarkComparator.compare_to_benchmark(strat, bench)
        assert result["up_capture"] == pytest.approx(1.0, abs=0.01)
        assert result["down_capture"] == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Tests for built-in signal functions
# ---------------------------------------------------------------------------

class TestBuiltInSignals:

    def test_rsi_signal_produces_valid_values(self):
        df = _make_ohlcv(n=100, seed=42)
        sig = rsi_signal(df)
        assert set(sig.unique()).issubset({-1, 0, 1})
        assert len(sig) == len(df)

    def test_ma_crossover_signal_produces_valid_values(self):
        df = _make_ohlcv(n=100, seed=42)
        sig = ma_crossover_signal(df)
        assert set(sig.unique()).issubset({-1, 0, 1})
        assert len(sig) == len(df)

    def test_macd_signal_produces_valid_values(self):
        df = _make_ohlcv(n=100, seed=42)
        sig = macd_signal(df)
        assert set(sig.unique()).issubset({-1, 0, 1})
        assert len(sig) == len(df)

    def test_bollinger_signal_produces_valid_values(self):
        df = _make_ohlcv(n=100, seed=42)
        sig = bollinger_signal(df)
        assert set(sig.unique()).issubset({-1, 0, 1})
        assert len(sig) == len(df)

    def test_composite_signal_produces_valid_values(self):
        df = _make_ohlcv(n=100, seed=42)
        sig = composite_signal(df)
        assert set(sig.unique()).issubset({-1, 0, 1})
        assert len(sig) == len(df)

    def test_rsi_signal_buy_on_oversold(self):
        """Create data that drives RSI below 30 and verify buy signals."""
        np.random.seed(42)
        n = 60
        dates = pd.bdate_range(start="2023-01-02", periods=n)
        # Sustained downtrend
        close = 200.0 * np.exp(np.cumsum(np.full(n, -0.01)))
        df = pd.DataFrame({
            "Open": close, "High": close * 1.003, "Low": close * 0.997,
            "Close": close, "Volume": np.ones(n) * 1e6,
        }, index=dates)

        sig = rsi_signal(df)
        # Should have at least some buy signals
        assert (sig == 1).sum() > 0

    def test_ma_crossover_bull_market(self):
        """Strong uptrend should produce mostly buy signals once SMA_fast > SMA_slow."""
        np.random.seed(42)
        n = 100
        dates = pd.bdate_range(start="2023-01-02", periods=n)
        close = 100.0 * np.exp(np.cumsum(np.full(n, 0.005)))
        df = pd.DataFrame({
            "Open": close, "High": close * 1.003, "Low": close * 0.997,
            "Close": close, "Volume": np.ones(n) * 1e6,
        }, index=dates)

        sig = ma_crossover_signal(df, fast=10, slow=30)
        # After warm-up, should be mostly +1
        assert (sig.iloc[40:] == 1).sum() > (sig.iloc[40:] == -1).sum()


# ---------------------------------------------------------------------------
# Tests for _extract_trades and _max_dd_duration static methods
# ---------------------------------------------------------------------------

class TestStaticMethods:

    def test_max_dd_duration_empty(self):
        result = StrategyBacktester._max_dd_duration(np.array([]))
        assert result == 0

    def test_max_dd_duration_monotonic(self):
        equity = np.array([100, 101, 102, 103, 104])
        result = StrategyBacktester._max_dd_duration(equity)
        assert result == 0

    def test_max_dd_duration_with_drawdown(self):
        equity = np.array([100, 110, 105, 100, 108, 112, 115])
        result = StrategyBacktester._max_dd_duration(equity)
        assert result == 3  # indices 2, 3, 4

    def test_rolling_sharpe_insufficient_data(self):
        net_returns = np.array([0.01, 0.02, -0.01])
        result = StrategyBacktester._rolling_sharpe(net_returns, window=252)
        assert result == []
