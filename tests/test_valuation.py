"""Tests for src.analysis.valuation -- DCF, sensitivity, Monte Carlo, DDM, comparables."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.analysis.valuation import (
    ValuationAnalyzer,
    ValuationAnalyzerPlugin,
    _safe_float,
    _safe_div,
    _extract_row,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cash_flow_df(fcf=20_000_000):
    """Return a minimal cash-flow DataFrame usable by dcf_valuation."""
    dates = pd.to_datetime(["2023-12-31"])
    return pd.DataFrame({"Free Cash Flow": [fcf]}, index=dates).T


def _make_balance_sheet(debt=50_000_000, cash=25_000_000):
    dates = pd.to_datetime(["2023-12-31"])
    return pd.DataFrame(
        {
            "Total Debt": [debt],
            "Cash And Cash Equivalents": [cash],
        },
        index=dates,
    ).T


def _make_income_stmt(interest=2_000_000):
    dates = pd.to_datetime(["2023-12-31"])
    return pd.DataFrame(
        {"Interest Expense": [interest]},
        index=dates,
    ).T


def _default_info():
    return {
        "beta": 1.2,
        "marketCap": 1_000_000_000,
        "currentPrice": 100.0,
        "sharesOutstanding": 10_000_000,
        "dividendRate": 0.0,
    }


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------

class TestSafeFloat:

    def test_safe_float_with_numeric(self):
        assert _safe_float(3.14) == 3.14

    def test_safe_float_with_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_with_default(self):
        assert _safe_float(None, default=5.0) == 5.0

    def test_safe_float_with_string(self):
        assert _safe_float("not_a_number") == 0.0

    def test_safe_float_with_numeric_string(self):
        assert _safe_float("42.5") == 42.5


class TestSafeDiv:

    def test_safe_div_normal(self):
        assert _safe_div(10.0, 2.0) == pytest.approx(5.0)

    def test_safe_div_zero_denominator(self):
        assert _safe_div(10.0, 0.0) == 0.0

    def test_safe_div_near_zero_denominator(self):
        assert _safe_div(10.0, 1e-15) == 0.0

    def test_safe_div_custom_default(self):
        assert _safe_div(10.0, 0.0, default=-1.0) == -1.0


class TestExtractRow:

    def test_extract_row_first_name_found(self):
        df = pd.DataFrame({"val": [100.0]}, index=["Free Cash Flow"]).T
        # Transpose so "Free Cash Flow" is in the index
        df_t = pd.DataFrame({"2023": [100.0]}, index=["Free Cash Flow"])
        result = _extract_row(df_t, ["Free Cash Flow"])
        assert result == pytest.approx(100.0)

    def test_extract_row_second_name_fallback(self):
        df = pd.DataFrame({"2023": [42.0]}, index=["Alt Name"])
        result = _extract_row(df, ["Primary Name", "Alt Name"])
        assert result == pytest.approx(42.0)

    def test_extract_row_none_when_missing(self):
        df = pd.DataFrame({"2023": [42.0]}, index=["Something Else"])
        result = _extract_row(df, ["Nonexistent"])
        assert result is None

    def test_extract_row_none_for_nan(self):
        df = pd.DataFrame({"2023": [float("nan")]}, index=["Key"])
        result = _extract_row(df, ["Key"])
        assert result is None


# ---------------------------------------------------------------------------
# Tests for _dcf_intrinsic_per_share (fast inner DCF)
# ---------------------------------------------------------------------------

class TestDCFIntrinsicPerShare:
    """Test the stripped-down DCF used for sensitivity and Monte Carlo."""

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient"), \
             patch("src.analysis.valuation.MacroDataClient"):
            self.analyzer = ValuationAnalyzer()

    def test_positive_fcf_returns_positive_value(self):
        result = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000,
            growth_rate=0.08,
            discount_rate=0.10,
            terminal_growth=0.025,
            stage1_years=5,
            stage2_years=5,
            net_debt=25_000_000,
            shares_outstanding=10_000_000,
        )
        assert result > 0

    def test_discount_rate_below_terminal_growth_returns_zero(self):
        result = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000,
            growth_rate=0.08,
            discount_rate=0.02,
            terminal_growth=0.025,
            stage1_years=5,
            stage2_years=5,
            net_debt=0,
            shares_outstanding=10_000_000,
        )
        assert result == 0.0

    def test_zero_shares_returns_zero(self):
        result = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000,
            growth_rate=0.08,
            discount_rate=0.10,
            terminal_growth=0.025,
            stage1_years=5,
            stage2_years=5,
            net_debt=0,
            shares_outstanding=0,
        )
        assert result == 0.0

    def test_higher_growth_increases_value(self):
        low_growth = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000, growth_rate=0.05, discount_rate=0.10,
            terminal_growth=0.025, stage1_years=5, stage2_years=5,
            net_debt=0, shares_outstanding=10_000_000,
        )
        high_growth = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000, growth_rate=0.15, discount_rate=0.10,
            terminal_growth=0.025, stage1_years=5, stage2_years=5,
            net_debt=0, shares_outstanding=10_000_000,
        )
        assert high_growth > low_growth

    def test_higher_discount_decreases_value(self):
        low_disc = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000, growth_rate=0.08, discount_rate=0.08,
            terminal_growth=0.025, stage1_years=5, stage2_years=5,
            net_debt=0, shares_outstanding=10_000_000,
        )
        high_disc = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000, growth_rate=0.08, discount_rate=0.15,
            terminal_growth=0.025, stage1_years=5, stage2_years=5,
            net_debt=0, shares_outstanding=10_000_000,
        )
        assert low_disc > high_disc

    def test_net_debt_subtraction(self):
        """Equity value = EV - net_debt; higher net_debt -> lower per-share value."""
        no_debt = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000, growth_rate=0.08, discount_rate=0.10,
            terminal_growth=0.025, stage1_years=5, stage2_years=5,
            net_debt=0, shares_outstanding=10_000_000,
        )
        with_debt = self.analyzer._dcf_intrinsic_per_share(
            current_fcf=20_000_000, growth_rate=0.08, discount_rate=0.10,
            terminal_growth=0.025, stage1_years=5, stage2_years=5,
            net_debt=50_000_000, shares_outstanding=10_000_000,
        )
        assert no_debt > with_debt
        assert no_debt - with_debt == pytest.approx(50_000_000 / 10_000_000, abs=0.01)


# ---------------------------------------------------------------------------
# Tests for multi-stage DCF
# ---------------------------------------------------------------------------

class TestDCFValuation:

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient") as mock_fc, \
             patch("src.analysis.valuation.MacroDataClient") as mock_mc:
            self.analyzer = ValuationAnalyzer()
            self.mock_fundamentals = mock_fc.return_value
            self.mock_macro = mock_mc.return_value

    def _setup_mocks(self, fcf=20_000_000, debt=50_000_000, cash=25_000_000,
                     interest=2_000_000):
        self.mock_fundamentals.get_cash_flow.return_value = _make_cash_flow_df(fcf)
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet(debt, cash)
        self.mock_fundamentals.get_income_statement.return_value = _make_income_stmt(interest)
        self.mock_macro.get_risk_free_rate.return_value = 0.04

    @patch("src.analysis.valuation.yf")
    def test_dcf_positive_fcf_returns_positive_intrinsic_value(self, mock_yf):
        self._setup_mocks()
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation("TEST", discount_rate=0.10)

        assert "error" not in result
        assert result["intrinsic_per_share"] > 0
        assert result["model"] == "multi_stage_dcf"
        assert result["current_fcf"] == 20_000_000

    @patch("src.analysis.valuation.yf")
    def test_dcf_projects_correct_number_of_fcfs(self, mock_yf):
        self._setup_mocks()
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation(
            "TEST", discount_rate=0.10, stage1_years=5, stage2_years=5
        )
        assert len(result["projected_fcfs"]) == 10  # 5 + 5

    @patch("src.analysis.valuation.yf")
    def test_dcf_stage1_grows_at_growth_rate(self, mock_yf):
        self._setup_mocks(fcf=1_000_000)
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation(
            "TEST", growth_rate=0.10, discount_rate=0.12,
            stage1_years=3, stage2_years=0,
        )
        fcfs = result["projected_fcfs"]
        assert fcfs[0] == pytest.approx(1_000_000 * 1.10, rel=0.01)
        assert fcfs[1] == pytest.approx(1_000_000 * 1.10 ** 2, rel=0.01)
        assert fcfs[2] == pytest.approx(1_000_000 * 1.10 ** 3, rel=0.01)

    @patch("src.analysis.valuation.yf")
    def test_dcf_ev_to_equity_bridge_subtracts_net_debt(self, mock_yf):
        self._setup_mocks(debt=50_000_000, cash=25_000_000)
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation("TEST", discount_rate=0.10)

        assert result["net_debt"] == pytest.approx(25_000_000, rel=0.01)
        assert result["equity_value"] == pytest.approx(
            result["enterprise_value"] - result["net_debt"], rel=0.01
        )

    @patch("src.analysis.valuation.yf")
    def test_dcf_empty_cashflow_returns_error(self, mock_yf):
        self.mock_fundamentals.get_cash_flow.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation("TEST")
        assert "error" in result

    @patch("src.analysis.valuation.yf")
    def test_dcf_negative_fcf_still_computes(self, mock_yf):
        self._setup_mocks(fcf=-5_000_000)
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation("TEST", discount_rate=0.10)
        # Should still compute, intrinsic will be negative or low
        assert "error" not in result
        assert result["current_fcf"] == -5_000_000

    @patch("src.analysis.valuation.yf")
    def test_dcf_discount_rate_below_terminal_returns_error(self, mock_yf):
        self._setup_mocks()
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.dcf_valuation(
            "TEST", discount_rate=0.02, terminal_growth=0.025
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests for Sensitivity Analysis
# ---------------------------------------------------------------------------

class TestSensitivityAnalysis:

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient") as mock_fc, \
             patch("src.analysis.valuation.MacroDataClient") as mock_mc:
            self.analyzer = ValuationAnalyzer()
            self.mock_fundamentals = mock_fc.return_value
            self.mock_macro = mock_mc.return_value

    @patch("src.analysis.valuation.yf")
    def test_sensitivity_matrix_dimensions(self, mock_yf):
        self.mock_fundamentals.get_cash_flow.return_value = _make_cash_flow_df()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()
        self.mock_macro.get_risk_free_rate.return_value = 0.04
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.sensitivity_analysis(
            "TEST",
            base_growth=0.08,
            base_wacc=0.10,
            growth_step=0.01,
            growth_spread=0.02,
            wacc_step=0.01,
            wacc_spread=0.02,
        )

        assert "error" not in result
        growth_rates = result["growth_rates"]
        discount_rates = result["discount_rates"]
        matrix = result["matrix"]

        # growth axis: from 0.06 to 0.10 in 0.01 steps = 5 values
        assert len(growth_rates) == 5
        assert len(matrix) == len(growth_rates)

        # Each row should have len(discount_rates) columns
        for g_key, row in matrix.items():
            assert len(row) == len(discount_rates)

    @patch("src.analysis.valuation.yf")
    def test_sensitivity_growth_and_wacc_axes_correct(self, mock_yf):
        self.mock_fundamentals.get_cash_flow.return_value = _make_cash_flow_df()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()
        self.mock_macro.get_risk_free_rate.return_value = 0.04
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.sensitivity_analysis(
            "TEST", base_growth=0.10, base_wacc=0.12,
            growth_step=0.02, growth_spread=0.02,
            wacc_step=0.01, wacc_spread=0.01,
        )

        # growth: 0.08, 0.10, 0.12
        assert 0.08 in [round(g, 2) for g in result["growth_rates"]]
        assert 0.10 in [round(g, 2) for g in result["growth_rates"]]


# ---------------------------------------------------------------------------
# Tests for Monte Carlo DCF
# ---------------------------------------------------------------------------

class TestMonteCarloDCF:

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient") as mock_fc, \
             patch("src.analysis.valuation.MacroDataClient") as mock_mc:
            self.analyzer = ValuationAnalyzer()
            self.mock_fundamentals = mock_fc.return_value
            self.mock_macro = mock_mc.return_value

    @patch("src.analysis.valuation.yf")
    def test_monte_carlo_returns_percentiles_and_probability(self, mock_yf):
        self.mock_fundamentals.get_cash_flow.return_value = _make_cash_flow_df()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()
        self.mock_macro.get_risk_free_rate.return_value = 0.04
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.monte_carlo_dcf(
            "TEST", growth_mean=0.08, wacc_mean=0.10, n_simulations=500,
        )

        assert "error" not in result
        assert "p10" in result
        assert "p25" in result
        assert "p75" in result
        assert "p90" in result
        assert "probability_undervalued_pct" in result
        assert "mean" in result
        assert "median" in result
        assert result["n_simulations"] == 500

    @patch("src.analysis.valuation.yf")
    def test_monte_carlo_percentile_ordering(self, mock_yf):
        self.mock_fundamentals.get_cash_flow.return_value = _make_cash_flow_df()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()
        self.mock_macro.get_risk_free_rate.return_value = 0.04
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.monte_carlo_dcf(
            "TEST", growth_mean=0.08, wacc_mean=0.10, n_simulations=500,
        )
        assert result["p10"] <= result["p25"]
        assert result["p25"] <= result["median"]
        assert result["median"] <= result["p75"]
        assert result["p75"] <= result["p90"]

    @patch("src.analysis.valuation.yf")
    def test_monte_carlo_empty_cashflow_returns_error(self, mock_yf):
        self.mock_fundamentals.get_cash_flow.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.monte_carlo_dcf("TEST")
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests for Comparable Valuation
# ---------------------------------------------------------------------------

class TestComparableValuation:

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient") as mock_fc, \
             patch("src.analysis.valuation.MacroDataClient"):
            self.analyzer = ValuationAnalyzer()
            self.mock_fundamentals = mock_fc.return_value

    @patch("src.analysis.valuation.yf")
    def test_comparable_premium_calculation(self, mock_yf):
        # Company ratios
        self.mock_fundamentals.get_key_ratios.side_effect = lambda t: {
            "TEST": {"pe_forward": 20.0, "pb_ratio": 3.0, "ps_ratio": 5.0, "ev_ebitda": 15.0, "ticker": "TEST"},
            "PEER1": {"pe_forward": 15.0, "pb_ratio": 2.5, "ps_ratio": 4.0, "ev_ebitda": 12.0, "ticker": "PEER1"},
            "PEER2": {"pe_forward": 18.0, "pb_ratio": 2.8, "ps_ratio": 4.5, "ev_ebitda": 14.0, "ticker": "PEER2"},
        }.get(t, {})

        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()

        info_map = {
            "TEST": {**_default_info(), "enterpriseValue": 1_500_000_000, "totalRevenue": 100_000_000},
            "PEER1": {"enterpriseValue": 1_200_000_000, "totalRevenue": 100_000_000},
            "PEER2": {"enterpriseValue": 1_400_000_000, "totalRevenue": 100_000_000},
        }
        mock_yf.Ticker.return_value.info = info_map["TEST"]

        # Override _get_ticker_info to return the right info per call
        call_count = [0]
        original_tickers = ["TEST", "PEER1", "PEER2"]

        def side_effect_info(t):
            return info_map.get(t, {})

        self.analyzer._get_ticker_info = side_effect_info

        result = self.analyzer.comparable_valuation("TEST", peers=["PEER1", "PEER2"])

        assert "error" not in result
        assert "comparison" in result
        assert "implied_values" in result
        assert result["peers"] == ["PEER1", "PEER2"]

    @patch("src.analysis.valuation.yf")
    def test_comparable_no_peers_returns_error(self, mock_yf):
        self.mock_fundamentals.get_key_ratios.return_value = {"pe_forward": 20.0}
        self.mock_fundamentals.get_peers.return_value = []
        mock_yf.Ticker.return_value.info = _default_info()

        result = self.analyzer.comparable_valuation("TEST", peers=[])
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests for Dividend Discount Model
# ---------------------------------------------------------------------------

class TestDividendDiscountModel:

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient") as mock_fc, \
             patch("src.analysis.valuation.MacroDataClient") as mock_mc:
            self.analyzer = ValuationAnalyzer()
            self.mock_fundamentals = mock_fc.return_value
            self.mock_macro = mock_mc.return_value

    @patch("src.analysis.valuation.yf")
    def test_ddm_skips_non_payer(self, mock_yf):
        info = _default_info()
        info["dividendRate"] = 0.0
        info["trailingAnnualDividendRate"] = 0.0
        mock_yf.Ticker.return_value.info = info

        result = self.analyzer.dividend_discount_model("TEST")
        assert result["skipped"] is True
        assert "does not pay" in result["reason"].lower()

    @patch("src.analysis.valuation.yf")
    def test_ddm_gordon_growth_for_stable_payer(self, mock_yf):
        """Stable payer: growth < 4%, should use Gordon Growth Model."""
        info = _default_info()
        info["dividendRate"] = 2.50
        info["trailingAnnualDividendRate"] = 2.50
        info["earningsGrowth"] = 0.03  # 3% < 4% threshold
        info["currentPrice"] = 50.0
        info["beta"] = 1.0
        mock_yf.Ticker.return_value.info = info

        self.mock_fundamentals.get_income_statement.return_value = _make_income_stmt()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()
        self.mock_macro.get_risk_free_rate.return_value = 0.04

        result = self.analyzer.dividend_discount_model("TEST", cost_of_equity=0.09)
        assert result["skipped"] is False
        assert result["model"] == "gordon_growth"

        # Gordon Growth: P = D1 / (ke - g) = 2.50 * 1.03 / (0.09 - 0.03) = 42.917
        d1 = 2.50 * 1.03
        expected = d1 / (0.09 - 0.03)
        assert result["intrinsic_value"] == pytest.approx(expected, rel=0.01)

    @patch("src.analysis.valuation.yf")
    def test_ddm_two_stage_for_growth_payer(self, mock_yf):
        """Growth payer: growth > 4%, should use two-stage DDM."""
        info = _default_info()
        info["dividendRate"] = 2.00
        info["trailingAnnualDividendRate"] = 2.00
        info["earningsGrowth"] = 0.12  # 12% > 4% threshold
        info["currentPrice"] = 80.0
        info["beta"] = 1.0
        mock_yf.Ticker.return_value.info = info

        self.mock_fundamentals.get_income_statement.return_value = _make_income_stmt()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()
        self.mock_macro.get_risk_free_rate.return_value = 0.04

        result = self.analyzer.dividend_discount_model(
            "TEST", cost_of_equity=0.10, high_growth_rate=0.12,
        )
        assert result["skipped"] is False
        assert result["model"] == "two_stage_ddm"
        assert result["intrinsic_value"] > 0


# ---------------------------------------------------------------------------
# Tests for WACC
# ---------------------------------------------------------------------------

class TestWACC:

    def setup_method(self):
        with patch("src.analysis.valuation.FundamentalsClient") as mock_fc, \
             patch("src.analysis.valuation.MacroDataClient") as mock_mc:
            self.analyzer = ValuationAnalyzer()
            self.mock_fundamentals = mock_fc.return_value
            self.mock_macro = mock_mc.return_value

    @patch("src.analysis.valuation.yf")
    def test_wacc_capm_formula(self, mock_yf):
        """Verify cost_of_equity = Rf + beta * ERP."""
        info = _default_info()
        info["beta"] = 1.5
        info["marketCap"] = 1_000_000_000
        mock_yf.Ticker.return_value.info = info

        self.mock_macro.get_risk_free_rate.return_value = 0.04
        self.mock_fundamentals.get_income_statement.return_value = _make_income_stmt()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()

        result = self.analyzer.calculate_wacc("TEST", info=info)

        expected_ke = 0.04 + 1.5 * 0.055
        assert result["cost_of_equity"] == pytest.approx(expected_ke, abs=0.0001)
        assert result["beta"] == pytest.approx(1.5, abs=0.01)
        assert result["risk_free_rate"] == pytest.approx(0.04, abs=0.001)

    @patch("src.analysis.valuation.yf")
    def test_wacc_beta_clamped(self, mock_yf):
        """Beta should be clamped to [0.2, 3.0]."""
        info = _default_info()
        info["beta"] = 5.0  # way too high
        mock_yf.Ticker.return_value.info = info

        self.mock_macro.get_risk_free_rate.return_value = 0.04
        self.mock_fundamentals.get_income_statement.return_value = _make_income_stmt()
        self.mock_fundamentals.get_balance_sheet.return_value = _make_balance_sheet()

        result = self.analyzer.calculate_wacc("TEST", info=info)
        assert result["beta"] == pytest.approx(3.0, abs=0.01)


# ---------------------------------------------------------------------------
# Tests for Plugin scoring helpers
# ---------------------------------------------------------------------------

class TestValuationPlugin:

    def test_score_margin_of_safety_maps_correctly(self):
        assert ValuationAnalyzerPlugin._score_margin_of_safety(-50.0) == pytest.approx(0.0)
        assert ValuationAnalyzerPlugin._score_margin_of_safety(0.0) == pytest.approx(50.0)
        assert ValuationAnalyzerPlugin._score_margin_of_safety(50.0) == pytest.approx(100.0)
        assert ValuationAnalyzerPlugin._score_margin_of_safety(100.0) == pytest.approx(100.0)

    def test_score_mc_probability_maps_correctly(self):
        assert ValuationAnalyzerPlugin._score_mc_probability(0.0) == pytest.approx(0.0)
        assert ValuationAnalyzerPlugin._score_mc_probability(50.0) == pytest.approx(50.0)
        assert ValuationAnalyzerPlugin._score_mc_probability(100.0) == pytest.approx(100.0)

    def test_score_comparable_premium_maps_correctly(self):
        # -40% discount -> 90
        assert ValuationAnalyzerPlugin._score_comparable_premium(-40.0) == pytest.approx(90.0)
        # 0% premium -> 50
        assert ValuationAnalyzerPlugin._score_comparable_premium(0.0) == pytest.approx(50.0)
        # +40% premium -> 10
        assert ValuationAnalyzerPlugin._score_comparable_premium(40.0) == pytest.approx(10.0)
        # None -> 50
        assert ValuationAnalyzerPlugin._score_comparable_premium(None) == pytest.approx(50.0)
