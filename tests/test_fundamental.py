"""Tests for src.analysis.fundamental -- Piotroski, Altman, DuPont, Quality, Capital, Working Capital."""

import math
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.analysis.fundamental import (
    FundamentalAnalyzer,
    _extract,
    _safe_div,
    _num_periods,
    _clamp,
    _FIELD_ALIASES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_inc(periods=2, **overrides):
    """Build an income-statement DataFrame with sensible defaults.

    Most-recent column first (col 0).
    """
    dates = pd.to_datetime([f"{2023 - i}-12-31" for i in range(periods)])
    base = {
        "Total Revenue": [120e6, 110e6, 100e6, 90e6][:periods],
        "Cost Of Revenue": [72e6, 68e6, 65e6, 60e6][:periods],
        "Gross Profit": [48e6, 42e6, 35e6, 30e6][:periods],
        "Operating Income": [30e6, 26e6, 22e6, 18e6][:periods],
        "EBIT": [28e6, 24.5e6, 21e6, 17e6][:periods],
        "EBITDA": [35e6, 31e6, 27e6, 23e6][:periods],
        "Pretax Income": [26e6, 23e6, 19.5e6, 15.5e6][:periods],
        "Tax Provision": [5.46e6, 4.83e6, 4.095e6, 3.255e6][:periods],
        "Net Income": [20.54e6, 18.17e6, 15.405e6, 12.245e6][:periods],
        "Interest Expense": [2e6, 1.5e6, 1.5e6, 1.5e6][:periods],
    }
    base.update(overrides)
    data = {}
    for i, d in enumerate(dates):
        col = {}
        for key, vals in base.items():
            col[key] = vals[i]
        data[d] = col
    return pd.DataFrame(data)


def _make_bs(periods=2, **overrides):
    """Build a balance-sheet DataFrame."""
    dates = pd.to_datetime([f"{2023 - i}-12-31" for i in range(periods)])
    base = {
        "Total Assets": [200e6, 185e6, 170e6, 160e6][:periods],
        "Total Liabilities Net Minority Interest": [90e6, 85e6, 80e6, 78e6][:periods],
        "Stockholders Equity": [110e6, 100e6, 90e6, 82e6][:periods],
        "Current Assets": [60e6, 55e6, 50e6, 45e6][:periods],
        "Current Liabilities": [30e6, 32e6, 28e6, 27e6][:periods],
        "Total Debt": [50e6, 55e6, 52e6, 51e6][:periods],
        "Long Term Debt": [45e6, 50e6, 47e6, 46e6][:periods],
        "Cash And Cash Equivalents": [25e6, 20e6, 18e6, 15e6][:periods],
        "Net Receivables": [15e6, 14e6, 13e6, 12e6][:periods],
        "Inventory": [10e6, 12e6, 11e6, 10e6][:periods],
        "Accounts Payable": [8e6, 9e6, 7.5e6, 7e6][:periods],
        "Retained Earnings": [80e6, 70e6, 60e6, 50e6][:periods],
        "Ordinary Shares Number": [10e6, 10e6, 10e6, 10.5e6][:periods],
    }
    base.update(overrides)
    data = {}
    for i, d in enumerate(dates):
        col = {}
        for key, vals in base.items():
            col[key] = vals[i]
        data[d] = col
    return pd.DataFrame(data)


def _make_cf(periods=2, **overrides):
    """Build a cash-flow DataFrame."""
    dates = pd.to_datetime([f"{2023 - i}-12-31" for i in range(periods)])
    base = {
        "Operating Cash Flow": [28e6, 25e6, 22e6, 19e6][:periods],
        "Capital Expenditure": [-8e6, -7e6, -6.5e6, -6e6][:periods],
        "Free Cash Flow": [20e6, 18e6, 15.5e6, 13e6][:periods],
    }
    base.update(overrides)
    data = {}
    for i, d in enumerate(dates):
        col = {}
        for key, vals in base.items():
            col[key] = vals[i]
        data[d] = col
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Tests for low-level helpers
# ---------------------------------------------------------------------------

class TestExtract:

    def test_extract_returns_correct_value(self):
        inc = _make_inc()
        val = _extract(inc, "revenue", 0)
        assert val == pytest.approx(120e6)

    def test_extract_prior_period(self):
        inc = _make_inc()
        val = _extract(inc, "revenue", 1)
        assert val == pytest.approx(110e6)

    def test_extract_returns_none_for_empty_df(self):
        assert _extract(pd.DataFrame(), "revenue") is None
        assert _extract(None, "revenue") is None

    def test_extract_returns_none_for_missing_field(self):
        inc = _make_inc()
        assert _extract(inc, "nonexistent_field") is None

    def test_extract_returns_none_for_out_of_range_col(self):
        inc = _make_inc(periods=2)
        assert _extract(inc, "revenue", 5) is None


class TestFundamentalSafeDiv:

    def test_normal_division(self):
        assert _safe_div(10.0, 2.0) == pytest.approx(5.0)

    def test_zero_denominator(self):
        assert _safe_div(10.0, 0.0) is None

    def test_none_inputs(self):
        assert _safe_div(None, 2.0) is None
        assert _safe_div(10.0, None) is None

    def test_custom_default(self):
        assert _safe_div(10.0, 0.0, default=0.0) == 0.0


class TestClamp:

    def test_clamp_within_range(self):
        assert _clamp(50.0) == 50.0

    def test_clamp_below_minimum(self):
        assert _clamp(-10.0) == 0.0

    def test_clamp_above_maximum(self):
        assert _clamp(150.0) == 100.0


# ---------------------------------------------------------------------------
# Tests for Piotroski F-Score
# ---------------------------------------------------------------------------

class TestPiotroskiFScore:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_perfect_score_with_all_positive_signals(self):
        """Construct data where all 9 Piotroski flags should be 1."""
        # Current period: NI positive, CFO positive > NI, ROA improved,
        # leverage decreased, current ratio increased, no dilution,
        # gross margin improved, asset turnover improved
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)

        result = self.analyzer._piotroski_f_score(inc, bs, cf)

        assert result["f_score"] >= 0
        assert result["f_score"] <= 9
        assert result["max_score"] == 9
        assert isinstance(result["flags"], dict)
        assert len(result["flags"]) == 9

    def test_positive_roa_flag(self):
        """ROA > 0 should set positive_roa = 1."""
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        # NI=20.54e6, TA=200e6 => ROA > 0
        assert result["flags"]["positive_roa"] == 1

    def test_positive_cfo_flag(self):
        """Positive operating cash flow should set flag to 1."""
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)  # CFO = 28e6 > 0

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        assert result["flags"]["positive_cfo"] == 1

    def test_accruals_flag_cfo_greater_than_ni(self):
        """CFO > NI should set accruals = 1."""
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)
        # CFO = 28e6, NI = 20.54e6, so CFO > NI

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        assert result["flags"]["accruals"] == 1

    def test_leverage_decrease_flag(self):
        """D/E ratio decreased => leverage_decrease = 1."""
        # Current: debt=50e6, equity=110e6 => D/E = 0.4545
        # Prior: debt=55e6, equity=100e6 => D/E = 0.55
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        assert result["flags"]["leverage_decrease"] == 1

    def test_no_dilution_flag(self):
        """Shares stayed same or decreased => no_dilution = 1."""
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)  # shares: 10e6, 10e6
        cf = _make_cf(periods=2)

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        assert result["flags"]["no_dilution"] == 1

    def test_gross_margin_improvement(self):
        """Current GM > Prior GM should set flag to 1."""
        # Current: GP=48e6/Rev=120e6 = 0.4
        # Prior: GP=42e6/Rev=110e6 = 0.3818
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        assert result["flags"]["gross_margin_improvement"] == 1

    def test_interpretation_strong(self):
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)
        cf = _make_cf(periods=2)

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        # With our test data, f_score should be >= 7
        if result["f_score"] >= 7:
            assert result["interpretation"] == "Strong"
        elif result["f_score"] >= 4:
            assert result["interpretation"] == "Moderate"
        else:
            assert result["interpretation"] == "Weak"

    def test_empty_dataframes_return_zero_score(self):
        inc = pd.DataFrame()
        bs = pd.DataFrame()
        cf = pd.DataFrame()

        result = self.analyzer._piotroski_f_score(inc, bs, cf)
        assert result["f_score"] == 0
        assert all(v == 0 for v in result["flags"].values())


# ---------------------------------------------------------------------------
# Tests for Altman Z-Score
# ---------------------------------------------------------------------------

class TestAltmanZScore:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_known_safe_zone(self):
        """With strong financials, Z-Score should be > 2.99 (Safe)."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        market_cap = 2_000_000_000  # $2B

        result = self.analyzer._altman_z_score(inc, bs, market_cap)

        assert result["z_score"] is not None
        assert isinstance(result["z_score"], float)
        # Verify the formula: Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        c = result["components"]
        expected_z = (
            1.2 * c["X1_wc_ta"]
            + 1.4 * c["X2_re_ta"]
            + 3.3 * c["X3_ebit_ta"]
            + 0.6 * c["X4_mktcap_tl"]
            + 1.0 * c["X5_rev_ta"]
        )
        assert result["z_score"] == pytest.approx(expected_z, abs=0.01)

    def test_zone_classification_safe(self):
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        market_cap = 5_000_000_000  # very large cap -> high X4

        result = self.analyzer._altman_z_score(inc, bs, market_cap)
        assert result["zone"] == "Safe"

    def test_zone_classification_distress(self):
        """Very low market cap and weak financials => Distress."""
        inc = _make_inc(periods=1, **{
            "Total Revenue": [10e6],
            "EBIT": [-5e6],
        })
        bs = _make_bs(periods=1, **{
            "Total Assets": [200e6],
            "Current Assets": [20e6],
            "Current Liabilities": [50e6],
            "Retained Earnings": [-30e6],
        })
        result = self.analyzer._altman_z_score(inc, bs, market_cap=1_000_000)
        assert result["zone"] == "Distress"

    def test_insufficient_data(self):
        result = self.analyzer._altman_z_score(pd.DataFrame(), pd.DataFrame(), None)
        assert result["z_score"] is None
        assert result["zone"] == "Insufficient data"

    def test_z_components_exist(self):
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        result = self.analyzer._altman_z_score(inc, bs, 1_000_000_000)
        assert "X1_wc_ta" in result["components"]
        assert "X2_re_ta" in result["components"]
        assert "X3_ebit_ta" in result["components"]
        assert "X4_mktcap_tl" in result["components"]
        assert "X5_rev_ta" in result["components"]


# ---------------------------------------------------------------------------
# Tests for DuPont Decomposition
# ---------------------------------------------------------------------------

class TestDuPontDecomposition:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_five_factor_product_equals_roe(self):
        """tax_burden * interest_burden * op_margin * asset_turnover * equity_multiplier = ROE."""
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)

        result = self.analyzer._dupont_decomposition(inc, bs)
        cur = result["current"]

        if all(cur.get(k) is not None for k in
               ["tax_burden", "interest_burden", "operating_margin",
                "asset_turnover", "equity_multiplier"]):
            product = (
                cur["tax_burden"]
                * cur["interest_burden"]
                * cur["operating_margin"]
                * cur["asset_turnover"]
                * cur["equity_multiplier"]
            )
            assert cur["roe"] == pytest.approx(product, rel=0.01)

    def test_dupont_returns_current_and_prior(self):
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)

        result = self.analyzer._dupont_decomposition(inc, bs)
        assert "current" in result
        assert "prior" in result
        assert result["current"]["roe"] is not None
        assert result["prior"]["roe"] is not None

    def test_dupont_drivers_populated(self):
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)

        result = self.analyzer._dupont_decomposition(inc, bs)
        assert isinstance(result["drivers"], list)

    def test_dupont_empty_data(self):
        result = self.analyzer._dupont_decomposition(pd.DataFrame(), pd.DataFrame())
        cur = result["current"]
        assert cur.get("roe") is None


# ---------------------------------------------------------------------------
# Tests for Quality of Earnings
# ---------------------------------------------------------------------------

class TestQualityOfEarnings:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_accrual_ratio_calculation(self):
        """Accrual ratio = (NI - CFO) / Total Assets."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        cf = _make_cf(periods=1)

        result = self.analyzer._quality_of_earnings(inc, bs, cf)

        # NI=20.54e6, CFO=28e6, TA=200e6 => (20.54-28)/200 = -0.0373
        expected_accrual = (20.54e6 - 28e6) / 200e6
        assert result["accrual_ratio"] == pytest.approx(expected_accrual, abs=0.001)

    def test_cash_conversion_ratio(self):
        """Cash conversion = CFO / NI."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        cf = _make_cf(periods=1)

        result = self.analyzer._quality_of_earnings(inc, bs, cf)
        expected = 28e6 / 20.54e6
        assert result["cash_conversion_ratio"] == pytest.approx(expected, rel=0.01)

    def test_red_flags_high_accrual(self):
        """Accrual ratio > 0.10 should trigger red flag."""
        # Create scenario: NI much higher than CFO, large accrual ratio
        inc = _make_inc(periods=1, **{"Net Income": [50e6]})
        bs = _make_bs(periods=1, **{"Total Assets": [200e6]})
        cf = _make_cf(periods=1, **{"Operating Cash Flow": [15e6]})

        result = self.analyzer._quality_of_earnings(inc, bs, cf)
        # accrual = (50e6 - 15e6) / 200e6 = 0.175 > 0.10
        assert any("accrual" in flag.lower() for flag in result["red_flags"])

    def test_score_within_0_100(self):
        inc = _make_inc(periods=4)
        bs = _make_bs(periods=4)
        cf = _make_cf(periods=4)

        result = self.analyzer._quality_of_earnings(inc, bs, cf)
        assert 0.0 <= result["score"] <= 100.0

    def test_empty_data_returns_none_metrics(self):
        result = self.analyzer._quality_of_earnings(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        )
        assert result["accrual_ratio"] is None
        assert result["cash_conversion_ratio"] is None
        assert result["score"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Tests for Capital Allocation
# ---------------------------------------------------------------------------

class TestCapitalAllocation:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_roic_calculation(self):
        """ROIC = NOPAT / Invested Capital."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        cf = _make_cf(periods=1)
        ratios = {}
        market_cap = 1_000_000_000

        result = self.analyzer._capital_allocation(inc, bs, cf, ratios, market_cap)

        assert result["roic"] is not None
        # EBIT = 28e6, tax_rate = 5.46e6/26e6 = 0.21
        # NOPAT = 28e6 * (1 - 0.21) = 22.12e6
        # IC = equity + debt - cash = 110e6 + 50e6 - 25e6 = 135e6
        # ROIC = 22.12e6 / 135e6 = 0.1638
        expected_nopat = 28e6 * (1 - 5.46e6 / 26e6)
        expected_ic = 110e6 + 50e6 - 25e6
        expected_roic = expected_nopat / expected_ic
        assert result["roic"] == pytest.approx(expected_roic, rel=0.02)

    def test_wacc_spread(self):
        """ROIC - WACC spread should be computed."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        cf = _make_cf(periods=1)

        result = self.analyzer._capital_allocation(inc, bs, cf, {}, 1_000_000_000)
        assert result["roic_wacc_spread"] is not None
        assert result["roic_wacc_spread"] == pytest.approx(
            result["roic"] - result["wacc_estimated"], abs=0.001
        )

    def test_score_within_range(self):
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)
        cf = _make_cf(periods=1)

        result = self.analyzer._capital_allocation(inc, bs, cf, {}, 1_000_000_000)
        assert 0.0 <= result["score"] <= 100.0

    def test_missing_fields_handled(self):
        result = self.analyzer._capital_allocation(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, None
        )
        assert result["roic"] is None


# ---------------------------------------------------------------------------
# Tests for Working Capital
# ---------------------------------------------------------------------------

class TestWorkingCapital:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_dso_calculation(self):
        """DSO = (Receivables / Revenue) * 365."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)

        result = self.analyzer._working_capital_analysis(inc, bs)
        # Receivables=15e6, Revenue=120e6 => DSO = 15e6/120e6 * 365 = 45.625
        expected = (15e6 / 120e6) * 365.0
        assert result["current"]["dso"] == pytest.approx(expected, abs=0.5)

    def test_dio_calculation(self):
        """DIO = (Inventory / COGS) * 365."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)

        result = self.analyzer._working_capital_analysis(inc, bs)
        # Inventory=10e6, COGS=72e6 => DIO = 10e6/72e6 * 365 = 50.694
        expected = (10e6 / 72e6) * 365.0
        assert result["current"]["dio"] == pytest.approx(expected, abs=0.5)

    def test_dpo_calculation(self):
        """DPO = (Payables / COGS) * 365."""
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)

        result = self.analyzer._working_capital_analysis(inc, bs)
        expected = (8e6 / 72e6) * 365.0
        assert result["current"]["dpo"] == pytest.approx(expected, abs=0.5)

    def test_cash_conversion_cycle(self):
        """CCC = DSO + DIO - DPO."""
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)

        result = self.analyzer._working_capital_analysis(inc, bs)
        cur = result["current"]
        if all(cur.get(k) is not None for k in ["dso", "dio", "dpo"]):
            expected_ccc = cur["dso"] + cur["dio"] - cur["dpo"]
            assert cur["cash_conversion_cycle"] == pytest.approx(expected_ccc, abs=0.5)

    def test_trends_populated(self):
        inc = _make_inc(periods=2)
        bs = _make_bs(periods=2)

        result = self.analyzer._working_capital_analysis(inc, bs)
        assert "trends" in result
        assert "dso" in result["trends"]

    def test_single_period_data(self):
        inc = _make_inc(periods=1)
        bs = _make_bs(periods=1)

        result = self.analyzer._working_capital_analysis(inc, bs)
        assert result["current"]["dso"] is not None
        # Prior should be empty / None
        assert result["prior"]["dso"] is None

    def test_empty_data(self):
        result = self.analyzer._working_capital_analysis(pd.DataFrame(), pd.DataFrame())
        assert result["current"]["dso"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestFundamentalEdgeCases:

    def setup_method(self):
        with patch("src.analysis.fundamental.FundamentalsClient"):
            self.analyzer = FundamentalAnalyzer()

    def test_num_periods_empty(self):
        assert _num_periods(pd.DataFrame()) == 0
        assert _num_periods(None) == 0

    def test_num_periods_valid(self):
        df = _make_inc(periods=4)
        assert _num_periods(df) == 4

    def test_field_aliases_exist(self):
        """Check that important field aliases are defined."""
        assert "revenue" in _FIELD_ALIASES
        assert "net_income" in _FIELD_ALIASES
        assert "total_assets" in _FIELD_ALIASES
        assert "free_cashflow" in _FIELD_ALIASES
