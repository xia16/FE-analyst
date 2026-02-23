"""Valuation models - Two-stage DCF, reverse DCF, comparables, analyst targets.

Institutional-grade valuation engine with proper WACC (debt + equity),
two-stage growth projection, dual terminal value methods, probability-weighted
scenario analysis, and reverse DCF implied growth calculation.
"""

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from src.data_sources.fundamentals import FundamentalsClient
from src.data_sources.macro_data import MacroDataClient
from src.utils.logger import setup_logger

logger = setup_logger("valuation")

# Country risk premiums for WACC calculation
COUNTRY_PREMIUM = {
    "United States": 0.0,
    "Japan": 0.015,
    "Taiwan": 0.03,
    "South Korea": 0.02,
    "Netherlands": 0.005,
    "France": 0.005,
    "Germany": 0.005,
    "China": 0.025,
    "Israel": 0.015,
}

# Country-adjusted terminal growth rates
TERMINAL_GROWTH_BY_COUNTRY = {
    "Japan": 0.020,
    "United States": 0.030,
    "Netherlands": 0.025,
    "Taiwan": 0.025,
    "South Korea": 0.025,
    "France": 0.025,
    "Germany": 0.025,
    "China": 0.025,
}

# Default exit multiples (EV/EBITDA) by sector
SECTOR_EXIT_MULTIPLES = {
    "Technology": 18,
    "Semiconductors": 15,
    "Communication Services": 16,
    "Consumer Cyclical": 12,
    "Consumer Defensive": 14,
    "Healthcare": 16,
    "Industrials": 12,
    "Financial Services": 10,
    "Energy": 8,
    "Utilities": 10,
    "Real Estate": 14,
    "Basic Materials": 10,
}

DEFAULT_EXIT_MULTIPLE = 13


class ValuationAnalyzer:
    """Estimate intrinsic value using multiple methods."""

    def __init__(self):
        self.fundamentals = FundamentalsClient()
        self.macro = MacroDataClient()

    # ------------------------------------------------------------------
    # Growth estimation
    # ------------------------------------------------------------------

    def _estimate_growth_rate(self, ticker: str) -> dict:
        """Estimate FCF growth rate from multiple sources.

        Uses revenue growth and earnings growth as primary signals.
        Historical FCF CAGR is only included when positive (FCF is too
        volatile for capex-heavy companies like AMZN/GOOG to use negative CAGR).
        """
        sources = {}

        # Source 1: Historical FCF CAGR (3-year, only if positive both ends)
        try:
            cf = self.fundamentals.get_cash_flow(ticker)
            if not cf.empty and "Free Cash Flow" in cf.index:
                fcf_row = cf.loc["Free Cash Flow"].dropna()
                if len(fcf_row) >= 3:
                    recent = float(fcf_row.iloc[0])
                    older = float(fcf_row.iloc[min(2, len(fcf_row) - 1)])
                    if older > 0 and recent > 0:
                        years = min(2, len(fcf_row) - 1)
                        cagr = (recent / older) ** (1.0 / years) - 1
                        # Only include if CAGR is plausible (FCF can swing wildly)
                        if cagr > -0.20:
                            sources["historical_fcf_cagr"] = cagr
        except Exception as e:
            logger.debug("FCF CAGR failed for %s: %s", ticker, e)

        # Source 2: Revenue growth from yfinance
        ratios = {}
        try:
            ratios = self.fundamentals.get_key_ratios(ticker)
            rg = ratios.get("revenue_growth")
            if rg is not None:
                sources["revenue_growth"] = float(rg)
        except Exception as e:
            logger.debug("Revenue growth failed for %s: %s", ticker, e)

        # Source 3: Earnings growth from yfinance
        try:
            eg = ratios.get("earnings_growth")
            if eg is not None:
                sources["earnings_growth"] = float(eg)
        except Exception:
            pass

        if not sources:
            return {"growth_rate": 0.08, "source": "default", "sources": {}}

        # Use median of available sources, capped to reasonable range
        vals = list(sources.values())
        selected = float(np.median(vals))
        selected = max(-0.05, min(0.30, selected))

        return {
            "growth_rate": round(selected, 4),
            "source": "multi_source_median",
            "sources": {k: round(v, 4) for k, v in sources.items()},
        }

    # ------------------------------------------------------------------
    # Tax rate estimation
    # ------------------------------------------------------------------

    def _estimate_tax_rate(self, ticker: str) -> float:
        """Estimate effective tax rate from income statement.

        Computes tax_provision / pretax_income from the most recent annual
        income statement.  Falls back to 21% (US statutory) on failure.
        """
        try:
            inc = self.fundamentals.get_income_statement(ticker)
            if inc.empty:
                return 0.21

            pretax = None
            for key in ["Pretax Income", "Income Before Tax", "EBIT"]:
                if key in inc.index:
                    val = inc.loc[key].iloc[0]
                    if pd.notna(val) and float(val) != 0:
                        pretax = float(val)
                        break

            tax_provision = None
            for key in ["Tax Provision", "Income Tax Expense", "Tax Effect Of Unusual Items"]:
                if key in inc.index:
                    val = inc.loc[key].iloc[0]
                    if pd.notna(val):
                        tax_provision = float(val)
                        break

            if pretax and tax_provision is not None and pretax > 0:
                rate = tax_provision / pretax
                # Clamp to reasonable range (0% - 40%)
                return max(0.0, min(0.40, rate))
        except Exception as e:
            logger.debug("Tax rate estimation failed for %s: %s", ticker, e)

        return 0.21

    # ------------------------------------------------------------------
    # WACC calculation (CAPM-based with debt component)
    # ------------------------------------------------------------------

    def _compute_wacc(self, ticker: str) -> dict:
        """Compute WACC = Ke * (E/(E+D)) + Kd * (1-t) * (D/(E+D)).

        Uses CAPM for cost of equity and interest_expense / total_debt for
        cost of debt.  Falls back to WACC ~ Ke when debt data is unavailable.
        """
        import yfinance as yf
        from src.analysis.risk import RiskAnalyzer

        risk_free = self.macro.get_risk_free_rate()
        erp = 0.06  # equity risk premium

        # Get beta
        beta = 1.0
        try:
            risk_result = RiskAnalyzer().analyze(ticker)
            beta = risk_result.get("beta", 1.0)
            if beta is None or beta == 0:
                beta = 1.0
        except Exception as e:
            logger.warning("Beta calculation failed for %s: %s", ticker, e)

        # Country premium
        country = "United States"
        try:
            profile = self.fundamentals.get_company_profile(ticker)
            country = profile.get("country", "United States") or "United States"
        except Exception:
            pass
        country_prem = COUNTRY_PREMIUM.get(country, 0.01)

        # Cost of equity (CAPM)
        cost_of_equity = risk_free + beta * erp + country_prem

        # Terminal growth (country-adjusted)
        terminal_growth = TERMINAL_GROWTH_BY_COUNTRY.get(country, 0.025)

        # ----- Debt-weighted WACC computation -----
        cost_of_debt = 0.0
        tax_rate = 0.21
        equity_weight = 1.0
        debt_weight = 0.0
        wacc = cost_of_equity  # default: all-equity

        try:
            info = yf.Ticker(ticker).info
            # Use financial debt only (excludes operating lease liabilities)
            financial_debt = info.get("longTermDebt", 0) or 0
            if financial_debt == 0:
                financial_debt = info.get("totalDebt", 0) or 0
            market_cap = info.get("marketCap", 0) or 0
            interest_expense = abs(info.get("interestExpense", 0) or 0)

            if financial_debt > 0 and market_cap > 0:
                # Cost of debt = interest expense / financial debt
                if interest_expense > 0:
                    cost_of_debt = interest_expense / financial_debt
                    # Clamp to reasonable range (1% - 15%)
                    cost_of_debt = max(0.01, min(0.15, cost_of_debt))
                else:
                    # No interest data; approximate with risk-free + 2% spread
                    cost_of_debt = risk_free + 0.02

                # Effective tax rate
                tax_rate = self._estimate_tax_rate(ticker)

                # Capital structure weights
                total_capital = market_cap + financial_debt
                equity_weight = market_cap / total_capital
                debt_weight = financial_debt / total_capital

                # WACC = Ke * (E/(E+D)) + Kd * (1-t) * (D/(E+D))
                wacc = (
                    cost_of_equity * equity_weight
                    + cost_of_debt * (1 - tax_rate) * debt_weight
                )
            else:
                # No meaningful debt: WACC = Ke (all-equity assumption)
                logger.debug(
                    "%s: no debt data available, using all-equity WACC", ticker
                )
        except Exception as e:
            logger.warning("Debt-weighted WACC failed for %s, using Ke: %s", ticker, e)

        return {
            "risk_free_rate": round(risk_free, 4),
            "beta": round(beta, 3),
            "equity_risk_premium": erp,
            "country_premium": country_prem,
            "country": country,
            "cost_of_equity": round(cost_of_equity, 4),
            "cost_of_debt": round(cost_of_debt, 4),
            "tax_rate": round(tax_rate, 4),
            "equity_weight": round(equity_weight, 4),
            "debt_weight": round(debt_weight, 4),
            "wacc": round(wacc, 4),
            "terminal_growth": round(terminal_growth, 4),
        }

    # ------------------------------------------------------------------
    # Net debt adjustment (EV -> Equity Value)
    # ------------------------------------------------------------------

    def _net_debt_adjustment(self, ticker: str) -> dict:
        """Calculate net debt: Financial Debt - Cash & Equivalents.

        Uses *financial* debt only (Long Term Debt + Current Debt), excluding
        operating lease liabilities which yfinance bundles into "Total Debt".
        For cash, prefers Cash + Short Term Investments (broader liquidity).
        """
        try:
            bs = self.fundamentals.get_balance_sheet(ticker)
            if bs.empty:
                return {"total_debt": 0, "cash": 0, "net_debt": 0, "note": "No balance sheet data"}

            # --- Financial debt (exclude lease liabilities) ---
            long_term_debt = 0
            for key in ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]:
                if key in bs.index:
                    val = bs.loc[key].iloc[0]
                    if pd.notna(val):
                        long_term_debt = float(val)
                        break

            # If we got the lease-inflated figure, try to subtract leases
            if long_term_debt > 0:
                pure_lt = bs.loc["Long Term Debt"].iloc[0] if "Long Term Debt" in bs.index else None
                if pure_lt is not None and pd.notna(pure_lt) and float(pure_lt) > 0:
                    long_term_debt = float(pure_lt)

            current_debt = 0
            for key in ["Current Debt", "Current Debt And Capital Lease Obligation",
                        "Short Long Term Debt", "Current Long Term Debt"]:
                if key in bs.index:
                    val = bs.loc[key].iloc[0]
                    if pd.notna(val):
                        current_debt = float(val)
                        break

            total_debt = long_term_debt + current_debt

            # --- Cash & liquid assets ---
            cash = 0
            # Prefer broader measure (cash + short-term investments)
            for key in ["Cash Cash Equivalents And Short Term Investments",
                        "Cash And Cash Equivalents", "Cash"]:
                if key in bs.index:
                    val = bs.loc[key].iloc[0]
                    if pd.notna(val):
                        cash = float(val)
                        break

            return {
                "total_debt": total_debt,
                "long_term_debt": long_term_debt,
                "current_debt": current_debt,
                "cash": cash,
                "net_debt": total_debt - cash,
                "note": "Balance sheet sourced (financial debt only, excl. lease liabilities)",
            }
        except Exception as e:
            logger.warning("Net debt failed for %s: %s", ticker, e)
            return {"total_debt": 0, "cash": 0, "net_debt": 0, "note": f"Error: {e}"}

    # ------------------------------------------------------------------
    # Two-stage FCF projection
    # ------------------------------------------------------------------

    def _project_two_stage_fcf(
        self, current_fcf: float, growth_rate: float, terminal_growth: float,
        stage1_years: int = 5, stage2_years: int = 5,
    ) -> list[dict]:
        """Project FCFs using a two-stage model.

        Stage 1 (years 1-5): constant growth at growth_rate.
        Stage 2 (years 6-10): linear fade from growth_rate to terminal_growth.

        Returns a list of dicts: [{year, growth, fcf}, ...]
        """
        projections = []
        prev_fcf = current_fcf

        # Stage 1: high growth
        for yr in range(1, stage1_years + 1):
            fcf = prev_fcf * (1 + growth_rate)
            projections.append({
                "year": yr,
                "stage": 1,
                "growth_rate": round(growth_rate, 4),
                "fcf": fcf,
            })
            prev_fcf = fcf

        # Stage 2: linear fade from growth_rate -> terminal_growth
        for i in range(stage2_years):
            yr = stage1_years + 1 + i
            # Linear interpolation
            fade_fraction = (i + 1) / stage2_years
            faded_growth = growth_rate + (terminal_growth - growth_rate) * fade_fraction
            fcf = prev_fcf * (1 + faded_growth)
            projections.append({
                "year": yr,
                "stage": 2,
                "growth_rate": round(faded_growth, 4),
                "fcf": fcf,
            })
            prev_fcf = fcf

        return projections

    # ------------------------------------------------------------------
    # Terminal value: dual method (Gordon Growth + Exit Multiple)
    # ------------------------------------------------------------------

    def _compute_terminal_value(
        self, final_fcf: float, terminal_growth: float, wacc: float,
        ticker: str, peer_ev_ebitda: float | None = None,
    ) -> dict:
        """Compute terminal value using two methods and average them.

        1. Gordon Growth Model: TV = FCF_n+1 / (WACC - g)
        2. Exit Multiple: TV = EBITDA_n * EV/EBITDA multiple

        Returns dict with both values and the averaged terminal value.
        """
        # Method 1: Gordon Growth Model
        gordon_tv = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)

        # Method 2: Exit Multiple
        exit_multiple_tv = None
        exit_multiple_used = None

        # Determine exit multiple
        if peer_ev_ebitda is not None and peer_ev_ebitda > 0:
            exit_multiple_used = peer_ev_ebitda
        else:
            # Use sector default
            try:
                profile = self.fundamentals.get_company_profile(ticker)
                sector = profile.get("sector", "")
                exit_multiple_used = SECTOR_EXIT_MULTIPLES.get(sector, DEFAULT_EXIT_MULTIPLE)
            except Exception:
                exit_multiple_used = DEFAULT_EXIT_MULTIPLE

        # Estimate terminal EBITDA from FCF.  Approximate EBITDA ~ FCF / 0.60
        # (assumes ~60% FCF-to-EBITDA conversion, conservative for capital-light firms).
        estimated_terminal_ebitda = final_fcf / 0.60
        exit_multiple_tv = estimated_terminal_ebitda * exit_multiple_used

        # Averaged terminal value
        if exit_multiple_tv is not None and exit_multiple_tv > 0:
            averaged_tv = (gordon_tv + exit_multiple_tv) / 2.0
        else:
            averaged_tv = gordon_tv

        return {
            "gordon_growth": round(gordon_tv, 0),
            "exit_multiple": round(exit_multiple_tv, 0) if exit_multiple_tv else None,
            "exit_multiple_used": exit_multiple_used,
            "averaged": round(averaged_tv, 0),
        }

    # ------------------------------------------------------------------
    # Sensitivity analysis
    # ------------------------------------------------------------------

    def _sensitivity_analysis(
        self, current_fcf, growth_rate, terminal_growth_base, shares, net_debt,
        base_wacc, base_tg, stage1_years=5, stage2_years=5,
    ):
        """5x5 sensitivity matrix: WACC vs terminal growth (two-stage model)."""
        wacc_range = [
            base_wacc - 0.02, base_wacc - 0.01, base_wacc,
            base_wacc + 0.01, base_wacc + 0.02,
        ]
        tg_range = [
            base_tg - 0.01, base_tg - 0.005, base_tg,
            base_tg + 0.005, base_tg + 0.01,
        ]

        total_years = stage1_years + stage2_years

        matrix = []
        for wacc in wacc_range:
            row = []
            for tg in tg_range:
                if wacc <= tg:
                    row.append(None)  # invalid: wacc must exceed terminal growth
                    continue
                try:
                    projections = self._project_two_stage_fcf(
                        current_fcf, growth_rate, tg, stage1_years, stage2_years
                    )
                    pv_fcfs = sum(
                        p["fcf"] / (1 + wacc) ** p["year"] for p in projections
                    )
                    final_fcf = projections[-1]["fcf"]
                    tv = final_fcf * (1 + tg) / (wacc - tg)
                    pv_tv = tv / (1 + wacc) ** total_years
                    ev = pv_fcfs + pv_tv
                    equity = ev - net_debt
                    row.append(round(equity / shares, 2) if shares > 0 else None)
                except Exception:
                    row.append(None)
            matrix.append(row)

        return {
            "wacc_range": [round(w, 4) for w in wacc_range],
            "terminal_growth_range": [round(t, 4) for t in tg_range],
            "matrix": matrix,
            "base_wacc_idx": 2,
            "base_tg_idx": 2,
        }

    # ------------------------------------------------------------------
    # Scenario analysis (bull / base / bear) with probability weights
    # ------------------------------------------------------------------

    def _scenario_analysis(
        self, current_fcf, base_growth, base_wacc, base_tg,
        shares, net_debt, current_price, stage1_years=5, stage2_years=5,
    ):
        """Bull / Base / Bear DCF scenarios with probability weights.

        Probabilities: bear=25%, base=50%, bull=25%.
        Also computes risk/reward ratio from current price.
        """
        scenarios = {}
        configs = {
            "bull": {"growth_mult": 1.30, "wacc_mult": 0.95, "tg_add": 0.005, "probability": 0.25},
            "base": {"growth_mult": 1.00, "wacc_mult": 1.00, "tg_add": 0.0, "probability": 0.50},
            "bear": {"growth_mult": 0.70, "wacc_mult": 1.05, "tg_add": -0.005, "probability": 0.25},
        }

        total_years = stage1_years + stage2_years

        for name, cfg in configs.items():
            g = base_growth * cfg["growth_mult"]
            w = base_wacc * cfg["wacc_mult"]
            tg = base_tg + cfg["tg_add"]
            if w <= tg:
                w = tg + 0.02

            projections = self._project_two_stage_fcf(
                current_fcf, g, tg, stage1_years, stage2_years
            )
            pv_fcfs = sum(
                p["fcf"] / (1 + w) ** p["year"] for p in projections
            )
            final_fcf = projections[-1]["fcf"]
            tv = final_fcf * (1 + tg) / (w - tg)
            pv_tv = tv / (1 + w) ** total_years
            ev = pv_fcfs + pv_tv
            equity = ev - net_debt
            per_share = equity / shares if shares > 0 else 0

            scenarios[name] = {
                "growth_rate": round(g, 4),
                "wacc": round(w, 4),
                "terminal_growth": round(tg, 4),
                "enterprise_value": round(ev, 0),
                "equity_value": round(equity, 0),
                "intrinsic_per_share": round(per_share, 2),
                "probability": cfg["probability"],
            }

        # Probability-weighted fair value
        prob_weighted = sum(
            s["intrinsic_per_share"] * s["probability"]
            for s in scenarios.values()
        )
        scenarios["probability_weighted"] = round(prob_weighted, 2)

        # Risk/reward ratio: upside_to_bull / downside_to_bear (from current price)
        risk_reward = None
        if current_price and current_price > 0:
            upside = scenarios["bull"]["intrinsic_per_share"] - current_price
            downside = current_price - scenarios["bear"]["intrinsic_per_share"]
            if downside > 0:
                risk_reward = round(upside / downside, 2)
            elif downside <= 0 and upside > 0:
                # Even bear case is above current price; infinite upside ratio
                risk_reward = 99.0

        return scenarios, prob_weighted, risk_reward

    # ------------------------------------------------------------------
    # Analyst price targets
    # ------------------------------------------------------------------

    def _get_analyst_targets(self, ticker: str) -> dict:
        """Fetch analyst price targets and recommendation from yfinance."""
        import yfinance as yf

        try:
            info = yf.Ticker(ticker).info
            count = info.get("numberOfAnalystOpinions")
            if count is None or count == 0:
                return {"available": False, "note": "No analyst coverage"}

            return {
                "available": True,
                "mean": info.get("targetMeanPrice"),
                "high": info.get("targetHighPrice"),
                "low": info.get("targetLowPrice"),
                "median": info.get("targetMedianPrice"),
                "count": count,
                "recommendation": info.get("recommendationKey"),
            }
        except Exception as e:
            logger.debug("Analyst targets failed for %s: %s", ticker, e)
            return {"available": False, "note": f"Error: {e}"}

    # ------------------------------------------------------------------
    # Peer EV/EBITDA for exit multiple
    # ------------------------------------------------------------------

    def _get_peer_ev_ebitda(self, ticker: str, peers: list[str] | None = None) -> float | None:
        """Get median EV/EBITDA from peer companies for exit multiple."""
        if peers is None:
            try:
                peers = self.fundamentals.get_peers(ticker)[:5]
            except Exception:
                return None

        if not peers:
            return None

        multiples = []
        for p in peers:
            try:
                pr = self.fundamentals.get_key_ratios(p)
                ev_ebitda = pr.get("ev_ebitda")
                if ev_ebitda is not None and 0 < ev_ebitda < 100:
                    multiples.append(float(ev_ebitda))
            except Exception:
                continue

        if multiples:
            return float(np.median(multiples))
        return None

    # ------------------------------------------------------------------
    # Owner Earnings helper (OCF - maintenance capex)
    # ------------------------------------------------------------------

    def _get_owner_earnings(self, ticker: str) -> tuple[float, dict, list[str]]:
        """Compute Owner Earnings = Operating Cash Flow - Maintenance CapEx.

        For capex-heavy growth companies (AMZN, GOOG, META), total capex includes
        massive growth investment (new data centers, logistics networks).  Using
        raw FCF (OCF - total capex) dramatically undervalues these companies.

        Maintenance capex is estimated as:
          1. Depreciation & Amortization (best proxy for replacement cost)
          2. If D&A unavailable, 50% of total capex (conservative assumption)

        Returns (owner_earnings, breakdown_dict, warnings).
        """
        warnings: list[str] = []
        breakdown = {}

        try:
            cf = self.fundamentals.get_cash_flow(ticker)
            inc = self.fundamentals.get_income_statement(ticker)

            if cf.empty:
                return 0.0, {}, ["No cash flow data for owner earnings"]

            # Operating cash flow
            ocf = 0.0
            for key in ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]:
                if key in cf.index:
                    val = cf.loc[key].iloc[0]
                    if pd.notna(val):
                        ocf = float(val)
                        break

            if ocf <= 0:
                return 0.0, {}, ["Operating cash flow is negative or zero"]

            # Total capex (negative in financial statements)
            total_capex = 0.0
            for key in ["Capital Expenditure", "Capital Expenditures"]:
                if key in cf.index:
                    val = cf.loc[key].iloc[0]
                    if pd.notna(val):
                        total_capex = abs(float(val))
                        break

            # Depreciation & Amortization (proxy for maintenance capex)
            da = 0.0
            for key in ["Depreciation And Amortization", "Reconciled Depreciation",
                        "Depreciation Amortization Depletion"]:
                if key in cf.index:
                    val = cf.loc[key].iloc[0]
                    if pd.notna(val):
                        da = abs(float(val))
                        break
            if da == 0 and not inc.empty:
                for key in ["Depreciation And Amortization", "Reconciled Depreciation"]:
                    if key in inc.index:
                        val = inc.loc[key].iloc[0]
                        if pd.notna(val):
                            da = abs(float(val))
                            break

            # Estimate maintenance capex
            if da > 0:
                maintenance_capex = da
                growth_capex = max(0, total_capex - da)
                capex_method = "D&A proxy"
            elif total_capex > 0:
                maintenance_capex = total_capex * 0.50
                growth_capex = total_capex * 0.50
                capex_method = "50% total capex estimate"
                warnings.append("D&A unavailable; estimated maintenance capex at 50% of total")
            else:
                maintenance_capex = 0
                growth_capex = 0
                capex_method = "no capex data"

            owner_earnings = ocf - maintenance_capex
            raw_fcf = ocf - total_capex

            # Compute growth capex ratio — if >50% of capex is growth, flag it
            growth_capex_ratio = growth_capex / total_capex if total_capex > 0 else 0
            if growth_capex_ratio > 0.3:
                warnings.append(
                    f"~{growth_capex_ratio:.0%} of capex is growth investment "
                    f"(${growth_capex/1e9:.1f}B growth vs ${maintenance_capex/1e9:.1f}B maintenance)"
                )

            breakdown = {
                "operating_cash_flow": round(ocf, 0),
                "total_capex": round(total_capex, 0),
                "depreciation_amortization": round(da, 0),
                "maintenance_capex": round(maintenance_capex, 0),
                "growth_capex": round(growth_capex, 0),
                "growth_capex_ratio": round(growth_capex_ratio, 3),
                "owner_earnings": round(owner_earnings, 0),
                "raw_fcf": round(raw_fcf, 0),
                "capex_method": capex_method,
            }

            return owner_earnings, breakdown, warnings

        except Exception as e:
            logger.warning("Owner earnings failed for %s: %s", ticker, e)
            return 0.0, {}, [f"Owner earnings error: {e}"]

    # ------------------------------------------------------------------
    # Earnings Power Value (EPV)
    # ------------------------------------------------------------------

    def _earnings_power_value(self, ticker: str) -> dict:
        """Compute Earnings Power Value = Normalized EBIT × (1-t) / WACC.

        EPV values a company based on its current earnings power without
        assuming any growth.  Useful as a floor valuation and for companies
        where FCF is distorted by investment cycles.
        """
        import yfinance as yf

        try:
            inc = self.fundamentals.get_income_statement(ticker)
            if inc.empty:
                return {"error": "No income statement data"}

            # Get EBIT (operating income) — average of available years for normalization
            ebit_vals = []
            for key in ["EBIT", "Operating Income"]:
                if key in inc.index:
                    row = inc.loc[key].dropna()
                    ebit_vals = [float(v) for v in row if pd.notna(v) and float(v) > 0]
                    break

            if not ebit_vals:
                return {"error": "No positive EBIT data available"}

            # Normalize: use average of last 3 years to smooth cyclical effects
            normalized_ebit = float(np.mean(ebit_vals[:3]))

            # WACC and tax rate
            wacc_info = self._compute_wacc(ticker)
            wacc = wacc_info["wacc"]
            tax_rate = self._estimate_tax_rate(ticker)

            if wacc <= 0:
                return {"error": "Invalid WACC for EPV"}

            # EPV = NOPAT / WACC
            nopat = normalized_ebit * (1 - tax_rate)
            epv_enterprise = nopat / wacc

            # Subtract net debt to get equity value
            net_debt_info = self._net_debt_adjustment(ticker)
            net_debt = net_debt_info["net_debt"]
            epv_equity = epv_enterprise - net_debt

            # Per share
            info = yf.Ticker(ticker).info
            shares = info.get("impliedSharesOutstanding") or info.get("sharesOutstanding", 1) or 1
            epv_per_share = epv_equity / shares

            return {
                "normalized_ebit": round(normalized_ebit, 0),
                "nopat": round(nopat, 0),
                "wacc": round(wacc, 4),
                "tax_rate": round(tax_rate, 4),
                "enterprise_value": round(epv_enterprise, 0),
                "net_debt": round(net_debt, 0),
                "equity_value": round(epv_equity, 0),
                "per_share": round(epv_per_share, 2),
                "years_averaged": min(3, len(ebit_vals)),
                "note": "No-growth valuation based on current earnings power",
            }

        except Exception as e:
            logger.warning("EPV failed for %s: %s", ticker, e)
            return {"error": f"EPV calculation failed: {e}"}

    # ------------------------------------------------------------------
    # Owner Earnings DCF (alternative to FCF-based DCF)
    # ------------------------------------------------------------------

    def owner_earnings_dcf(self, ticker: str) -> dict:
        """DCF using Owner Earnings (OCF - maintenance capex) instead of FCF.

        This method is more appropriate for capex-heavy growth companies
        (AMZN, GOOG, META, MSFT) where a large portion of capex is growth
        investment that FCF-based DCF penalizes.

        Uses the same two-stage model, WACC, and terminal value logic as
        the standard DCF but with owner earnings as the cash flow input.
        """
        import yfinance as yf

        owner_earnings, oe_breakdown, warnings = self._get_owner_earnings(ticker)

        if owner_earnings <= 0:
            return {
                "error": "Owner earnings non-positive",
                "breakdown": oe_breakdown,
                "warnings": warnings,
            }

        # Growth and WACC
        growth_info = self._estimate_growth_rate(ticker)
        growth_rate = growth_info["growth_rate"]

        wacc_info = self._compute_wacc(ticker)
        discount_rate = wacc_info["wacc"]
        terminal_growth = wacc_info["terminal_growth"]

        if discount_rate <= terminal_growth:
            discount_rate = terminal_growth + 0.02
            warnings.append(f"WACC adjusted to {discount_rate:.2%}")

        # Two-stage projection
        stage1_years = 5
        stage2_years = 5
        total_years = stage1_years + stage2_years

        projections = self._project_two_stage_fcf(
            owner_earnings, growth_rate, terminal_growth, stage1_years, stage2_years
        )

        pv_fcfs = sum(p["fcf"] / (1 + discount_rate) ** p["year"] for p in projections)
        final_oe = projections[-1]["fcf"]

        # Terminal value (Gordon Growth only — more appropriate for OE)
        terminal_value = final_oe * (1 + terminal_growth) / (discount_rate - terminal_growth)
        pv_terminal = terminal_value / (1 + discount_rate) ** total_years

        enterprise_value = pv_fcfs + pv_terminal

        # Net debt adjustment
        net_debt_info = self._net_debt_adjustment(ticker)
        net_debt = net_debt_info["net_debt"]
        equity_value = enterprise_value - net_debt

        # Per share
        info = yf.Ticker(ticker).info
        shares = info.get("impliedSharesOutstanding") or info.get("sharesOutstanding", 1) or 1
        intrinsic_per_share = equity_value / shares
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0

        margin_of_safety = (
            (intrinsic_per_share - current_price) / intrinsic_per_share * 100
            if intrinsic_per_share > 0
            else -100
        )

        return {
            "method": "Owner Earnings DCF",
            "owner_earnings": round(owner_earnings, 0),
            "owner_earnings_breakdown": oe_breakdown,
            "growth_rate": round(growth_rate, 4),
            "discount_rate": round(discount_rate, 4),
            "terminal_growth": round(terminal_growth, 4),
            "enterprise_value": round(enterprise_value, 0),
            "equity_value": round(equity_value, 0),
            "net_debt": round(net_debt, 0),
            "intrinsic_per_share": round(intrinsic_per_share, 2),
            "current_price": current_price,
            "margin_of_safety_pct": round(margin_of_safety, 2),
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Composite Fair Value (multi-method)
    # ------------------------------------------------------------------

    def composite_fair_value(self, ticker: str) -> dict:
        """Compute a weighted composite fair value from multiple methods.

        Methods and default weights:
          - FCF DCF (standard):    30%  (penalized for high-capex companies)
          - Owner Earnings DCF:    40%  (better for growth/capex-heavy)
          - Earnings Power Value:  15%  (floor valuation, no-growth)
          - Analyst Consensus:     15%  (market wisdom sanity check)

        Weights are dynamically adjusted:
          - If growth capex > 40% of total capex → OE DCF gets more weight
          - If FCF is negative → FCF DCF weight drops to 0
          - If analyst consensus unavailable → redistribute to other methods
        """
        methods = {}
        weights = {}
        fair_values = {}
        notes = []

        # --- Method 1: Standard FCF DCF ---
        try:
            fcf_dcf = self.dcf_valuation(ticker)
            if not fcf_dcf.get("error"):
                fv = fcf_dcf.get("intrinsic_per_share", 0)
                if fv > 0:
                    methods["fcf_dcf"] = fcf_dcf
                    fair_values["fcf_dcf"] = fv
                    weights["fcf_dcf"] = 0.30
                else:
                    notes.append("FCF DCF produced non-positive value; excluded")
            else:
                notes.append(f"FCF DCF failed: {fcf_dcf.get('error')}")
        except Exception as e:
            notes.append(f"FCF DCF error: {e}")

        # --- Method 2: Owner Earnings DCF ---
        try:
            oe_dcf = self.owner_earnings_dcf(ticker)
            if not oe_dcf.get("error"):
                fv = oe_dcf.get("intrinsic_per_share", 0)
                if fv > 0:
                    methods["owner_earnings_dcf"] = oe_dcf
                    fair_values["owner_earnings_dcf"] = fv
                    weights["owner_earnings_dcf"] = 0.40
                else:
                    notes.append("Owner Earnings DCF produced non-positive value; excluded")
            else:
                notes.append(f"Owner Earnings DCF: {oe_dcf.get('error')}")
        except Exception as e:
            notes.append(f"Owner Earnings DCF error: {e}")

        # --- Method 3: Earnings Power Value ---
        try:
            epv = self._earnings_power_value(ticker)
            if not epv.get("error"):
                fv = epv.get("per_share", 0)
                if fv > 0:
                    methods["epv"] = epv
                    fair_values["epv"] = fv
                    weights["epv"] = 0.15
                else:
                    notes.append("EPV produced non-positive value; excluded")
            else:
                notes.append(f"EPV: {epv.get('error')}")
        except Exception as e:
            notes.append(f"EPV error: {e}")

        # --- Method 4: Analyst Consensus ---
        try:
            analyst = self._get_analyst_targets(ticker)
            if analyst.get("available") and analyst.get("mean"):
                methods["analyst_consensus"] = analyst
                fair_values["analyst_consensus"] = float(analyst["mean"])
                weights["analyst_consensus"] = 0.15
            else:
                notes.append("No analyst consensus available")
        except Exception as e:
            notes.append(f"Analyst targets error: {e}")

        if not fair_values:
            return {"error": "No valuation methods produced valid results", "notes": notes}

        # --- Dynamic weight adjustment ---
        # Adjust for capex-heavy companies
        oe_data = methods.get("owner_earnings_dcf", {})
        oe_breakdown = oe_data.get("owner_earnings_breakdown", {})
        growth_capex_ratio = oe_breakdown.get("growth_capex_ratio", 0)

        if growth_capex_ratio > 0.40 and "fcf_dcf" in weights and "owner_earnings_dcf" in weights:
            # High growth capex — shift weight from FCF DCF to OE DCF
            shift = 0.15
            weights["fcf_dcf"] = max(0.10, weights["fcf_dcf"] - shift)
            weights["owner_earnings_dcf"] += shift
            notes.append(
                f"Growth capex {growth_capex_ratio:.0%} of total — "
                f"shifted weight toward Owner Earnings DCF"
            )

        # If OE DCF fair value is >2x FCF DCF, further reduce FCF DCF weight
        # (indicates FCF heavily suppressed by growth investment)
        fcf_fv = fair_values.get("fcf_dcf", 0)
        oe_fv = fair_values.get("owner_earnings_dcf", 0)
        if fcf_fv > 0 and oe_fv > 0 and oe_fv > fcf_fv * 2:
            if "fcf_dcf" in weights:
                extra_shift = min(0.10, weights["fcf_dcf"] - 0.05)
                if extra_shift > 0:
                    weights["fcf_dcf"] -= extra_shift
                    weights["owner_earnings_dcf"] += extra_shift
                    notes.append(
                        f"OE DCF ${oe_fv:.0f} is >{fcf_fv * 2:.0f} (2× FCF DCF) — "
                        f"FCF heavily suppressed by growth investment"
                    )

        # Reduce EPV weight for high-growth companies (EPV assumes no growth)
        growth_info = methods.get("owner_earnings_dcf", {}).get("growth_rate") or \
                     methods.get("fcf_dcf", {}).get("growth_rate") or 0
        if growth_info > 0.15 and "epv" in weights:
            # High-growth companies: EPV floor is less relevant
            epv_reduction = 0.05
            weights["epv"] = max(0.05, weights["epv"] - epv_reduction)
            # Redistribute to OE DCF
            if "owner_earnings_dcf" in weights:
                weights["owner_earnings_dcf"] += epv_reduction
            elif "fcf_dcf" in weights:
                weights["fcf_dcf"] += epv_reduction
            notes.append(f"Growth rate {growth_info:.0%} — reduced EPV weight (no-growth floor less relevant)")

        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        # Compute weighted composite fair value
        composite_fv = sum(fair_values[k] * weights[k] for k in fair_values)

        # Get current price for MOS
        current_price = 0
        for m in methods.values():
            if isinstance(m, dict) and m.get("current_price"):
                current_price = m["current_price"]
                break

        margin_of_safety = (
            (composite_fv - current_price) / composite_fv * 100
            if composite_fv > 0
            else -100
        )

        return {
            "composite_fair_value": round(composite_fv, 2),
            "current_price": current_price,
            "margin_of_safety_pct": round(margin_of_safety, 2),
            "verdict": (
                "UNDERVALUED" if margin_of_safety > 15
                else "FAIR" if margin_of_safety > -10
                else "OVERVALUED"
            ),
            "method_fair_values": {k: round(v, 2) for k, v in fair_values.items()},
            "method_weights": {k: round(v, 3) for k, v in weights.items()},
            "methods": methods,
            "notes": notes,
        }

    # ------------------------------------------------------------------
    # Smoothed FCF helper
    # ------------------------------------------------------------------

    def _get_smoothed_fcf(self, ticker: str) -> tuple[float, list[str]]:
        """Return (current_fcf, warnings) using smoothed FCF logic.

        If the latest FCF is less than 40% of the average of prior positive
        years, use the average of up to 3 positive years instead.
        """
        warnings: list[str] = []

        cf = self.fundamentals.get_cash_flow(ticker)
        if cf.empty or "Free Cash Flow" not in cf.index:
            return 0.0, ["No FCF data available"]

        fcf_row = cf.loc["Free Cash Flow"]
        fcf_vals = fcf_row.dropna()
        positive_fcfs = [float(v) for v in fcf_vals if float(v) > 0]
        latest_fcf = float(fcf_vals.iloc[0]) if len(fcf_vals) > 0 else 0

        if len(positive_fcfs) >= 2 and latest_fcf > 0:
            avg_prior = np.mean(positive_fcfs[1:]) if len(positive_fcfs) > 1 else positive_fcfs[0]
            if latest_fcf < avg_prior * 0.40:
                current_fcf = float(np.mean(positive_fcfs[:3]))
                warnings.append(
                    f"Latest FCF anomalously low vs prior years; "
                    f"using {len(positive_fcfs[:3])}-year positive average"
                )
            else:
                current_fcf = latest_fcf
        elif latest_fcf > 0:
            current_fcf = latest_fcf
        elif positive_fcfs:
            current_fcf = positive_fcfs[0]
            warnings.append("Latest FCF negative; using most recent positive year")
        else:
            current_fcf = latest_fcf  # negative — will produce negative valuation
            warnings.append("No positive FCF years found")

        return current_fcf, warnings

    # ------------------------------------------------------------------
    # Reverse DCF: implied growth rate
    # ------------------------------------------------------------------

    def reverse_dcf(self, ticker: str) -> dict:
        """Solve for the implied growth rate that justifies the current market price.

        Uses scipy.optimize.brentq to find the growth_rate where the two-stage
        DCF intrinsic value equals the current share price.
        """
        import yfinance as yf

        # Gather inputs — use smoothed FCF for consistency with dcf_valuation
        current_fcf, _fcf_warnings = self._get_smoothed_fcf(ticker)
        if current_fcf <= 0:
            return {
                "error": "Negative or zero FCF; reverse DCF not meaningful",
                "current_fcf": current_fcf,
            }

        wacc_info = self._compute_wacc(ticker)
        wacc = wacc_info["wacc"]
        terminal_growth = wacc_info["terminal_growth"]

        net_debt_info = self._net_debt_adjustment(ticker)
        net_debt = net_debt_info["net_debt"]

        info = yf.Ticker(ticker).info
        shares = info.get("impliedSharesOutstanding") or info.get("sharesOutstanding", 1) or 1
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0

        if current_price <= 0:
            return {"error": "No current price available"}

        stage1_years = 5
        stage2_years = 5
        total_years = stage1_years + stage2_years

        def _intrinsic_at_growth(g):
            """Compute intrinsic per share for a given growth rate."""
            tg = terminal_growth
            w = wacc
            if w <= tg:
                w = tg + 0.02
            projections = self._project_two_stage_fcf(
                current_fcf, g, tg, stage1_years, stage2_years
            )
            pv_fcfs = sum(p["fcf"] / (1 + w) ** p["year"] for p in projections)
            final_fcf = projections[-1]["fcf"]
            tv = final_fcf * (1 + tg) / (w - tg)
            pv_tv = tv / (1 + w) ** total_years
            ev = pv_fcfs + pv_tv
            equity = ev - net_debt
            return equity / shares - current_price

        # Search for implied growth rate in range [-30%, +60%]
        try:
            low_val = _intrinsic_at_growth(-0.30)
            high_val = _intrinsic_at_growth(0.60)

            if low_val > 0:
                # Even at -30% growth, intrinsic > price; market is very pessimistic
                return {
                    "implied_growth_rate": None,
                    "verdict": "Market prices in extreme decline (worse than -30% FCF growth)",
                    "current_price": current_price,
                    "note": "Implied growth below -30%",
                }
            if high_val < 0:
                # Even at +60% growth, intrinsic < price; extreme overvaluation
                return {
                    "implied_growth_rate": None,
                    "verdict": "Market prices in extreme growth (>60% FCF CAGR implied)",
                    "current_price": current_price,
                    "note": "Implied growth above 60%",
                }

            implied_g = brentq(_intrinsic_at_growth, -0.30, 0.60, xtol=1e-5)

            # Assess reasonableness
            growth_info = self._estimate_growth_rate(ticker)
            estimated_g = growth_info["growth_rate"]
            gap = implied_g - estimated_g

            if gap > 0.10:
                verdict = "Market expects significantly higher growth than fundamentals suggest"
            elif gap > 0.03:
                verdict = "Market expectations moderately above fundamental estimates"
            elif gap < -0.10:
                verdict = "Market is pricing in much lower growth than fundamentals suggest (potential opportunity)"
            elif gap < -0.03:
                verdict = "Market expectations moderately below fundamental estimates"
            else:
                verdict = "Market expectations roughly align with fundamental growth estimates"

            return {
                "implied_growth_rate": round(implied_g, 4),
                "estimated_growth_rate": round(estimated_g, 4),
                "gap": round(gap, 4),
                "verdict": verdict,
                "current_price": current_price,
                "wacc_used": round(wacc, 4),
                "terminal_growth_used": round(terminal_growth, 4),
            }

        except ValueError as e:
            return {
                "error": f"Solver failed: {e}",
                "current_price": current_price,
            }
        except Exception as e:
            logger.warning("Reverse DCF failed for %s: %s", ticker, e)
            return {"error": f"Reverse DCF error: {e}"}

    # ------------------------------------------------------------------
    # Main DCF valuation (two-stage)
    # ------------------------------------------------------------------

    def dcf_valuation(
        self,
        ticker: str,
        growth_rate: float | None = None,
        terminal_growth: float | None = None,
        discount_rate: float | None = None,
        projection_years: int = 5,
    ) -> dict:
        """Two-stage DCF valuation with proper WACC, dual terminal value,
        sensitivity matrix, and probability-weighted scenarios.

        Args:
            ticker: Stock symbol
            growth_rate: Expected FCF growth rate (auto-estimated if None)
            terminal_growth: Long-term terminal growth (country-adjusted if None)
            discount_rate: WACC / required return (computed if None)
            projection_years: Years for stage 1 (stage 2 adds another 5)
        """
        import yfinance as yf

        current_fcf, warnings = self._get_smoothed_fcf(ticker)
        if current_fcf == 0.0 and warnings and "No FCF data" in warnings[0]:
            return {"error": "No cash flow data available"}

        # --- Growth rate estimation ---
        growth_info = {"source": "override", "sources": {}}
        if growth_rate is None:
            growth_info = self._estimate_growth_rate(ticker)
            growth_rate = growth_info["growth_rate"]

        # --- WACC calculation ---
        wacc_info = self._compute_wacc(ticker)
        if discount_rate is None:
            discount_rate = wacc_info["wacc"]
        if terminal_growth is None:
            terminal_growth = wacc_info["terminal_growth"]

        # Validate: discount rate must exceed terminal growth
        if discount_rate <= terminal_growth:
            discount_rate = terminal_growth + 0.02
            warnings.append(f"WACC adjusted to {discount_rate:.2%} (must exceed terminal growth)")

        # --- Two-stage FCF projection ---
        stage1_years = projection_years
        stage2_years = 5
        total_years = stage1_years + stage2_years

        projections = self._project_two_stage_fcf(
            current_fcf, growth_rate, terminal_growth, stage1_years, stage2_years
        )

        # --- Discount projected FCFs to present value ---
        pv_fcfs = sum(
            p["fcf"] / (1 + discount_rate) ** p["year"] for p in projections
        )

        final_fcf = projections[-1]["fcf"]

        # --- Terminal value (dual method) ---
        peer_ev_ebitda = self._get_peer_ev_ebitda(ticker)
        tv_methods = self._compute_terminal_value(
            final_fcf, terminal_growth, discount_rate, ticker, peer_ev_ebitda
        )
        terminal_value = tv_methods["averaged"]
        pv_terminal = terminal_value / (1 + discount_rate) ** total_years

        enterprise_value = pv_fcfs + pv_terminal

        # Terminal value sanity check
        tv_pct = pv_terminal / enterprise_value if enterprise_value > 0 else 1.0
        if tv_pct > 0.75:
            warnings.append(
                f"Terminal value is {tv_pct:.0%} of total EV "
                "(>75% -- model heavily dependent on terminal assumptions)"
            )

        # --- Net debt adjustment ---
        net_debt_info = self._net_debt_adjustment(ticker)
        net_debt = net_debt_info["net_debt"]
        equity_value = enterprise_value - net_debt

        # --- Shares outstanding ---
        info = yf.Ticker(ticker).info
        shares = info.get("impliedSharesOutstanding") or info.get("sharesOutstanding", 1) or 1
        intrinsic_per_share = equity_value / shares
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0

        margin_of_safety = (
            (intrinsic_per_share - current_price) / intrinsic_per_share * 100
            if intrinsic_per_share > 0
            else -100
        )

        # --- Sensitivity analysis ---
        sensitivity = self._sensitivity_analysis(
            current_fcf, growth_rate, terminal_growth, shares, net_debt,
            discount_rate, terminal_growth, stage1_years, stage2_years,
        )

        # --- Scenario analysis (with probabilities) ---
        scenarios, prob_weighted_fv, risk_reward = self._scenario_analysis(
            current_fcf, growth_rate, discount_rate, terminal_growth,
            shares, net_debt, current_price, stage1_years, stage2_years,
        )

        # --- Analyst targets ---
        analyst_targets = self._get_analyst_targets(ticker)

        # --- Serializable two-stage projection ---
        two_stage_projection = [
            {
                "year": p["year"],
                "stage": p["stage"],
                "growth_rate": p["growth_rate"],
                "fcf": round(p["fcf"], 0),
            }
            for p in projections
        ]

        return {
            "current_fcf": current_fcf,
            "discount_rate": round(discount_rate, 4),
            "growth_rate": round(growth_rate, 4),
            "growth_source": growth_info.get("source", "override"),
            "growth_sources": growth_info.get("sources", {}),
            "terminal_growth": round(terminal_growth, 4),
            "enterprise_value": round(enterprise_value, 0),
            "equity_value": round(equity_value, 0),
            "net_debt": round(net_debt, 0),
            "net_debt_detail": net_debt_info,
            "shares_diluted": shares,
            "intrinsic_per_share": round(intrinsic_per_share, 2),
            "current_price": current_price,
            "margin_of_safety_pct": round(margin_of_safety, 2),
            "verdict": (
                "UNDERVALUED" if margin_of_safety > 15
                else "FAIR" if margin_of_safety > -10
                else "OVERVALUED"
            ),
            "wacc_breakdown": wacc_info,
            "value_breakdown": {
                "pv_fcfs": round(pv_fcfs, 0),
                "pv_terminal": round(pv_terminal, 0),
                "tv_pct_of_total": round(tv_pct, 3),
            },
            "two_stage_projection": two_stage_projection,
            "terminal_value_methods": tv_methods,
            "sensitivity": sensitivity,
            "scenarios": scenarios,
            "probability_weighted_fair_value": round(prob_weighted_fv, 2),
            "risk_reward_ratio": risk_reward,
            "analyst_targets": analyst_targets,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Comparable valuation
    # ------------------------------------------------------------------

    def comparable_valuation(self, ticker: str, peers: list[str] | None = None) -> dict:
        """Valuation by comparing multiples to peers."""
        ratios = self.fundamentals.get_key_ratios(ticker)
        if peers is None:
            peers = self.fundamentals.get_peers(ticker)[:5]

        if not peers:
            return {"error": "No peer companies available"}

        peer_ratios = []
        for p in peers:
            try:
                pr = self.fundamentals.get_key_ratios(p)
                peer_ratios.append(pr)
            except Exception:
                continue

        if not peer_ratios:
            return {"error": "Could not fetch peer data"}

        metrics = ["pe_forward", "pb_ratio", "ev_ebitda", "ps_ratio"]
        comparison = {}
        for m in metrics:
            company_val = ratios.get(m)
            peer_vals = [pr.get(m) for pr in peer_ratios if pr.get(m) is not None]
            if company_val is not None and peer_vals:
                median = float(np.median(peer_vals))
                comparison[m] = {
                    "company": company_val,
                    "peer_median": round(median, 2),
                    "premium_pct": round((company_val / median - 1) * 100, 1) if median else 0,
                }

        return {"ticker": ticker, "peers": peers, "comparison": comparison}


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class ValuationAnalyzerPlugin(_BaseAnalyzer):
    name = "valuation"
    default_weight = 0.20

    def __init__(self):
        self._analyzer = ValuationAnalyzer()

    def analyze(self, ticker, ctx):
        try:
            dcf = self._analyzer.dcf_valuation(ticker)
        except Exception:
            dcf = {"error": "DCF failed"}

        # --- Multi-method composite fair value ---
        composite = {}
        try:
            composite = self._analyzer.composite_fair_value(ticker)
            dcf["composite"] = composite
        except Exception as e:
            dcf["composite"] = {"error": f"Composite valuation failed: {e}"}

        # Use composite MOS for scoring if available, else fall back to DCF-only
        if composite.get("margin_of_safety_pct") is not None:
            mos_for_scoring = composite["margin_of_safety_pct"]
        else:
            mos_for_scoring = dcf.get("margin_of_safety_pct", 0)

        mos_for_scoring = max(-50, min(50, mos_for_scoring))
        dcf_score = max(0, min(100, 50 + mos_for_scoring))

        comps_score = 50
        try:
            comps = self._analyzer.comparable_valuation(ticker)
            if comps.get("comparison"):
                premiums = [v["premium_pct"] for v in comps["comparison"].values() if v.get("premium_pct") is not None]
                if premiums:
                    avg_premium = sum(premiums) / len(premiums)
                    comps_score = max(0, min(100, 50 - avg_premium))
            dcf["comparables"] = comps
        except Exception:
            pass

        # Reverse DCF (non-blocking: failure does not affect scoring)
        try:
            rev = self._analyzer.reverse_dcf(ticker)
            dcf["reverse_dcf"] = rev
        except Exception as e:
            dcf["reverse_dcf"] = {"error": f"Reverse DCF failed: {e}"}

        # Analyst targets (non-blocking)
        if "analyst_targets" not in dcf:
            try:
                dcf["analyst_targets"] = self._analyzer._get_analyst_targets(ticker)
            except Exception:
                dcf["analyst_targets"] = {"available": False, "note": "Fetch failed"}

        score = dcf_score * 0.60 + comps_score * 0.25 + 50 * 0.15
        dcf["score"] = round(score, 1)
        dcf["dcf_score"] = round(dcf_score, 1)
        dcf["comps_score"] = round(comps_score, 1)
        return dcf
