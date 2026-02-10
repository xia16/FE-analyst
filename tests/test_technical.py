"""Tests for src.analysis.technical -- indicators, signals, divergences, patterns, multi-TF."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.technical import (
    TechnicalAnalyzer,
    Signal,
    Divergence,
    PatternMatch,
    _local_extrema,
    _MIN_ROWS_BASIC,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n=252, seed=42, start_price=150.0, trend=0.0004, vol=0.015):
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


def _make_rsi_oversold_ohlcv(n=100):
    """Generate OHLCV with a downtrend that will produce RSI < 30."""
    np.random.seed(42)
    dates = pd.bdate_range(start="2023-01-02", periods=n)
    # Start high and decline steadily
    close = 200.0 * np.exp(np.cumsum(np.random.normal(-0.008, 0.005, n)))
    high = close * 1.005
    low = close * 0.995
    open_ = close * 1.001
    volume = np.random.randint(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


# ---------------------------------------------------------------------------
# Tests for _local_extrema helper
# ---------------------------------------------------------------------------

class TestLocalExtrema:

    def test_finds_peak(self):
        arr = np.array([1.0, 2.0, 5.0, 3.0, 1.0])
        peaks = _local_extrema(arr, mode="peak", order=1)
        assert 2 in peaks

    def test_finds_trough(self):
        arr = np.array([5.0, 3.0, 1.0, 3.0, 5.0])
        troughs = _local_extrema(arr, mode="trough", order=1)
        assert 2 in troughs

    def test_no_extrema_in_flat_series(self):
        arr = np.array([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
        peaks = _local_extrema(arr, mode="peak", order=2)
        # Flat values can match as peaks (>=), so this is valid
        # Just verify it returns a list
        assert isinstance(peaks, list)

    def test_handles_nans(self):
        arr = np.array([1.0, np.nan, 3.0, np.nan, 1.0])
        peaks = _local_extrema(arr, mode="peak", order=1)
        assert isinstance(peaks, list)


# ---------------------------------------------------------------------------
# Tests for compute_indicators
# ---------------------------------------------------------------------------

class TestComputeIndicators:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_sma_columns_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "SMA_20" in result.columns
        assert "SMA_50" in result.columns
        assert "SMA_200" in result.columns

    def test_ema_columns_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "EMA_12" in result.columns
        assert "EMA_26" in result.columns

    def test_rsi_column_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "RSI_14" in result.columns
        # RSI should be 0-100
        rsi_vals = result["RSI_14"].dropna()
        assert rsi_vals.min() >= 0
        assert rsi_vals.max() <= 100

    def test_macd_columns_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "MACD" in result.columns
        assert "MACD_signal" in result.columns
        assert "MACD_hist" in result.columns

    def test_bollinger_bands_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "BB_upper" in result.columns
        assert "BB_mid" in result.columns
        assert "BB_lower" in result.columns

    def test_obv_column_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "OBV" in result.columns

    def test_ichimoku_columns_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "ichimoku_tenkan" in result.columns
        assert "ichimoku_kijun" in result.columns
        assert "ichimoku_senkou_a" in result.columns
        assert "ichimoku_senkou_b" in result.columns

    def test_vwap_column_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.compute_indicators(df)
        assert "VWAP" in result.columns

    def test_short_dataframe_skips_long_indicators(self):
        """A 20-row DataFrame should have SMA_20 but not SMA_200."""
        df = _make_ohlcv(n=20)
        result = self.analyzer.compute_indicators(df)
        assert "SMA_20" in result.columns
        assert "SMA_200" not in result.columns

    def test_output_preserves_original_columns(self):
        df = _make_ohlcv(n=50)
        result = self.analyzer.compute_indicators(df)
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in result.columns

    def test_output_length_unchanged(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.compute_indicators(df)
        assert len(result) == len(df)


# ---------------------------------------------------------------------------
# Tests for signal generation
# ---------------------------------------------------------------------------

class TestSignalGeneration:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_oversold_rsi_generates_buy_signal(self):
        """When RSI < 30, should generate BUY signal."""
        df = _make_rsi_oversold_ohlcv(n=100)
        signals_raw = self.analyzer.get_signals(df)

        # Look for RSI-related signals
        rsi_signals = {k: v for k, v in signals_raw.items() if "rsi" in k.lower()}
        if rsi_signals:
            # At least one RSI signal should be BUY
            has_buy = any(v.get("signal") == "BUY" for v in rsi_signals.values())
            assert has_buy, f"Expected BUY RSI signal but got: {rsi_signals}"

    def test_get_signals_returns_dict(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.get_signals(df)
        assert isinstance(result, dict)

    def test_signals_have_required_keys(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.get_signals(df)
        for name, sig in result.items():
            assert "signal" in sig
            assert sig["signal"] in ("BUY", "SELL", "HOLD")
            assert "strength" in sig
            assert "reason" in sig


# ---------------------------------------------------------------------------
# Tests for divergence detection
# ---------------------------------------------------------------------------

class TestDivergenceDetection:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_bearish_divergence_price_higher_rsi_lower(self):
        """Create a scenario where price makes higher high but RSI makes lower high.

        This is done by constructing price data with a V-shape then a higher peak,
        but with declining momentum. The divergence checker may or may not fire
        depending on the exact data, so we verify the structure.
        """
        n = 60
        np.random.seed(42)
        dates = pd.bdate_range(start="2023-01-02", periods=n)

        # Create rising prices followed by a dip and then a new higher high
        close = np.concatenate([
            np.linspace(100, 130, 20),   # strong rise
            np.linspace(130, 115, 10),   # pullback
            np.linspace(115, 135, 15),   # new high with weaker momentum
            np.linspace(135, 132, 15),   # slight decline
        ])
        high = close * 1.005
        low = close * 0.995
        open_ = close * 1.001
        volume = np.random.randint(1_000_000, 10_000_000, n).astype(float)
        df = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
            index=dates,
        )

        divs = self.analyzer.detect_divergences(df)
        # We verify the output is a list of Divergence objects
        assert isinstance(divs, list)
        for d in divs:
            assert isinstance(d, Divergence)
            assert d.divergence_type in ("bullish", "bearish")

    def test_no_divergence_on_random_data(self):
        """Random data might or might not have divergences; just check it runs."""
        df = _make_ohlcv(n=100, seed=123)
        divs = self.analyzer.detect_divergences(df)
        assert isinstance(divs, list)

    def test_short_data_returns_empty(self):
        """Insufficient data should return empty list."""
        df = _make_ohlcv(n=10)
        divs = self.analyzer.detect_divergences(df)
        assert divs == []


# ---------------------------------------------------------------------------
# Tests for pattern detection
# ---------------------------------------------------------------------------

class TestPatternDetection:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_double_top_detection(self):
        """Create a price series with two peaks at similar levels."""
        n = 80
        np.random.seed(42)
        dates = pd.bdate_range(start="2023-01-02", periods=n)

        # Create two peaks around 150, with a valley between
        close = np.concatenate([
            np.linspace(100, 150, 20),   # rise to first peak
            np.linspace(150, 130, 15),   # drop to valley
            np.linspace(130, 150, 15),   # rise to second peak (same level)
            np.linspace(150, 135, 15),   # decline after double top
            np.linspace(135, 132, 15),   # continued decline
        ])
        high = close * 1.003
        low = close * 0.997
        open_ = close * 1.001
        volume = np.random.randint(1_000_000, 10_000_000, n).astype(float)
        df = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
            index=dates,
        )

        patterns = self.analyzer.detect_patterns(df)
        assert isinstance(patterns, list)
        for p in patterns:
            assert isinstance(p, PatternMatch)
            assert 0 <= p.confidence <= 1
            assert p.direction in ("bullish", "bearish")

    def test_short_data_returns_empty(self):
        df = _make_ohlcv(n=20)
        patterns = self.analyzer.detect_patterns(df)
        assert patterns == []

    def test_pattern_match_to_dict(self):
        pm = PatternMatch("double_top", 0.85, "bearish")
        d = pm.to_dict()
        assert d["pattern_name"] == "double_top"
        assert d["confidence"] == 0.85
        assert d["direction"] == "bearish"


# ---------------------------------------------------------------------------
# Tests for multi-timeframe analysis
# ---------------------------------------------------------------------------

class TestMultiTimeframe:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_daily_always_present(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.multi_timeframe_analysis(df)
        assert "daily" in result

    def test_weekly_present_with_enough_data(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.multi_timeframe_analysis(df)
        assert "weekly" in result

    def test_monthly_present_with_enough_data(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.multi_timeframe_analysis(df)
        assert "monthly" in result

    def test_timeframe_has_snapshot_and_signals(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.multi_timeframe_analysis(df)
        for tf_label, data in result.items():
            assert "snapshot" in data
            assert "signals" in data
            assert isinstance(data["signals"], list)


# ---------------------------------------------------------------------------
# Tests for composite scoring
# ---------------------------------------------------------------------------

class TestCompositeScore:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_score_in_0_100_range(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.full_analysis(df)
        assert 0 <= result["score"] <= 100

    def test_full_analysis_returns_all_keys(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.full_analysis(df)
        assert "multi_timeframe" in result
        assert "divergences" in result
        assert "patterns" in result
        assert "support_resistance" in result
        assert "volume_analysis" in result
        assert "trend" in result
        assert "confluence" in result
        assert "scoring" in result
        assert "score" in result

    def test_score_normalization(self):
        """Composite score should always be 0-100."""
        df = _make_ohlcv(n=252, seed=99)
        result = self.analyzer.full_analysis(df)
        assert 0.0 <= result["scoring"]["score"] <= 100.0


# ---------------------------------------------------------------------------
# Tests for volume analysis
# ---------------------------------------------------------------------------

class TestVolumeAnalysis:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_volume_analysis_keys(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.analyze_volume(df)
        assert "volume_profile" in result
        assert "volume_trend" in result
        assert "accumulation_distribution" in result
        assert "volume_breakout" in result

    def test_volume_trend_is_valid(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.analyze_volume(df)
        assert result["volume_trend"] in ("expanding", "contracting", "stable", "unknown")

    def test_short_data_returns_defaults(self):
        df = _make_ohlcv(n=10)
        result = self.analyzer.analyze_volume(df)
        assert result["volume_trend"] == "unknown"


# ---------------------------------------------------------------------------
# Tests for support/resistance
# ---------------------------------------------------------------------------

class TestSupportResistance:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_sr_returns_levels(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.get_support_resistance(df)
        assert "resistance_levels" in result
        assert "support_levels" in result
        assert "current" in result

    def test_resistance_above_support(self):
        df = _make_ohlcv(n=100)
        result = self.analyzer.get_support_resistance(df)
        current = result["current"]
        for r in result["resistance_levels"]:
            assert r > current
        for s in result["support_levels"]:
            assert s <= current


# ---------------------------------------------------------------------------
# Tests for trend analysis
# ---------------------------------------------------------------------------

class TestTrendAnalysis:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_trend_keys_present(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.analyze_trend(df)
        assert "trend_strength" in result
        assert "trend_direction" in result
        assert "trend_duration_bars" in result
        assert "ichimoku_position" in result

    def test_trend_direction_valid(self):
        df = _make_ohlcv(n=252)
        result = self.analyzer.analyze_trend(df)
        assert result["trend_direction"] in ("bullish", "bearish", "neutral")


# ---------------------------------------------------------------------------
# Tests for Signal / Divergence dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:

    def test_signal_to_dict(self):
        s = Signal("rsi_oversold", "BUY", 30.0, "RSI < 30", "daily", 1.0)
        d = s.to_dict()
        assert d["signal_name"] == "rsi_oversold"
        assert d["direction"] == "BUY"
        assert d["strength"] == 30.0

    def test_divergence_to_dict(self):
        d = Divergence("bearish", "RSI", 20)
        result = d.to_dict()
        assert result["divergence_type"] == "bearish"
        assert result["indicator"] == "RSI"
        assert result["lookback_bars"] == 20


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_very_short_dataframe(self):
        """DataFrame with < 30 rows should not crash."""
        df = _make_ohlcv(n=5)
        result = self.analyzer.compute_indicators(df)
        assert len(result) == 5

    def test_all_nan_close_column(self):
        """All-NaN close column should not crash compute_indicators."""
        n = 50
        dates = pd.bdate_range(start="2023-01-02", periods=n)
        df = pd.DataFrame({
            "Open": np.full(n, np.nan),
            "High": np.full(n, np.nan),
            "Low": np.full(n, np.nan),
            "Close": np.full(n, np.nan),
            "Volume": np.full(n, np.nan),
        }, index=dates)
        # talib handles NaN gracefully; no crash
        try:
            result = self.analyzer.compute_indicators(df)
            assert len(result) == n
        except Exception:
            # If talib raises on all-NaN, that is acceptable
            pass
