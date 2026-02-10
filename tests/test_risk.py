"""Tests for src.analysis.risk -- volatility, Sharpe, drawdown, beta, VaR, tail risk, classification."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from src.analysis.risk import (
    RiskAnalyzer,
    _round,
    TRADING_DAYS,
    HISTORICAL_SCENARIOS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_return_series(mean=0.0004, std=0.015, n=252, seed=42):
    """Generate a return series with known parameters."""
    np.random.seed(seed)
    dates = pd.bdate_range(start="2023-01-02", periods=n)
    returns = np.random.normal(mean, std, n)
    return pd.Series(returns, index=dates, name="returns")


def _make_price_series(start=100.0, mean=0.0004, std=0.015, n=252, seed=42):
    """Generate a price series from returns."""
    np.random.seed(seed)
    returns = np.random.normal(mean, std, n)
    dates = pd.bdate_range(start="2023-01-02", periods=n)
    prices = start * np.exp(np.cumsum(returns))
    return pd.Series(prices, index=dates, name="Close")


# ---------------------------------------------------------------------------
# Tests for _round helper
# ---------------------------------------------------------------------------

class TestRoundHelper:

    def test_round_normal_value(self):
        assert _round(3.14159, 2) == 3.14

    def test_round_nan_returns_zero(self):
        assert _round(float("nan")) == 0.0

    def test_round_inf_returns_zero(self):
        assert _round(float("inf")) == 0.0
        assert _round(float("-inf")) == 0.0


# ---------------------------------------------------------------------------
# Tests for volatility
# ---------------------------------------------------------------------------

class TestVolatility:

    def test_annualized_volatility_known_series(self):
        """Known daily std * sqrt(252) should equal annualized vol."""
        np.random.seed(42)
        n = 1000
        daily_std = 0.015
        returns = pd.Series(np.random.normal(0, daily_std, n))

        vol = RiskAnalyzer._annualized_volatility(returns)
        expected = returns.std() * np.sqrt(TRADING_DAYS)
        assert vol == pytest.approx(expected, rel=0.01)

    def test_zero_volatility_for_constant_returns(self):
        returns = pd.Series([0.01] * 100)
        vol = RiskAnalyzer._annualized_volatility(returns)
        assert vol == pytest.approx(0.0, abs=0.001)


# ---------------------------------------------------------------------------
# Tests for Sharpe ratio
# ---------------------------------------------------------------------------

class TestSharpeRatio:

    def test_sharpe_ratio_with_known_inputs(self):
        """Sharpe = (mean(excess) / std(excess)) * sqrt(252)."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.015, 500))
        rf_daily = 0.04 / 252

        sharpe = RiskAnalyzer._sharpe_ratio(returns, rf_daily)

        excess = returns - rf_daily
        expected = float(excess.mean()) / float(excess.std()) * np.sqrt(TRADING_DAYS)
        assert sharpe == pytest.approx(expected, rel=0.01)

    def test_sharpe_zero_for_zero_std(self):
        returns = pd.Series([0.0001] * 100)
        rf = 0.0001
        sharpe = RiskAnalyzer._sharpe_ratio(returns, rf)
        assert sharpe == 0.0


# ---------------------------------------------------------------------------
# Tests for max drawdown
# ---------------------------------------------------------------------------

class TestMaxDrawdown:

    def test_max_drawdown_known_series(self):
        """Construct a series: 100, 110, 90, 105 => max drawdown from 110 to 90."""
        prices = pd.Series([100.0, 110.0, 90.0, 105.0])
        dd = RiskAnalyzer._max_drawdown(prices)
        # Drawdown from 110 to 90 = (90 - 110) / 110 = -0.18182
        assert dd == pytest.approx(-0.1818, abs=0.001)

    def test_max_drawdown_monotonic_increasing(self):
        """A monotonically increasing price series should have 0 drawdown."""
        prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
        dd = RiskAnalyzer._max_drawdown(prices)
        assert dd == pytest.approx(0.0, abs=0.001)

    def test_max_drawdown_deep_drop(self):
        """50% drawdown: peak 200, trough 100."""
        prices = pd.Series([100.0, 200.0, 100.0, 150.0])
        dd = RiskAnalyzer._max_drawdown(prices)
        assert dd == pytest.approx(-0.5, abs=0.001)


# ---------------------------------------------------------------------------
# Tests for max drawdown duration
# ---------------------------------------------------------------------------

class TestMaxDrawdownDuration:

    def test_no_drawdown_returns_zero(self):
        prices = pd.Series([100.0, 101.0, 102.0, 103.0])
        assert RiskAnalyzer._max_drawdown_duration(prices) == 0

    def test_known_drawdown_duration(self):
        # Peak at 110, then 3 days in drawdown before recovery
        prices = pd.Series([100.0, 110.0, 105.0, 100.0, 108.0, 111.0])
        duration = RiskAnalyzer._max_drawdown_duration(prices)
        assert duration == 3  # bars 2, 3, 4 are in drawdown


# ---------------------------------------------------------------------------
# Tests for beta
# ---------------------------------------------------------------------------

class TestBeta:

    def test_perfectly_correlated_series_beta_one(self):
        """If stock returns == benchmark returns, beta should be ~1.0."""
        np.random.seed(42)
        bench = pd.Series(np.random.normal(0, 0.01, 200))
        stock = bench.copy()
        beta = RiskAnalyzer._beta(stock, bench)
        assert beta == pytest.approx(1.0, abs=0.01)

    def test_double_beta(self):
        """If stock returns = 2 * benchmark returns, beta should be ~2.0."""
        np.random.seed(42)
        bench = pd.Series(np.random.normal(0, 0.01, 200))
        stock = bench * 2
        beta = RiskAnalyzer._beta(stock, bench)
        assert beta == pytest.approx(2.0, abs=0.05)

    def test_uncorrelated_series_beta_near_zero(self):
        """Independent random series should have beta near 0."""
        np.random.seed(42)
        bench = pd.Series(np.random.normal(0, 0.01, 5000))
        np.random.seed(99)
        stock = pd.Series(np.random.normal(0, 0.01, 5000))
        beta = RiskAnalyzer._beta(stock, bench)
        assert abs(beta) < 0.1

    def test_empty_benchmark_returns_zero(self):
        stock = pd.Series([0.01, 0.02])
        bench = pd.Series(dtype=float)
        beta = RiskAnalyzer._beta(stock, bench)
        assert beta == 0.0


# ---------------------------------------------------------------------------
# Tests for VaR
# ---------------------------------------------------------------------------

class TestVaR:

    def test_var_95_known_normal(self):
        """For large N(0, sigma), VaR at 95% ~ -1.645 * sigma."""
        np.random.seed(42)
        sigma = 0.02
        returns = pd.Series(np.random.normal(0, sigma, 100000))
        var_95 = RiskAnalyzer._value_at_risk(returns, 0.95)
        expected = -1.645 * sigma
        assert var_95 == pytest.approx(expected, abs=0.001)

    def test_var_99_is_more_extreme_than_var_95(self):
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 10000))
        var_95 = RiskAnalyzer._value_at_risk(returns, 0.95)
        var_99 = RiskAnalyzer._value_at_risk(returns, 0.99)
        assert var_99 < var_95  # more extreme = more negative


# ---------------------------------------------------------------------------
# Tests for CVaR
# ---------------------------------------------------------------------------

class TestCVaR:

    def test_cvar_more_extreme_than_var(self):
        """CVaR (expected shortfall) should be at least as extreme as VaR."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 10000))
        var_95 = RiskAnalyzer._value_at_risk(returns, 0.95)
        cvar_95 = RiskAnalyzer._conditional_var(returns, 0.95)
        assert cvar_95 <= var_95


# ---------------------------------------------------------------------------
# Tests for tail risk metrics
# ---------------------------------------------------------------------------

class TestTailRisk:

    def test_skewness_calculation(self):
        """Normal distribution should have skewness near 0."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 10000))
        result = RiskAnalyzer._tail_risk_metrics(returns)
        assert abs(result["skewness"]) < 0.1

    def test_kurtosis_calculation(self):
        """Normal distribution should have excess kurtosis near 0."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 10000))
        result = RiskAnalyzer._tail_risk_metrics(returns)
        assert abs(result["excess_kurtosis"]) < 0.2

    def test_tail_risk_keys(self):
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 500))
        result = RiskAnalyzer._tail_risk_metrics(returns)
        assert "skewness" in result
        assert "excess_kurtosis" in result
        assert "jarque_bera_statistic" in result
        assert "tail_ratio" in result
        assert "gain_to_pain_ratio" in result

    def test_fat_tailed_distribution_has_positive_kurtosis(self):
        """Student-t with low df should show positive excess kurtosis."""
        np.random.seed(42)
        from scipy.stats import t as t_dist
        returns = pd.Series(t_dist.rvs(df=3, size=10000))
        result = RiskAnalyzer._tail_risk_metrics(returns)
        assert result["excess_kurtosis"] > 1.0


# ---------------------------------------------------------------------------
# Tests for tracking error
# ---------------------------------------------------------------------------

class TestTrackingError:

    def test_tracking_error_identical_returns_is_zero(self):
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.01, 200))
        te = RiskAnalyzer._tracking_error(returns, returns)
        assert te == pytest.approx(0.0, abs=0.001)

    def test_tracking_error_different_returns_positive(self):
        np.random.seed(42)
        stock = pd.Series(np.random.normal(0, 0.02, 200))
        np.random.seed(99)
        bench = pd.Series(np.random.normal(0, 0.01, 200))
        te = RiskAnalyzer._tracking_error(stock, bench)
        assert te > 0


# ---------------------------------------------------------------------------
# Tests for risk classification
# ---------------------------------------------------------------------------

class TestRiskClassification:

    def test_conservative_classification(self):
        """Low volatility, low drawdown, good Sharpe => CONSERVATIVE."""
        result_dict = {
            "basic_metrics": {
                "annualized_volatility": 0.08,
                "max_drawdown": -0.05,
                "beta": 0.5,
                "sharpe_ratio": 2.0,
            },
            "tail_risk": {
                "skewness": 0.0,
                "excess_kurtosis": 0.0,
            },
            "factor_model": {},
            "rolling_risk": {"regime_shift_detected": False},
        }
        classification = RiskAnalyzer._risk_classification(result_dict)
        assert classification["risk_score"] >= 75
        assert classification["risk_tier"] == "CONSERVATIVE"

    def test_speculative_classification(self):
        """High volatility, deep drawdown, high beta => SPECULATIVE."""
        result_dict = {
            "basic_metrics": {
                "annualized_volatility": 0.65,
                "max_drawdown": -0.55,
                "beta": 2.5,
                "sharpe_ratio": -0.5,
            },
            "tail_risk": {
                "skewness": -1.5,
                "excess_kurtosis": 5.0,
            },
            "factor_model": {},
            "rolling_risk": {"regime_shift_detected": True},
        }
        classification = RiskAnalyzer._risk_classification(result_dict)
        assert classification["risk_score"] < 25
        assert classification["risk_tier"] == "SPECULATIVE"

    def test_score_always_in_0_100(self):
        """Classification score should be clamped to [0, 100]."""
        result_dict = {
            "basic_metrics": {
                "annualized_volatility": 0.20,
                "max_drawdown": -0.15,
                "beta": 1.0,
                "sharpe_ratio": 1.0,
            },
            "tail_risk": {"skewness": 0.0, "excess_kurtosis": 0.0},
            "factor_model": {},
            "rolling_risk": {"regime_shift_detected": False},
        }
        classification = RiskAnalyzer._risk_classification(result_dict)
        assert 0 <= classification["risk_score"] <= 100

    def test_risk_flags_populated(self):
        result_dict = {
            "basic_metrics": {
                "annualized_volatility": 0.50,
                "max_drawdown": -0.35,
                "beta": 1.8,
                "sharpe_ratio": 0.2,
            },
            "tail_risk": {"skewness": -0.8, "excess_kurtosis": 4.0},
            "factor_model": {},
            "rolling_risk": {"regime_shift_detected": False},
        }
        classification = RiskAnalyzer._risk_classification(result_dict)
        assert "high_volatility" in classification["risk_flags"]
        assert "severe_drawdown" in classification["risk_flags"]
        assert "high_beta" in classification["risk_flags"]


# ---------------------------------------------------------------------------
# Tests for stress testing
# ---------------------------------------------------------------------------

class TestStressTesting:

    def test_stress_scenario_loss_calculation(self):
        """Estimated loss = scenario drawdown * beta."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.015, 252))
        beta = 1.5

        result = RiskAnalyzer._stress_testing(returns, beta)

        for name, params in HISTORICAL_SCENARIOS.items():
            expected_loss = _round(params["drawdown"] * beta)
            assert result["historical_scenarios"][name]["estimated_portfolio_loss"] == pytest.approx(
                expected_loss, abs=0.001
            )

    def test_sigma_moves(self):
        """Verify 2-sigma and 3-sigma daily loss calculations."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 252))
        daily_vol = float(returns.std())

        result = RiskAnalyzer._stress_testing(returns, beta=1.0)
        assert result["sigma_moves"]["2_sigma_daily_loss"] == pytest.approx(
            -2.0 * daily_vol, abs=0.001
        )
        assert result["sigma_moves"]["3_sigma_daily_loss"] == pytest.approx(
            -3.0 * daily_vol, abs=0.001
        )

    def test_all_scenarios_present(self):
        returns = pd.Series(np.random.normal(0, 0.015, 100))
        result = RiskAnalyzer._stress_testing(returns, beta=1.0)
        for name in HISTORICAL_SCENARIOS:
            assert name in result["historical_scenarios"]


# ---------------------------------------------------------------------------
# Tests for sortino ratio
# ---------------------------------------------------------------------------

class TestSortinoRatio:

    def test_sortino_ratio_positive_returns(self):
        """All positive excess returns => sortino should handle edge case."""
        returns = pd.Series([0.01, 0.02, 0.015, 0.005, 0.01])
        rf = 0.0
        sortino = RiskAnalyzer._sortino_ratio(returns, rf)
        # All positive excess => no downside, sortino returns 0
        assert sortino == 0.0

    def test_sortino_with_mixed_returns(self):
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.015, 500))
        rf = 0.04 / 252
        sortino = RiskAnalyzer._sortino_ratio(returns, rf)
        assert isinstance(sortino, float)
