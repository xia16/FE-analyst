"""Fundamental analysis engine -- institutional-quality multi-factor model.

Implements:
  * Piotroski F-Score  (9 binary signals, 0-9)
  * Altman Z-Score     (bankruptcy risk: Safe / Grey / Distress)
  * 5-Factor DuPont Decomposition  (ROE driver attribution)
  * Quality of Earnings  (accrual ratio, cash conversion, persistence)
  * Capital Allocation Efficiency  (ROIC, WACC spread, FCF yield)
  * Working Capital / Cash Conversion Cycle  (DSO, DIO, DPO trends)
  * Multi-Year Trend Analysis  (CAGR, inflection points, margin trajectory)
  * Enhanced Financial Health  (interest coverage, quick ratio, debt/EBITDA)
  * Comprehensive Composite Scoring  (weighted 0-100)
"""

from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.data_sources.fundamentals import FundamentalsClient
from src.utils.logger import setup_logger

logger = setup_logger("fundamental_analysis")


# ---------------------------------------------------------------------------
# yfinance field aliases -- financial-statement rows use inconsistent labels
# ---------------------------------------------------------------------------
_FIELD_ALIASES: dict[str, list[str]] = {
    # Income statement
    "revenue": ["Total Revenue", "Revenue", "Operating Revenue"],
    "cogs": [
        "Cost Of Revenue", "Cost of Revenue", "Reconciled Cost Of Revenue",
    ],
    "gross_profit": ["Gross Profit"],
    "operating_income": [
        "Operating Income", "Total Operating Income As Reported",
    ],
    "ebit": ["EBIT", "Ebit"],
    "ebitda": ["EBITDA", "Ebitda", "Normalized EBITDA"],
    "net_income": [
        "Net Income", "Net Income Common Stockholders",
        "Net Income From Continuing Operation Net Minority Interest",
    ],
    "pretax_income": ["Pretax Income", "Pre Tax Income"],
    "interest_expense": [
        "Interest Expense", "Interest Expense Non Operating",
        "Net Interest Income",
    ],
    "tax_provision": ["Tax Provision", "Income Tax Expense"],

    # Balance sheet
    "total_assets": ["Total Assets"],
    "total_liabilities": [
        "Total Liabilities Net Minority Interest", "Total Liabilities",
        "Total Liab",
    ],
    "shareholders_equity": [
        "Stockholders Equity", "Total Stockholder Equity",
        "Common Stock Equity", "Total Equity Gross Minority Interest",
    ],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "total_debt": [
        "Total Debt", "Long Term Debt And Capital Lease Obligation",
    ],
    "long_term_debt": [
        "Long Term Debt", "Long Term Debt And Capital Lease Obligation",
    ],
    "cash": [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash Financial", "Cash",
    ],
    "receivables": [
        "Net Receivables", "Accounts Receivable", "Receivables",
    ],
    "inventory": ["Inventory"],
    "payables": [
        "Accounts Payable", "Payables And Accrued Expenses",
        "Current Deferred Liabilities",
    ],
    "retained_earnings": ["Retained Earnings"],
    "working_capital": ["Working Capital"],
    "shares_issued": ["Ordinary Shares Number", "Share Issued"],

    # Cash flow
    "operating_cashflow": [
        "Operating Cash Flow", "Total Cash From Operating Activities",
        "Cash Flow From Continuing Operating Activities",
    ],
    "free_cashflow": ["Free Cash Flow"],
    "capex": ["Capital Expenditure", "Capital Expenditures"],
}


# ---------------------------------------------------------------------------
# Low-level extraction helpers
# ---------------------------------------------------------------------------

def _extract(
    df: pd.DataFrame | None,
    field_key: str,
    col_idx: int = 0,
) -> Optional[float]:
    """Safely pull a single numeric value from a financial-statement DataFrame.

    Args:
        df: yfinance financial statement (rows = line items, cols = dates,
            most-recent date first).
        field_key: Logical name mapped through ``_FIELD_ALIASES``.
        col_idx: Column ordinal (0 = most recent period).

    Returns:
        ``float`` value or ``None`` when unavailable.
    """
    if df is None or df.empty:
        return None
    if col_idx < 0 or col_idx >= len(df.columns):
        return None

    aliases = _FIELD_ALIASES.get(field_key, [field_key])
    for alias in aliases:
        if alias in df.index:
            try:
                row = df.loc[alias]
                # Duplicate index labels would give a DataFrame
                if isinstance(row, pd.DataFrame):
                    val = row.iloc[0, col_idx]
                else:
                    val = row.iloc[col_idx]
                if pd.notna(val):
                    return float(val)
            except (IndexError, ValueError, TypeError, KeyError):
                continue
    return None


def _safe_div(
    numerator: Optional[float],
    denominator: Optional[float],
    default: Optional[float] = None,
) -> Optional[float]:
    """Division that returns *default* when inputs are missing or denom is 0."""
    if numerator is None or denominator is None:
        return default
    if denominator == 0:
        return default
    return numerator / denominator


def _num_periods(df: pd.DataFrame | None) -> int:
    """Number of reporting periods (columns) available."""
    if df is None or df.empty:
        return 0
    return len(df.columns)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Restrict *value* to [lo, hi]."""
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class FundamentalAnalyzer:
    """Institutional-quality fundamental analysis engine.

    Fetches income statements, balance sheets, cash-flow statements, and
    summary ratios, then computes a comprehensive set of financial models
    and a composite score (0-100).
    """

    def __init__(self) -> None:
        self.client = FundamentalsClient()

    # ------------------------------------------------------------------ #
    # Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def analyze(self, ticker: str) -> dict[str, Any]:
        """Run the full suite of fundamental analyses.

        Returns a dict containing every sub-model plus a composite **score**
        (0-100) and backward-compatible ``health``, ``growth``, ``valuation``
        sub-dicts.
        """
        logger.info("Running institutional fundamental analysis: %s", ticker)

        # -- Fetch raw data --------------------------------------------- #
        ratios = self.client.get_key_ratios(ticker)
        profile = self.client.get_company_profile(ticker)
        inc = self.client.get_income_statement(ticker)
        bs = self.client.get_balance_sheet(ticker)
        cf = self.client.get_cash_flow(ticker)
        market_cap: Optional[float] = profile.get("market_cap")

        # -- Run every analysis module --------------------------------- #
        piotroski = self._piotroski_f_score(inc, bs, cf)
        altman = self._altman_z_score(inc, bs, market_cap)
        dupont = self._dupont_decomposition(inc, bs)
        quality = self._quality_of_earnings(inc, bs, cf)
        capital = self._capital_allocation(inc, bs, cf, ratios, market_cap)
        working = self._working_capital_analysis(inc, bs)
        trends = self._multi_year_trends(inc, bs, cf)
        health = self._assess_financial_health(ratios, inc, bs)
        growth = self._assess_growth(ratios, trends)
        valuation = self._assess_valuation(ratios, capital)

        # -- Composite score ------------------------------------------- #
        composite = self._comprehensive_score(
            health=health,
            growth=growth,
            quality=quality,
            capital=capital,
            valuation=valuation,
            piotroski=piotroski,
        )

        return {
            "ticker": ticker,
            "company": profile.get("name"),
            "sector": profile.get("sector"),
            "score": composite["composite_score"],
            # Backward-compatible keys consumed by scoring.py
            "health": health,
            "growth": growth,
            "valuation": valuation,
            # Extended analysis blocks
            "piotroski": piotroski,
            "altman_z": altman,
            "dupont": dupont,
            "quality_of_earnings": quality,
            "capital_allocation": capital,
            "working_capital": working,
            "trends": trends,
            "composite": composite,
            "ratios": ratios,
        }

    # ================================================================== #
    # 1.  Piotroski F-Score  (9 binary signals, total 0-9)                #
    # ================================================================== #

    def _piotroski_f_score(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
        cf: pd.DataFrame,
    ) -> dict[str, Any]:
        """Compute the Piotroski F-Score from three financial statements.

        Returns a dict with ``f_score`` (0-9), individual ``flags``,
        human-readable ``details``, and an ``interpretation`` string.
        """
        flags: dict[str, int] = {}
        details: dict[str, str] = {}

        # -- Extract current (0) and prior (1) period values ----------- #
        ni_0 = _extract(inc, "net_income", 0)
        ni_1 = _extract(inc, "net_income", 1)
        ta_0 = _extract(bs, "total_assets", 0)
        ta_1 = _extract(bs, "total_assets", 1)
        cfo_0 = _extract(cf, "operating_cashflow", 0)
        rev_0 = _extract(inc, "revenue", 0)
        rev_1 = _extract(inc, "revenue", 1)
        gp_0 = _extract(inc, "gross_profit", 0)
        gp_1 = _extract(inc, "gross_profit", 1)
        td_0 = _extract(bs, "total_debt", 0)
        td_1 = _extract(bs, "total_debt", 1)
        eq_0 = _extract(bs, "shareholders_equity", 0)
        eq_1 = _extract(bs, "shareholders_equity", 1)
        ca_0 = _extract(bs, "current_assets", 0)
        ca_1 = _extract(bs, "current_assets", 1)
        cl_0 = _extract(bs, "current_liabilities", 0)
        cl_1 = _extract(bs, "current_liabilities", 1)
        shares_0 = _extract(bs, "shares_issued", 0)
        shares_1 = _extract(bs, "shares_issued", 1)

        roa_0 = _safe_div(ni_0, ta_0)
        roa_1 = _safe_div(ni_1, ta_1)

        # -- Profitability (4 signals) --------------------------------- #

        # 1. Positive ROA
        if roa_0 is not None:
            flags["positive_roa"] = int(roa_0 > 0)
            details["positive_roa"] = f"ROA = {roa_0:.4f}"
        else:
            flags["positive_roa"] = 0
            details["positive_roa"] = "ROA unavailable"

        # 2. Positive operating cash flow
        if cfo_0 is not None:
            flags["positive_cfo"] = int(cfo_0 > 0)
            details["positive_cfo"] = f"CFO = {cfo_0:,.0f}"
        else:
            flags["positive_cfo"] = 0
            details["positive_cfo"] = "CFO unavailable"

        # 3. ROA improvement year-over-year
        if roa_0 is not None and roa_1 is not None:
            flags["roa_improvement"] = int(roa_0 > roa_1)
            details["roa_improvement"] = f"ROA {roa_1:.4f} -> {roa_0:.4f}"
        else:
            flags["roa_improvement"] = 0
            details["roa_improvement"] = "Insufficient ROA history"

        # 4. Accruals: CFO > Net Income (earnings backed by cash)
        if cfo_0 is not None and ni_0 is not None:
            flags["accruals"] = int(cfo_0 > ni_0)
            details["accruals"] = f"CFO = {cfo_0:,.0f} vs NI = {ni_0:,.0f}"
        else:
            flags["accruals"] = 0
            details["accruals"] = "Accrual data unavailable"

        # -- Leverage / Liquidity (3 signals) -------------------------- #

        # 5. Decrease in leverage (Debt / Equity)
        de_0 = _safe_div(td_0, eq_0)
        de_1 = _safe_div(td_1, eq_1)
        if de_0 is not None and de_1 is not None:
            flags["leverage_decrease"] = int(de_0 < de_1)
            details["leverage_decrease"] = f"D/E {de_1:.2f} -> {de_0:.2f}"
        else:
            flags["leverage_decrease"] = 0
            details["leverage_decrease"] = "Leverage data unavailable"

        # 6. Increase in current ratio
        cr_0 = _safe_div(ca_0, cl_0)
        cr_1 = _safe_div(ca_1, cl_1)
        if cr_0 is not None and cr_1 is not None:
            flags["current_ratio_increase"] = int(cr_0 > cr_1)
            details["current_ratio_increase"] = f"CR {cr_1:.2f} -> {cr_0:.2f}"
        else:
            flags["current_ratio_increase"] = 0
            details["current_ratio_increase"] = "Current ratio data unavailable"

        # 7. No new equity issuance (share count did not increase)
        if shares_0 is not None and shares_1 is not None:
            flags["no_dilution"] = int(shares_0 <= shares_1)
            details["no_dilution"] = f"Shares {shares_1:,.0f} -> {shares_0:,.0f}"
        else:
            flags["no_dilution"] = 0
            details["no_dilution"] = "Share count unavailable"

        # -- Operating Efficiency (2 signals) -------------------------- #

        # 8. Gross margin improvement
        gm_0 = _safe_div(gp_0, rev_0)
        gm_1 = _safe_div(gp_1, rev_1)
        if gm_0 is not None and gm_1 is not None:
            flags["gross_margin_improvement"] = int(gm_0 > gm_1)
            details["gross_margin_improvement"] = f"GM {gm_1:.2%} -> {gm_0:.2%}"
        else:
            flags["gross_margin_improvement"] = 0
            details["gross_margin_improvement"] = "Gross margin data unavailable"

        # 9. Asset turnover improvement
        at_0 = _safe_div(rev_0, ta_0)
        at_1 = _safe_div(rev_1, ta_1)
        if at_0 is not None and at_1 is not None:
            flags["asset_turnover_improvement"] = int(at_0 > at_1)
            details["asset_turnover_improvement"] = (
                f"AT {at_1:.3f} -> {at_0:.3f}"
            )
        else:
            flags["asset_turnover_improvement"] = 0
            details["asset_turnover_improvement"] = (
                "Asset turnover data unavailable"
            )

        f_score = sum(flags.values())
        return {
            "f_score": f_score,
            "max_score": 9,
            "flags": flags,
            "details": details,
            "interpretation": (
                "Strong" if f_score >= 7
                else "Moderate" if f_score >= 4
                else "Weak"
            ),
        }

    # ================================================================== #
    # 2.  Altman Z-Score                                                  #
    # ================================================================== #

    def _altman_z_score(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
        market_cap: Optional[float],
    ) -> dict[str, Any]:
        """Compute the Altman Z-Score for public manufacturing firms.

        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        Zones: >2.99 Safe, 1.81-2.99 Grey, <1.81 Distress.
        """
        ta = _extract(bs, "total_assets")
        tl = _extract(bs, "total_liabilities")
        ca = _extract(bs, "current_assets")
        cl = _extract(bs, "current_liabilities")
        re = _extract(bs, "retained_earnings")
        ebit = _extract(inc, "ebit")
        rev = _extract(inc, "revenue")

        if ta is None or ta == 0:
            return {
                "z_score": None,
                "zone": "Insufficient data",
                "components": {},
            }

        wc = (ca - cl) if (ca is not None and cl is not None) else None

        x1 = _safe_div(wc, ta, 0.0)
        x2 = _safe_div(re, ta, 0.0)
        x3 = _safe_div(ebit, ta, 0.0)
        x4 = (
            _safe_div(market_cap, tl, 0.0)
            if tl is not None and tl > 0
            else 0.0
        )
        x5 = _safe_div(rev, ta, 0.0)

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        if z > 2.99:
            zone = "Safe"
        elif z >= 1.81:
            zone = "Grey"
        else:
            zone = "Distress"

        return {
            "z_score": round(z, 3),
            "zone": zone,
            "components": {
                "X1_wc_ta": round(x1, 4),
                "X2_re_ta": round(x2, 4),
                "X3_ebit_ta": round(x3, 4),
                "X4_mktcap_tl": round(x4, 4),
                "X5_rev_ta": round(x5, 4),
            },
        }

    # ================================================================== #
    # 3.  DuPont 5-Factor Decomposition                                   #
    # ================================================================== #

    def _dupont_decomposition(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
    ) -> dict[str, Any]:
        """Decompose ROE into five multiplicative factors for two periods
        and identify which component is driving changes.

        ROE = Tax Burden x Interest Burden x Operating Margin
              x Asset Turnover x Equity Multiplier
        """
        results: dict[str, Any] = {"current": {}, "prior": {}, "drivers": []}

        for period_idx, label in [(0, "current"), (1, "prior")]:
            ni = _extract(inc, "net_income", period_idx)
            pretax = _extract(inc, "pretax_income", period_idx)
            ebit = _extract(inc, "ebit", period_idx)
            rev = _extract(inc, "revenue", period_idx)
            ta = _extract(bs, "total_assets", period_idx)
            eq = _extract(bs, "shareholders_equity", period_idx)

            tax_burden = _safe_div(ni, pretax)
            interest_burden = _safe_div(pretax, ebit)
            op_margin = _safe_div(ebit, rev)
            asset_turnover = _safe_div(rev, ta)
            equity_multiplier = _safe_div(ta, eq)

            components = [
                tax_burden, interest_burden, op_margin,
                asset_turnover, equity_multiplier,
            ]
            if all(c is not None for c in components):
                roe_computed = math.prod(components)
            else:
                roe_computed = _safe_div(ni, eq)

            results[label] = {
                "tax_burden": (
                    round(tax_burden, 4) if tax_burden is not None else None
                ),
                "interest_burden": (
                    round(interest_burden, 4)
                    if interest_burden is not None else None
                ),
                "operating_margin": (
                    round(op_margin, 4) if op_margin is not None else None
                ),
                "asset_turnover": (
                    round(asset_turnover, 4)
                    if asset_turnover is not None else None
                ),
                "equity_multiplier": (
                    round(equity_multiplier, 4)
                    if equity_multiplier is not None else None
                ),
                "roe": (
                    round(roe_computed, 4)
                    if roe_computed is not None else None
                ),
            }

        # Identify the biggest driver of ROE change
        cur = results["current"]
        pri = results["prior"]
        if cur.get("roe") is not None and pri.get("roe") is not None:
            component_keys = [
                "tax_burden", "interest_burden", "operating_margin",
                "asset_turnover", "equity_multiplier",
            ]
            changes: dict[str, float] = {}
            for key in component_keys:
                c_val = cur.get(key)
                p_val = pri.get(key)
                if (
                    c_val is not None
                    and p_val is not None
                    and p_val != 0
                ):
                    changes[key] = (c_val - p_val) / abs(p_val)

            if changes:
                sorted_keys = sorted(
                    changes, key=lambda k: abs(changes[k]), reverse=True,
                )
                for rank, key in enumerate(sorted_keys):
                    direction = (
                        "improved" if changes[key] > 0 else "deteriorated"
                    )
                    suffix = (
                        " (largest ROE driver)" if rank == 0 else ""
                    )
                    results["drivers"].append(
                        f"{key} {direction} by "
                        f"{abs(changes[key]):.1%}{suffix}"
                    )

        return results

    # ================================================================== #
    # 4.  Quality of Earnings                                             #
    # ================================================================== #

    def _quality_of_earnings(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
        cf: pd.DataFrame,
    ) -> dict[str, Any]:
        """Assess whether reported earnings are backed by real cash.

        Metrics:
          * Accrual Ratio  = (NI - CFO) / Total Assets  (lower is better)
          * Cash Conversion = CFO / NI  (>1 is good)
          * Earnings Persistence  (lag-1 autocorrelation of NI series)
        """
        ni_0 = _extract(inc, "net_income", 0)
        cfo_0 = _extract(cf, "operating_cashflow", 0)
        ta_0 = _extract(bs, "total_assets", 0)

        # Accrual ratio
        accrual_numerator: Optional[float] = None
        if ni_0 is not None and cfo_0 is not None:
            accrual_numerator = ni_0 - cfo_0
        accrual_ratio = _safe_div(accrual_numerator, ta_0)

        # Cash conversion
        cash_conversion = _safe_div(cfo_0, ni_0)

        # Red flags
        red_flags: list[str] = []
        if accrual_ratio is not None and accrual_ratio > 0.10:
            red_flags.append(
                f"High accrual ratio ({accrual_ratio:.3f} > 0.10): "
                "earnings may not be cash-backed"
            )
        if cash_conversion is not None and cash_conversion < 0.5:
            red_flags.append(
                f"Low cash conversion ({cash_conversion:.2f} < 0.50): "
                "poor cash quality"
            )

        # Earnings persistence: lag-1 autocorrelation of NI over periods
        n_periods = _num_periods(inc)
        earnings_series: list[float] = []
        for i in range(min(n_periods, 8)):
            ni = _extract(inc, "net_income", i)
            if ni is not None:
                earnings_series.append(ni)

        persistence: Optional[float] = None
        if len(earnings_series) >= 4:
            # Reverse to chronological order (oldest first)
            x = np.array(earnings_series[::-1], dtype=np.float64)
            if np.std(x) > 0:
                corr_matrix = np.corrcoef(x[:-1], x[1:])
                corr_val = corr_matrix[0, 1]
                if not np.isnan(corr_val):
                    persistence = round(float(corr_val), 4)

        # Score (0-100) starting from a neutral 50
        score = 50.0
        if accrual_ratio is not None:
            if accrual_ratio < 0.0:
                score += 20
            elif accrual_ratio < 0.05:
                score += 10
            elif accrual_ratio > 0.10:
                score -= 20
            elif accrual_ratio > 0.05:
                score -= 10
        if cash_conversion is not None:
            if cash_conversion > 1.2:
                score += 20
            elif cash_conversion > 1.0:
                score += 10
            elif cash_conversion < 0.5:
                score -= 20
            elif cash_conversion < 0.8:
                score -= 10
        if persistence is not None:
            if persistence > 0.8:
                score += 10
            elif persistence > 0.5:
                score += 5
            elif persistence < 0:
                score -= 10

        score = _clamp(score)

        return {
            "score": round(score, 1),
            "max_score": 100,
            "accrual_ratio": (
                round(accrual_ratio, 4)
                if accrual_ratio is not None else None
            ),
            "cash_conversion_ratio": (
                round(cash_conversion, 3)
                if cash_conversion is not None else None
            ),
            "earnings_persistence": persistence,
            "periods_analyzed": len(earnings_series),
            "red_flags": red_flags,
        }

    # ================================================================== #
    # 5.  Capital Allocation Efficiency                                   #
    # ================================================================== #

    def _capital_allocation(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
        cf: pd.DataFrame,
        ratios: dict[str, Any],
        market_cap: Optional[float],
    ) -> dict[str, Any]:
        """Compute ROIC, estimated WACC, ROIC-WACC spread, and FCF yield.

        NOPAT = EBIT * (1 - effective_tax_rate)
        Invested Capital = Equity + Total Debt - Cash
        ROIC = NOPAT / Invested Capital
        """
        ebit = _extract(inc, "ebit")
        tax_prov = _extract(inc, "tax_provision")
        pretax = _extract(inc, "pretax_income")
        eq = _extract(bs, "shareholders_equity")
        td = _extract(bs, "total_debt")
        cash = _extract(bs, "cash")
        fcf = _extract(cf, "free_cashflow")

        # Effective tax rate (clamp to reasonable range, fallback 21%)
        raw_tax_rate = _safe_div(tax_prov, pretax)
        if raw_tax_rate is not None and 0.0 <= raw_tax_rate <= 0.60:
            tax_rate = raw_tax_rate
        else:
            tax_rate = 0.21  # US statutory fallback

        # NOPAT
        nopat: Optional[float] = None
        if ebit is not None:
            nopat = ebit * (1.0 - tax_rate)

        # Invested Capital
        invested_capital: Optional[float] = None
        if eq is not None and td is not None and cash is not None:
            invested_capital = eq + td - cash
        elif eq is not None and td is not None:
            invested_capital = eq + td

        roic = _safe_div(nopat, invested_capital)

        # Estimated WACC (simplified model)
        interest_exp = _extract(inc, "interest_expense")
        cost_of_debt_pretax = _safe_div(
            abs(interest_exp) if interest_exp is not None else None,
            td,
        )
        if cost_of_debt_pretax is not None:
            cost_of_debt = cost_of_debt_pretax * (1.0 - tax_rate)
        else:
            cost_of_debt = 0.04  # fallback after-tax

        cost_of_equity = 0.10  # simplified: Rf + beta*ERP ~ 4.5% + 1*5.5%

        if (
            market_cap is not None
            and td is not None
            and (market_cap + td) > 0
        ):
            total_capital_val = market_cap + td
            weight_equity = market_cap / total_capital_val
            weight_debt = td / total_capital_val
            wacc = weight_equity * cost_of_equity + weight_debt * cost_of_debt
        else:
            wacc = 0.09  # fallback

        roic_wacc_spread: Optional[float] = None
        if roic is not None:
            roic_wacc_spread = roic - wacc

        # Enterprise Value = Market Cap + Debt - Cash
        ev: Optional[float] = None
        if market_cap is not None:
            ev = market_cap + (td or 0.0) - (cash or 0.0)

        fcf_yield: Optional[float] = None
        if fcf is not None and ev is not None and ev > 0:
            fcf_yield = fcf / ev

        # Score (0-100) from neutral 50
        score = 50.0
        if roic is not None:
            if roic > 0.20:
                score += 25
            elif roic > 0.12:
                score += 15
            elif roic > 0.08:
                score += 5
            elif roic < 0:
                score -= 25
            else:
                score -= 10
        if roic_wacc_spread is not None:
            if roic_wacc_spread > 0.10:
                score += 15
            elif roic_wacc_spread > 0.02:
                score += 8
            elif roic_wacc_spread < 0:
                score -= 15
        if fcf_yield is not None:
            if fcf_yield > 0.08:
                score += 10
            elif fcf_yield > 0.04:
                score += 5
            elif fcf_yield < 0:
                score -= 10

        score = _clamp(score)

        return {
            "score": round(score, 1),
            "max_score": 100,
            "roic": round(roic, 4) if roic is not None else None,
            "nopat": round(nopat, 0) if nopat is not None else None,
            "invested_capital": (
                round(invested_capital, 0)
                if invested_capital is not None else None
            ),
            "wacc_estimated": round(wacc, 4),
            "roic_wacc_spread": (
                round(roic_wacc_spread, 4)
                if roic_wacc_spread is not None else None
            ),
            "fcf_yield": (
                round(fcf_yield, 4) if fcf_yield is not None else None
            ),
            "enterprise_value": (
                round(ev, 0) if ev is not None else None
            ),
            "effective_tax_rate": round(tax_rate, 4),
        }

    # ================================================================== #
    # 6.  Working Capital Analysis                                        #
    # ================================================================== #

    def _working_capital_analysis(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
    ) -> dict[str, Any]:
        """Compute DSO, DIO, DPO, and Cash Conversion Cycle with YoY trend.

        DSO = (Receivables / Revenue) * 365
        DIO = (Inventory  / COGS)    * 365
        DPO = (Payables   / COGS)    * 365
        CCC = DSO + DIO - DPO
        """
        results: dict[str, Any] = {
            "current": {}, "prior": {}, "trends": {},
        }

        for period_idx, label in [(0, "current"), (1, "prior")]:
            recv = _extract(bs, "receivables", period_idx)
            inv = _extract(bs, "inventory", period_idx)
            pay = _extract(bs, "payables", period_idx)
            rev = _extract(inc, "revenue", period_idx)
            cogs = _extract(inc, "cogs", period_idx)

            dso: Optional[float] = None
            if recv is not None and rev is not None and rev > 0:
                dso = (recv / rev) * 365.0

            dio: Optional[float] = None
            if inv is not None and cogs is not None and cogs > 0:
                dio = (inv / cogs) * 365.0

            dpo: Optional[float] = None
            if pay is not None and cogs is not None and cogs > 0:
                dpo = (pay / cogs) * 365.0

            ccc: Optional[float] = None
            if dso is not None and dio is not None and dpo is not None:
                ccc = dso + dio - dpo

            results[label] = {
                "dso": round(dso, 1) if dso is not None else None,
                "dio": round(dio, 1) if dio is not None else None,
                "dpo": round(dpo, 1) if dpo is not None else None,
                "cash_conversion_cycle": (
                    round(ccc, 1) if ccc is not None else None
                ),
            }

        # YoY trend direction for each metric
        cur = results["current"]
        pri = results["prior"]
        for metric in ["dso", "dio", "dpo", "cash_conversion_cycle"]:
            c_val = cur.get(metric)
            p_val = pri.get(metric)
            if c_val is not None and p_val is not None:
                # For DSO and DIO: lower is better (improving)
                # For DPO: higher is better (improving -- holding cash longer)
                # For CCC: lower is better (improving)
                if metric == "dpo":
                    if c_val > p_val:
                        results["trends"][metric] = "improving"
                    elif c_val < p_val:
                        results["trends"][metric] = "deteriorating"
                    else:
                        results["trends"][metric] = "stable"
                else:
                    if c_val < p_val:
                        results["trends"][metric] = "improving"
                    elif c_val > p_val:
                        results["trends"][metric] = "deteriorating"
                    else:
                        results["trends"][metric] = "stable"
            else:
                results["trends"][metric] = "insufficient data"

        return results

    # ================================================================== #
    # 7.  Multi-Year Trend Analysis                                       #
    # ================================================================== #

    def _multi_year_trends(
        self,
        inc: pd.DataFrame,
        bs: pd.DataFrame,
        cf: pd.DataFrame,
    ) -> dict[str, Any]:
        """Track key metrics across all available periods.

        Computes CAGR for revenue and earnings, identifies inflection points
        (sign changes in growth), and classifies margin trajectory.
        """
        n = _num_periods(inc)
        if n == 0:
            return {
                "periods": 0,
                "revenue_cagr": None,
                "earnings_cagr": None,
                "gross_margin_trajectory": "unknown",
                "operating_margin_trajectory": "unknown",
            }

        # Collect time series in chronological order (oldest -> newest)
        revenue_ts: list[Optional[float]] = []
        ni_ts: list[Optional[float]] = []
        gm_ts: list[Optional[float]] = []
        om_ts: list[Optional[float]] = []
        roe_ts: list[Optional[float]] = []
        de_ts: list[Optional[float]] = []

        for i in range(n - 1, -1, -1):  # reverse to chronological
            rev = _extract(inc, "revenue", i)
            ni = _extract(inc, "net_income", i)
            gp = _extract(inc, "gross_profit", i)
            ebit_val = _extract(inc, "ebit", i)
            ta = _extract(bs, "total_assets", i)
            eq = _extract(bs, "shareholders_equity", i)
            td = _extract(bs, "total_debt", i)

            revenue_ts.append(rev)
            ni_ts.append(ni)
            gm_ts.append(_safe_div(gp, rev))
            om_ts.append(_safe_div(ebit_val, rev))
            roe_ts.append(_safe_div(ni, eq))
            de_ts.append(_safe_div(td, eq))

        # ---- CAGR helper ----
        def _cagr(series: list[Optional[float]]) -> Optional[float]:
            valid = [
                (idx, v)
                for idx, v in enumerate(series)
                if v is not None and v > 0
            ]
            if len(valid) < 2:
                return None
            first_idx, first_val = valid[0]
            last_idx, last_val = valid[-1]
            years = last_idx - first_idx
            if years <= 0 or first_val <= 0:
                return None
            return (last_val / first_val) ** (1.0 / years) - 1.0

        revenue_cagr = _cagr(revenue_ts)
        earnings_cagr = _cagr(ni_ts)

        # ---- Margin trajectory ----
        def _trajectory(series: list[Optional[float]]) -> str:
            valid = [v for v in series if v is not None]
            if len(valid) < 3:
                return "insufficient data"
            mid = len(valid) // 2
            first_half_avg = float(np.mean(valid[:mid]))
            second_half_avg = float(np.mean(valid[mid:]))
            if second_half_avg > first_half_avg + 0.01:
                return "expanding"
            if second_half_avg < first_half_avg - 0.01:
                return "contracting"
            return "stable"

        gm_traj = _trajectory(gm_ts)
        om_traj = _trajectory(om_ts)

        # ---- Inflection points: sign changes in YoY revenue growth ----
        rev_growth: list[Optional[float]] = []
        for i in range(1, len(revenue_ts)):
            prev = revenue_ts[i - 1]
            curr = revenue_ts[i]
            if (
                curr is not None
                and prev is not None
                and prev != 0
            ):
                rev_growth.append((curr - prev) / abs(prev))
            else:
                rev_growth.append(None)

        inflection_count = 0
        for i in range(1, len(rev_growth)):
            g_curr = rev_growth[i]
            g_prev = rev_growth[i - 1]
            if g_curr is not None and g_prev is not None:
                if (g_curr > 0) != (g_prev > 0):
                    inflection_count += 1

        def _round_series(
            series: list[Optional[float]], decimals: int = 4,
        ) -> list[Optional[float]]:
            return [
                round(v, decimals) if v is not None else None
                for v in series
            ]

        return {
            "periods": n,
            "revenue_cagr": (
                round(revenue_cagr, 4)
                if revenue_cagr is not None else None
            ),
            "earnings_cagr": (
                round(earnings_cagr, 4)
                if earnings_cagr is not None else None
            ),
            "gross_margin_trajectory": gm_traj,
            "operating_margin_trajectory": om_traj,
            "revenue_inflections": inflection_count,
            "revenue_series": _round_series(revenue_ts, 0),
            "net_income_series": _round_series(ni_ts, 0),
            "gross_margin_series": _round_series(gm_ts),
            "operating_margin_series": _round_series(om_ts),
            "roe_series": _round_series(roe_ts),
            "debt_equity_series": _round_series(de_ts),
        }

    # ================================================================== #
    # 8.  Enhanced Financial Health                                       #
    # ================================================================== #

    def _assess_financial_health(
        self,
        ratios: dict[str, Any],
        inc: pd.DataFrame,
        bs: pd.DataFrame,
    ) -> dict[str, Any]:
        """Score financial health from balance-sheet strength ratios.

        Evaluates: current ratio, quick ratio, D/E, ROE, interest coverage,
        Debt/EBITDA, and cash ratio.  Returns a score/max_score pair plus
        a ``normalized`` 0-100 value for the composite scorer.
        """
        score = 0
        max_score = 14
        reasons: list[str] = []

        # ---- Current ratio ----
        cr = ratios.get("current_ratio")
        if cr is None:
            ca = _extract(bs, "current_assets")
            cl = _extract(bs, "current_liabilities")
            cr = _safe_div(ca, cl)
        if cr is not None:
            if cr > 2.0:
                score += 2
                reasons.append(f"Strong current ratio: {cr:.2f}")
            elif cr > 1.5:
                score += 2
                reasons.append(f"Good current ratio: {cr:.2f}")
            elif cr > 1.0:
                score += 1
                reasons.append(f"Adequate current ratio: {cr:.2f}")
            else:
                reasons.append(f"Weak current ratio: {cr:.2f}")

        # ---- Quick ratio ----
        qr = ratios.get("quick_ratio")
        if qr is None:
            ca = _extract(bs, "current_assets")
            inv = _extract(bs, "inventory")
            cl = _extract(bs, "current_liabilities")
            if ca is not None and cl is not None and cl != 0:
                inv_val = inv if inv is not None else 0.0
                qr = (ca - inv_val) / cl
        if qr is not None:
            if qr > 1.5:
                score += 2
                reasons.append(f"Strong quick ratio: {qr:.2f}")
            elif qr > 1.0:
                score += 1
                reasons.append(f"Adequate quick ratio: {qr:.2f}")
            else:
                reasons.append(f"Weak quick ratio: {qr:.2f}")

        # ---- Debt / Equity ----
        de = ratios.get("debt_to_equity")
        if de is not None:
            if de < 50:
                score += 2
                reasons.append(f"Low debt/equity: {de:.1f}%")
            elif de < 100:
                score += 1
                reasons.append(f"Moderate debt/equity: {de:.1f}%")
            else:
                reasons.append(f"High debt/equity: {de:.1f}%")

        # ---- ROE ----
        roe = ratios.get("roe")
        if roe is not None:
            if roe > 0.20:
                score += 2
                reasons.append(f"Excellent ROE: {roe:.1%}")
            elif roe > 0.12:
                score += 2
                reasons.append(f"Strong ROE: {roe:.1%}")
            elif roe > 0.08:
                score += 1
                reasons.append(f"Adequate ROE: {roe:.1%}")
            else:
                reasons.append(f"Weak ROE: {roe:.1%}")

        # ---- Interest Coverage (EBIT / |Interest Expense|) ----
        ebit = _extract(inc, "ebit")
        int_exp = _extract(inc, "interest_expense")
        interest_coverage: Optional[float] = None
        if ebit is not None and int_exp is not None and int_exp != 0:
            interest_coverage = ebit / abs(int_exp)
            if interest_coverage > 10:
                score += 2
                reasons.append(
                    f"Excellent interest coverage: {interest_coverage:.1f}x"
                )
            elif interest_coverage > 5:
                score += 2
                reasons.append(
                    f"Strong interest coverage: {interest_coverage:.1f}x"
                )
            elif interest_coverage > 2:
                score += 1
                reasons.append(
                    f"Adequate interest coverage: {interest_coverage:.1f}x"
                )
            else:
                reasons.append(
                    f"Weak interest coverage: {interest_coverage:.1f}x"
                )

        # ---- Debt / EBITDA ----
        ebitda = _extract(inc, "ebitda")
        td = _extract(bs, "total_debt")
        debt_ebitda: Optional[float] = None
        if td is not None and ebitda is not None and ebitda > 0:
            debt_ebitda = td / ebitda
            if debt_ebitda < 1.5:
                score += 2
                reasons.append(f"Low Debt/EBITDA: {debt_ebitda:.1f}x")
            elif debt_ebitda < 3.0:
                score += 1
                reasons.append(f"Moderate Debt/EBITDA: {debt_ebitda:.1f}x")
            else:
                reasons.append(f"High Debt/EBITDA: {debt_ebitda:.1f}x")

        # ---- Cash ratio ----
        cash_val = _extract(bs, "cash")
        cl_val = _extract(bs, "current_liabilities")
        cash_ratio = _safe_div(cash_val, cl_val)
        if cash_ratio is not None:
            if cash_ratio > 0.5:
                score += 2
                reasons.append(f"Strong cash ratio: {cash_ratio:.2f}")
            elif cash_ratio > 0.2:
                score += 1
                reasons.append(f"Adequate cash ratio: {cash_ratio:.2f}")
            else:
                reasons.append(f"Low cash ratio: {cash_ratio:.2f}")

        return {
            "score": score,
            "max_score": max_score,
            "normalized": round(score / max(max_score, 1) * 100, 1),
            "reasons": reasons,
            "metrics": {
                "current_ratio": (
                    round(cr, 2) if cr is not None else None
                ),
                "quick_ratio": (
                    round(qr, 2) if qr is not None else None
                ),
                "interest_coverage": (
                    round(interest_coverage, 2)
                    if interest_coverage is not None else None
                ),
                "debt_ebitda": (
                    round(debt_ebitda, 2)
                    if debt_ebitda is not None else None
                ),
                "cash_ratio": (
                    round(cash_ratio, 2) if cash_ratio is not None else None
                ),
            },
        }

    # ================================================================== #
    # Growth Profile                                                      #
    # ================================================================== #

    def _assess_growth(
        self,
        ratios: dict[str, Any],
        trends: dict[str, Any],
    ) -> dict[str, Any]:
        """Score growth profile using recent growth rates and multi-year CAGR.

        Returns score/max_score for backward compatibility and a normalized
        0-100 value.
        """
        score = 0
        max_score = 8
        reasons: list[str] = []

        # Recent revenue growth
        rev_g = ratios.get("revenue_growth")
        if rev_g is not None:
            if rev_g > 0.20:
                score += 2
                reasons.append(f"Strong revenue growth: {rev_g:.1%}")
            elif rev_g > 0.08:
                score += 1
                reasons.append(f"Moderate revenue growth: {rev_g:.1%}")
            else:
                reasons.append(f"Low revenue growth: {rev_g:.1%}")

        # Recent earnings growth
        earn_g = ratios.get("earnings_growth")
        if earn_g is not None:
            if earn_g > 0.20:
                score += 2
                reasons.append(f"Strong earnings growth: {earn_g:.1%}")
            elif earn_g > 0.08:
                score += 1
                reasons.append(f"Moderate earnings growth: {earn_g:.1%}")
            else:
                reasons.append(f"Low earnings growth: {earn_g:.1%}")

        # Multi-year revenue CAGR
        rev_cagr = trends.get("revenue_cagr")
        if rev_cagr is not None:
            if rev_cagr > 0.15:
                score += 2
                reasons.append(
                    f"Strong multi-year revenue CAGR: {rev_cagr:.1%}"
                )
            elif rev_cagr > 0.05:
                score += 1
                reasons.append(
                    f"Moderate multi-year revenue CAGR: {rev_cagr:.1%}"
                )
            else:
                reasons.append(
                    f"Low multi-year revenue CAGR: {rev_cagr:.1%}"
                )

        # Margin trajectory
        gm_traj = trends.get("gross_margin_trajectory", "unknown")
        if gm_traj == "expanding":
            score += 2
            reasons.append("Gross margins expanding")
        elif gm_traj == "stable":
            score += 1
            reasons.append("Gross margins stable")
        elif gm_traj == "contracting":
            reasons.append("Gross margins contracting")

        return {
            "score": score,
            "max_score": max_score,
            "normalized": round(score / max(max_score, 1) * 100, 1),
            "reasons": reasons,
        }

    # ================================================================== #
    # Valuation Assessment                                                #
    # ================================================================== #

    def _assess_valuation(
        self,
        ratios: dict[str, Any],
        capital: dict[str, Any],
    ) -> dict[str, Any]:
        """Score relative valuation using multiples and FCF yield.

        Returns score/max_score for backward compatibility and a normalized
        0-100 value.
        """
        score = 0
        max_score = 8
        reasons: list[str] = []

        # Forward P/E
        pe = ratios.get("pe_forward")
        if pe is not None and pe > 0:
            if pe < 12:
                score += 2
                reasons.append(f"Low forward P/E: {pe:.1f}")
            elif pe < 20:
                score += 1
                reasons.append(f"Moderate forward P/E: {pe:.1f}")
            else:
                reasons.append(f"High forward P/E: {pe:.1f}")

        # PEG ratio
        peg = ratios.get("peg_ratio")
        if peg is not None:
            if 0 < peg < 1:
                score += 2
                reasons.append(f"Attractive PEG: {peg:.2f}")
            elif 0 < peg < 2:
                score += 1
                reasons.append(f"Fair PEG: {peg:.2f}")
            else:
                reasons.append(f"Expensive PEG: {peg:.2f}")

        # EV / EBITDA
        ev_ebitda = ratios.get("ev_ebitda")
        if ev_ebitda is not None and ev_ebitda > 0:
            if ev_ebitda < 10:
                score += 2
                reasons.append(f"Low EV/EBITDA: {ev_ebitda:.1f}")
            elif ev_ebitda < 18:
                score += 1
                reasons.append(f"Moderate EV/EBITDA: {ev_ebitda:.1f}")
            else:
                reasons.append(f"High EV/EBITDA: {ev_ebitda:.1f}")

        # FCF Yield
        fcf_yield = capital.get("fcf_yield")
        if fcf_yield is not None:
            if fcf_yield > 0.06:
                score += 2
                reasons.append(f"Strong FCF Yield: {fcf_yield:.1%}")
            elif fcf_yield > 0.03:
                score += 1
                reasons.append(f"Moderate FCF Yield: {fcf_yield:.1%}")
            else:
                reasons.append(f"Low FCF Yield: {fcf_yield:.1%}")

        return {
            "score": score,
            "max_score": max_score,
            "normalized": round(score / max(max_score, 1) * 100, 1),
            "reasons": reasons,
        }

    # ================================================================== #
    # 9.  Comprehensive Composite Score  (0-100)                          #
    # ================================================================== #

    def _comprehensive_score(
        self,
        health: dict[str, Any],
        growth: dict[str, Any],
        quality: dict[str, Any],
        capital: dict[str, Any],
        valuation: dict[str, Any],
        piotroski: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine all sub-scores into a single 0-100 composite.

        Weights:
          Financial Health   20%
          Growth Profile     15%
          Quality of Earnings 20%
          Capital Efficiency  20%
          Valuation           15%
          Piotroski           10%
        """
        # Normalize each sub-score to 0-100
        health_norm = health.get(
            "normalized",
            health["score"] / max(health["max_score"], 1) * 100,
        )
        growth_norm = growth.get(
            "normalized",
            growth["score"] / max(growth["max_score"], 1) * 100,
        )
        quality_norm = quality.get("score", 50.0)
        capital_norm = capital.get("score", 50.0)
        valuation_norm = valuation.get(
            "normalized",
            valuation["score"] / max(valuation["max_score"], 1) * 100,
        )
        piotroski_norm = (
            piotroski["f_score"] / max(piotroski["max_score"], 1) * 100
        )

        weights = {
            "financial_health": 0.20,
            "growth_profile": 0.15,
            "quality_of_earnings": 0.20,
            "capital_efficiency": 0.20,
            "valuation": 0.15,
            "piotroski": 0.10,
        }

        sub_scores = {
            "financial_health": round(health_norm, 1),
            "growth_profile": round(growth_norm, 1),
            "quality_of_earnings": round(quality_norm, 1),
            "capital_efficiency": round(capital_norm, 1),
            "valuation": round(valuation_norm, 1),
            "piotroski": round(piotroski_norm, 1),
        }

        composite = sum(sub_scores[k] * weights[k] for k in weights)
        composite = round(_clamp(composite), 1)

        return {
            "composite_score": composite,
            "sub_scores": sub_scores,
            "weights": weights,
        }


# ---------------------------------------------------------------------------
# Plugin adapter for pipeline
# ---------------------------------------------------------------------------
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer  # noqa: E402


class FundamentalAnalyzerPlugin(_BaseAnalyzer):
    """Pipeline-compatible adapter wrapping :class:`FundamentalAnalyzer`.

    Conforms to the ``BaseAnalyzer`` interface: ``analyze(ticker, ctx)``
    returns a dict whose ``"score"`` key is a 0-100 composite value.
    """

    name = "fundamental"
    default_weight = 0.25

    def __init__(self) -> None:
        self._analyzer = FundamentalAnalyzer()

    def analyze(self, ticker: str, ctx: Any) -> dict[str, Any]:
        """Run full fundamental analysis and return scored result."""
        result = self._analyzer.analyze(ticker)
        # "score" is already set by _comprehensive_score; ensure it is present
        if "score" not in result:
            health = result["health"]
            growth = result["growth"]
            val = result["valuation"]
            h = health["score"] / max(health["max_score"], 1)
            g = growth["score"] / max(growth["max_score"], 1)
            v = val["score"] / max(val["max_score"], 1)
            result["score"] = round(
                (h * 0.4 + g * 0.3 + v * 0.3) * 100, 1,
            )
        return result
