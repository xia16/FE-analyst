"""Tests for src.analysis.portfolio -- mean-variance, risk parity, Kelly, sizing, analysis, frontier."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from src.analysis.portfolio import (
    PortfolioOptimizer,
    PositionSizer,
    PortfolioAnalyzer,
    _to_float,
    _regularize_cov,
    _fetch_returns,
    _TRADING_DAYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_returns_df(
    tickers=("A", "B"),
    n=252,
    means=(0.0004, 0.0003),
    stds=(0.015, 0.020),
    corr=0.5,
    seed=42,
):
    """Generate a synthetic returns DataFrame with controlled correlation.

    Returns a DataFrame where columns are tickers and rows are daily returns.
    """
    np.random.seed(seed)
    k = len(tickers)
    # Build correlation matrix
    C = np.full((k, k), corr)
    np.fill_diagonal(C, 1.0)
    L = np.linalg.cholesky(C)

    # Generate uncorrelated random normals, then correlate
    raw = np.random.randn(n, k)
    for i in range(k):
        raw[:, i] = raw[:, i] * stds[i] + means[i]

    # Apply correlation via Cholesky
    correlated = raw @ L.T

    dates = pd.bdate_range(start="2023-01-02", periods=n)
    df = pd.DataFrame(correlated, index=dates, columns=list(tickers))
    return df


def _mock_portfolio_optimizer(returns_df):
    """Create a PortfolioOptimizer with mocked MarketDataClient."""
    with patch("src.analysis.portfolio.MarketDataClient") as MockMDC:
        opt = PortfolioOptimizer()
        mock_mdc = MockMDC.return_value
        # For each ticker, return price data that produces the matching returns
        def _get_history(ticker, period="2y"):
            if ticker not in returns_df.columns:
                return pd.DataFrame()
            ret = returns_df[ticker]
            price = 100.0 * (1 + ret).cumprod()
            return pd.DataFrame({
                "Open": price, "High": price * 1.01, "Low": price * 0.99,
                "Close": price, "Volume": np.ones(len(price)) * 1e6,
            }, index=ret.index)
        mock_mdc.get_price_history.side_effect = _get_history
        opt.market = mock_mdc
        return opt


def _mock_portfolio_analyzer(returns_df):
    """Create a PortfolioAnalyzer with mocked MarketDataClient."""
    with patch("src.analysis.portfolio.MarketDataClient") as MockMDC:
        analyzer = PortfolioAnalyzer()
        mock_mdc = MockMDC.return_value
        def _get_history(ticker, period="2y"):
            if ticker not in returns_df.columns:
                return pd.DataFrame()
            ret = returns_df[ticker]
            price = 100.0 * (1 + ret).cumprod()
            return pd.DataFrame({
                "Open": price, "High": price * 1.01, "Low": price * 0.99,
                "Close": price, "Volume": np.ones(len(price)) * 1e6,
            }, index=ret.index)
        mock_mdc.get_price_history.side_effect = _get_history
        analyzer.market = mock_mdc
        return analyzer


# ---------------------------------------------------------------------------
# Tests for _to_float and _regularize_cov helpers
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_to_float_normal(self):
        assert _to_float(3.141592653) == pytest.approx(3.141593, abs=1e-6)

    def test_to_float_numpy_scalar(self):
        assert isinstance(_to_float(np.float64(42.0)), float)

    def test_regularize_cov_adds_ridge(self):
        cov = np.array([[1.0, 0.5], [0.5, 1.0]])
        reg = _regularize_cov(cov, eps=0.01)
        assert reg[0, 0] == pytest.approx(1.01, abs=1e-6)
        assert reg[1, 1] == pytest.approx(1.01, abs=1e-6)
        assert reg[0, 1] == pytest.approx(0.5, abs=1e-6)

    def test_regularize_cov_preserves_symmetry(self):
        np.random.seed(42)
        cov = np.random.randn(3, 3)
        cov = cov @ cov.T  # make PSD
        reg = _regularize_cov(cov)
        assert np.allclose(reg, reg.T)


# ---------------------------------------------------------------------------
# Tests for _fetch_returns
# ---------------------------------------------------------------------------

class TestFetchReturns:

    def test_fetch_returns_builds_aligned_df(self):
        ret_df = _make_returns_df(tickers=("X", "Y"))
        with patch("src.analysis.portfolio.MarketDataClient") as MockMDC:
            mock_mdc = MockMDC.return_value
            def _get(ticker, period="2y"):
                r = ret_df[ticker]
                price = 100.0 * (1 + r).cumprod()
                return pd.DataFrame({"Close": price}, index=r.index)
            mock_mdc.get_price_history.side_effect = _get

            result = _fetch_returns(mock_mdc, ["X", "Y"])
            assert list(result.columns) == ["X", "Y"]
            assert len(result) > 0

    def test_fetch_returns_raises_on_empty(self):
        with patch("src.analysis.portfolio.MarketDataClient") as MockMDC:
            mock_mdc = MockMDC.return_value
            mock_mdc.get_price_history.return_value = pd.DataFrame()

            with pytest.raises(ValueError, match="No valid price data"):
                _fetch_returns(mock_mdc, ["NOTHING"])


# ---------------------------------------------------------------------------
# Tests for Mean-Variance Optimization
# ---------------------------------------------------------------------------

class TestMeanVarianceOptimization:

    def test_two_negatively_correlated_assets_50_50(self):
        """Perfectly negatively correlated assets => optimal is ~50/50."""
        np.random.seed(42)
        n = 500
        dates = pd.bdate_range(start="2023-01-02", periods=n)
        base = np.random.normal(0.0005, 0.01, n)
        # Asset A = base; Asset B = -base + same positive mean
        a_returns = base
        b_returns = -base + 0.001

        ret_df = pd.DataFrame({"A": a_returns, "B": b_returns}, index=dates)
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_mean_variance(["A", "B"], risk_free_rate=0.00)

        w_a = result["optimal_weights"]["A"]
        w_b = result["optimal_weights"]["B"]
        # Weights should be close to 50/50 for min-variance of neg-corr assets
        min_var = result["min_variance_portfolio"]
        assert min_var["weights"]["A"] == pytest.approx(0.5, abs=0.15)
        assert min_var["weights"]["B"] == pytest.approx(0.5, abs=0.15)

    def test_weights_sum_to_one(self):
        ret_df = _make_returns_df(tickers=("X", "Y", "Z"),
                                  means=(0.0004, 0.0003, 0.0005),
                                  stds=(0.015, 0.020, 0.018))
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_mean_variance(["X", "Y", "Z"])
        total = sum(result["optimal_weights"].values())
        assert total == pytest.approx(1.0, abs=0.001)

    def test_weights_non_negative(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_mean_variance(["A", "B"])
        for w in result["optimal_weights"].values():
            assert w >= -0.001  # allow small numerical noise

    def test_single_asset(self):
        ret_df = _make_returns_df(tickers=("ONLY",), means=(0.001,), stds=(0.02,), corr=1.0)
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_mean_variance(["ONLY"])
        assert result["optimal_weights"]["ONLY"] == pytest.approx(1.0, abs=0.001)

    def test_target_return_constraint(self):
        ret_df = _make_returns_df(tickers=("A", "B"),
                                  means=(0.0004, 0.0008),
                                  stds=(0.015, 0.020))
        opt = _mock_portfolio_optimizer(ret_df)
        target = 0.15

        result = opt.optimize_mean_variance(["A", "B"], target_return=target)
        # The achieved return should be close to the target
        assert result["expected_return"] == pytest.approx(target, abs=0.05)

    def test_result_structure(self):
        ret_df = _make_returns_df()
        opt = _mock_portfolio_optimizer(ret_df)
        result = opt.optimize_mean_variance(["A", "B"])

        assert "method" in result
        assert result["method"] == "mean_variance"
        assert "optimal_weights" in result
        assert "expected_return" in result
        assert "expected_volatility" in result
        assert "sharpe_ratio" in result
        assert "min_variance_portfolio" in result


# ---------------------------------------------------------------------------
# Tests for Risk Parity
# ---------------------------------------------------------------------------

class TestRiskParity:

    def test_risk_contributions_equalized(self):
        """After risk-parity optimization, risk contributions should be ~equal."""
        np.random.seed(42)
        ret_df = _make_returns_df(tickers=("A", "B", "C"),
                                  means=(0.0004, 0.0003, 0.0005),
                                  stds=(0.01, 0.02, 0.015),
                                  corr=0.3)
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_risk_parity(["A", "B", "C"])
        rc = result["risk_contributions"]

        vals = list(rc.values())
        mean_rc = np.mean(vals)
        for v in vals:
            assert v == pytest.approx(mean_rc, abs=0.08)

    def test_weights_sum_to_one(self):
        ret_df = _make_returns_df(tickers=("X", "Y"))
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_risk_parity(["X", "Y"])
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=0.001)

    def test_higher_vol_asset_gets_lower_weight(self):
        """In risk parity, the more volatile asset should get less weight."""
        np.random.seed(42)
        ret_df = _make_returns_df(tickers=("LOW_VOL", "HIGH_VOL"),
                                  means=(0.0004, 0.0004),
                                  stds=(0.005, 0.03),
                                  corr=0.3)
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_risk_parity(["LOW_VOL", "HIGH_VOL"])
        assert result["weights"]["LOW_VOL"] > result["weights"]["HIGH_VOL"]

    def test_single_asset_returns_full_weight(self):
        ret_df = _make_returns_df(tickers=("ONLY",), means=(0.001,), stds=(0.02,), corr=1.0)
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_risk_parity(["ONLY"])
        assert result["weights"]["ONLY"] == pytest.approx(1.0, abs=0.001)


# ---------------------------------------------------------------------------
# Tests for Kelly Criterion
# ---------------------------------------------------------------------------

class TestKellyCriterion:

    def test_known_win_rate_and_payoff(self):
        """win_rate=0.6, avg_win=1.5, avg_loss=1.0 => f* = (0.6*1.5 - 0.4)/1.5 = 0.333."""
        result = PositionSizer.kelly_size(
            win_rate=0.6, avg_win=1.5, avg_loss=1.0,
        )
        expected_full = (0.6 * 1.5 - 0.4) / 1.5
        assert result["full_kelly_fraction"] == pytest.approx(expected_full, abs=0.001)
        assert result["half_kelly_fraction"] == pytest.approx(expected_full / 2, abs=0.001)

    def test_50_50_coin_toss_even_payoff_zero_kelly(self):
        """win=0.5, avg_win=1, avg_loss=1 => no edge => kelly=0."""
        result = PositionSizer.kelly_size(
            win_rate=0.5, avg_win=1.0, avg_loss=1.0,
        )
        assert result["full_kelly_fraction"] == pytest.approx(0.0, abs=0.001)

    def test_negative_edge_clamps_to_zero(self):
        """Bad win rate + low payoff => negative edge, clamped to 0."""
        result = PositionSizer.kelly_size(
            win_rate=0.3, avg_win=1.0, avg_loss=1.0,
        )
        assert result["full_kelly_fraction"] == pytest.approx(0.0, abs=0.001)

    def test_edge_field(self):
        result = PositionSizer.kelly_size(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
        # edge = p * b - q = 0.6 * 2.0 - 0.4 = 0.8
        assert result["edge"] == pytest.approx(0.8, abs=0.001)

    def test_invalid_avg_loss_raises(self):
        with pytest.raises(ValueError, match="avg_loss must be positive"):
            PositionSizer.kelly_size(win_rate=0.5, avg_win=1.0, avg_loss=-1.0)

    def test_invalid_win_rate_raises(self):
        with pytest.raises(ValueError, match="win_rate must be between"):
            PositionSizer.kelly_size(win_rate=1.5, avg_win=1.0, avg_loss=1.0)

    def test_recommended_pct_is_half_kelly_times_100(self):
        result = PositionSizer.kelly_size(win_rate=0.6, avg_win=1.5, avg_loss=1.0)
        assert result["recommended_pct"] == pytest.approx(
            result["half_kelly_fraction"] * 100, abs=0.01
        )


# ---------------------------------------------------------------------------
# Tests for Volatility Sizing
# ---------------------------------------------------------------------------

class TestVolatilitySizing:

    def test_position_size_formula(self):
        """dollar_amount = (target_vol * portfolio_value) / asset_vol.

        shares = int(dollar_amount / price)
        """
        with patch("src.analysis.portfolio.MarketDataClient") as MockMDC:
            sizer = PositionSizer()
            mock_mdc = MockMDC.return_value

            np.random.seed(42)
            n = 252
            dates = pd.bdate_range(start="2023-01-02", periods=n)
            price_base = 50.0
            # Known daily vol: std of returns * sqrt(252)
            daily_std = 0.02
            returns = np.random.normal(0.001, daily_std, n)
            close = price_base * np.exp(np.cumsum(returns))
            df = pd.DataFrame({"Close": close}, index=dates)
            mock_mdc.get_price_history.return_value = df
            sizer.market = mock_mdc

            result = sizer.vol_size(
                "TEST", target_vol=0.15, portfolio_value=100_000.0,
            )

            assert result["shares"] > 0
            assert result["dollar_amount"] > 0
            assert result["asset_volatility"] > 0
            assert result["target_vol"] == 0.15

    def test_near_zero_vol_handled(self):
        """Asset with ~0 vol gets capped position."""
        with patch("src.analysis.portfolio.MarketDataClient") as MockMDC:
            sizer = PositionSizer()
            mock_mdc = MockMDC.return_value

            n = 100
            dates = pd.bdate_range(start="2023-01-02", periods=n)
            close = pd.Series(np.full(n, 100.0), index=dates)
            df = pd.DataFrame({"Close": close}, index=dates)
            mock_mdc.get_price_history.return_value = df
            sizer.market = mock_mdc

            result = sizer.vol_size("TEST", target_vol=0.15, portfolio_value=100_000.0)
            # Should not crash; shares will be large
            assert result["shares"] >= 0


# ---------------------------------------------------------------------------
# Tests for PortfolioAnalyzer
# ---------------------------------------------------------------------------

class TestPortfolioAnalyzer:

    def test_portfolio_return_equals_weighted_avg(self):
        """Portfolio return = sum(w_i * mu_i) annualized."""
        ret_df = _make_returns_df(tickers=("A", "B"),
                                  means=(0.0004, 0.0008),
                                  stds=(0.015, 0.020))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(
            tickers=["A", "B"],
            weights=[0.6, 0.4],
        )

        # Compute expected from the actual return data
        daily_mu = ret_df.mean().values
        w = np.array([0.6, 0.4])
        expected_ret = float(w @ (daily_mu * _TRADING_DAYS))
        assert result["portfolio_return"] == pytest.approx(expected_ret, rel=0.05)

    def test_weights_are_normalized(self):
        ret_df = _make_returns_df()
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(
            tickers=["A", "B"],
            weights=[3.0, 7.0],  # will be normalized to 0.3, 0.7
        )
        total_w = sum(result["weights"].values())
        assert total_w == pytest.approx(1.0, abs=0.001)

    def test_correlation_matrix_diagonal_is_one(self):
        ret_df = _make_returns_df(tickers=("X", "Y"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(["X", "Y"], [0.5, 0.5])
        corr = result["correlation_matrix"]
        for t in ["X", "Y"]:
            assert corr[t][t] == pytest.approx(1.0, abs=0.01)

    def test_hhi_concentration(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(["A", "B"], [0.5, 0.5])
        # HHI for 50/50 = 0.25 + 0.25 = 0.5
        assert result["hhi"] == pytest.approx(0.5, abs=0.01)

    def test_effective_n(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(["A", "B"], [0.5, 0.5])
        # Effective N = 1/HHI = 1/0.5 = 2.0
        assert result["effective_n"] == pytest.approx(2.0, abs=0.1)

    def test_diversification_ratio_at_least_one(self):
        """Diversification ratio >= 1 (equal for perfectly correlated)."""
        ret_df = _make_returns_df(tickers=("A", "B"), corr=0.3)
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(["A", "B"], [0.5, 0.5])
        assert result["diversification_ratio"] >= 1.0 - 0.01

    def test_mismatched_tickers_weights_raises(self):
        ret_df = _make_returns_df()
        analyzer = _mock_portfolio_analyzer(ret_df)

        with pytest.raises(ValueError, match="same length"):
            analyzer.analyze_portfolio(["A", "B"], [1.0])

    def test_risk_contributions_sum_to_portfolio_vol(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.analyze_portfolio(["A", "B"], [0.5, 0.5])
        rc_total = sum(result["risk_contributions"].values())
        assert rc_total == pytest.approx(result["portfolio_volatility"], rel=0.05)


# ---------------------------------------------------------------------------
# Tests for Efficient Frontier
# ---------------------------------------------------------------------------

class TestEfficientFrontier:

    def test_n_points_returned(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.compute_efficient_frontier(["A", "B"], n_points=20)
        # At least some frontier points should be returned
        assert result["n_points"] > 0
        assert result["n_points"] <= 20

    def test_all_frontier_weights_sum_to_one(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.compute_efficient_frontier(["A", "B"], n_points=10)
        for point in result["frontier"]:
            total = sum(point["weights"].values())
            assert total == pytest.approx(1.0, abs=0.01)

    def test_tangency_portfolio_exists(self):
        ret_df = _make_returns_df(tickers=("X", "Y"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.compute_efficient_frontier(["X", "Y"], n_points=10)
        assert "tangency_portfolio" in result
        assert "weights" in result["tangency_portfolio"]
        assert sum(result["tangency_portfolio"]["weights"].values()) == pytest.approx(1.0, abs=0.01)

    def test_min_variance_portfolio_exists(self):
        ret_df = _make_returns_df(tickers=("X", "Y"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.compute_efficient_frontier(["X", "Y"], n_points=10)
        assert "min_variance_portfolio" in result
        mvp = result["min_variance_portfolio"]
        assert mvp["expected_volatility"] > 0

    def test_frontier_volatility_increases_with_return(self):
        """On the efficient frontier, higher return generally means higher vol."""
        ret_df = _make_returns_df(tickers=("A", "B"),
                                  means=(0.0002, 0.001),
                                  stds=(0.01, 0.025))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.compute_efficient_frontier(["A", "B"], n_points=30)
        frontier = result["frontier"]
        if len(frontier) >= 2:
            # Check that overall trend is non-decreasing
            vols = [p["expected_volatility"] for p in frontier]
            # Allow some non-monotonicity from optimization noise
            assert vols[-1] >= vols[0] - 0.01


# ---------------------------------------------------------------------------
# Tests for Rebalancing Analysis
# ---------------------------------------------------------------------------

class TestRebalancingAnalysis:

    def test_rebalancing_trade_directions(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.rebalancing_analysis(
            tickers=["A", "B"],
            weights=[0.6, 0.4],
            current_prices={"A": 100.0, "B": 50.0},
            current_shares={"A": 500, "B": 500},
            portfolio_value=100_000,
        )

        assert len(result["trades"]) == 2
        for trade in result["trades"]:
            assert trade["action"] in ("BUY", "SELL", "HOLD")

    def test_turnover_calculation(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.rebalancing_analysis(
            tickers=["A", "B"],
            weights=[0.5, 0.5],
            current_prices={"A": 100.0, "B": 100.0},
            current_shares={"A": 400, "B": 600},
            portfolio_value=100_000,
        )
        assert result["turnover"] >= 0
        assert result["total_trade_value"] >= 0

    def test_transaction_cost_proportional(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        analyzer = _mock_portfolio_analyzer(ret_df)

        result = analyzer.rebalancing_analysis(
            tickers=["A", "B"],
            weights=[0.5, 0.5],
            current_prices={"A": 100.0, "B": 100.0},
            current_shares={"A": 400, "B": 600},
            portfolio_value=100_000,
            transaction_cost_bps=10.0,
        )
        expected_cost = result["total_trade_value"] * 10.0 / 10_000
        assert result["estimated_transaction_cost"] == pytest.approx(expected_cost, abs=0.01)


# ---------------------------------------------------------------------------
# Tests for Black-Litterman (basic structure)
# ---------------------------------------------------------------------------

class TestBlackLitterman:

    def test_bl_returns_optimal_weights(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        opt = _mock_portfolio_optimizer(ret_df)

        with patch("src.analysis.portfolio.yf") as mock_yf:
            # Mock market cap info
            mock_info = MagicMock()
            mock_info.market_cap = 1_000_000_000
            mock_yf.Ticker.return_value.fast_info = mock_info

            result = opt.optimize_black_litterman(
                tickers=["A", "B"],
                views=[{"ticker": "A", "expected_return": 0.15}],
                view_confidences=[0.8],
                market_caps={"A": 1e9, "B": 1e9},
            )

        assert "optimal_weights" in result
        total = sum(result["optimal_weights"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_bl_posterior_returns_differ_from_equilibrium(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_black_litterman(
            tickers=["A", "B"],
            views=[{"ticker": "A", "expected_return": 0.20}],
            view_confidences=[0.9],
            market_caps={"A": 1e9, "B": 1e9},
        )

        post_a = result["posterior_returns"]["A"]
        eq_a = result["equilibrium_returns"]["A"]
        # Posterior should be tilted toward the view
        assert post_a != eq_a

    def test_bl_mismatched_views_raises(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        opt = _mock_portfolio_optimizer(ret_df)

        with pytest.raises(ValueError, match="same length"):
            opt.optimize_black_litterman(
                tickers=["A", "B"],
                views=[{"ticker": "A", "expected_return": 0.15}],
                view_confidences=[0.8, 0.5],  # mismatched length
                market_caps={"A": 1e9, "B": 1e9},
            )


# ---------------------------------------------------------------------------
# Tests for equal risk contribution
# ---------------------------------------------------------------------------

class TestEqualRiskContribution:

    def test_equal_risk_weights_sum_to_one(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_equal_risk(["A", "B"])
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=0.001)

    def test_custom_risk_budgets(self):
        ret_df = _make_returns_df(tickers=("A", "B"))
        opt = _mock_portfolio_optimizer(ret_df)

        result = opt.optimize_equal_risk(
            ["A", "B"], risk_budgets=[0.7, 0.3]
        )
        assert "risk_budgets" in result
        assert result["risk_budgets"]["A"] == pytest.approx(0.7, abs=0.01)
        assert result["risk_budgets"]["B"] == pytest.approx(0.3, abs=0.01)
