"""Fundamental analysis engine — institutional-grade metrics.

Provides: financial health, growth, valuation, ROIC, Piotroski F-Score,
DuPont decomposition (3-way & 5-way), earnings quality, cash conversion
cycle, capital allocation scoring, multi-quarter trend analysis, and
SG&A efficiency.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from src.data_sources.fundamentals import FundamentalsClient
from src.utils.logger import setup_logger

logger = setup_logger("fundamental_analysis")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(df: pd.DataFrame, label: str, col: int = 0,
              fallbacks: list[str] | None = None) -> float | None:
    """Safely extract a single value from a financial-statement DataFrame.

    yfinance DataFrames have row-index = line-item name, columns = dates
    (most recent first).  *col* selects the period (0 = latest).

    Tries *label* first, then each string in *fallbacks*.
    """
    candidates = [label] + (fallbacks or [])
    for name in candidates:
        if name in df.index:
            try:
                val = df.loc[name].iloc[col]
                if pd.notna(val):
                    return float(val)
            except (IndexError, TypeError):
                continue
    return None


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Divide two nullable floats; returns None on failure or zero denom."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def _fmt_pct(val: float | None, decimals: int = 1) -> str:
    """Format a ratio as a percentage string, e.g. 0.153 -> '15.3%'."""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}%}"


def _fmt_ratio(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


# ---------------------------------------------------------------------------
# Core analyser
# ---------------------------------------------------------------------------

class FundamentalAnalyzer:
    """Analyze company fundamentals for investment decisions."""

    def __init__(self):
        self.client = FundamentalsClient()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def analyze(self, ticker: str) -> dict:
        """Run full fundamental analysis on a company."""
        # --- Fetch all data up-front; failures return empty containers ---
        ratios = self._fetch(self.client.get_key_ratios, ticker, default={})
        profile = self._fetch(self.client.get_company_profile, ticker, default={})
        income_a = self._fetch(self.client.get_income_statement, ticker, default=pd.DataFrame())
        income_q = self._fetch(self.client.get_income_statement, ticker, default=pd.DataFrame(), quarterly=True)
        balance = self._fetch(self.client.get_balance_sheet, ticker, default=pd.DataFrame())
        cashflow = self._fetch(self.client.get_cash_flow, ticker, default=pd.DataFrame())

        # yfinance info for supplemental data (shares outstanding, market cap)
        info = self._fetch_info(ticker)

        # --- Legacy scores (preserved interface) ---
        health = self._assess_financial_health(ratios)
        growth = self._assess_growth(ratios)
        valuation = self._assess_valuation(ratios)

        # --- New institutional metrics ---
        roic = self._calc_roic(income_a, balance)
        piotroski = self._calc_piotroski(income_a, balance, cashflow, ratios, info)
        dupont = self._calc_dupont(income_a, balance)
        earnings_quality = self._calc_earnings_quality(income_a, cashflow, balance)
        ccc = self._calc_cash_conversion_cycle(income_a, balance)
        capital_alloc = self._calc_capital_allocation(income_a, cashflow, info)
        quarterly_trends = self._calc_quarterly_trends(income_q)
        sga_eff = self._calc_sga_efficiency(income_a)

        return {
            "ticker": ticker,
            "company": profile.get("name"),
            "sector": profile.get("sector"),
            "health": health,
            "growth": growth,
            "valuation": valuation,
            "ratios": ratios,
            "roic": roic,
            "piotroski": piotroski,
            "dupont": dupont,
            "earnings_quality": earnings_quality,
            "cash_conversion_cycle": ccc,
            "capital_allocation": capital_alloc,
            "quarterly_trends": quarterly_trends,
            "sga_efficiency": sga_eff,
        }

    # ------------------------------------------------------------------
    # Safe data fetching
    # ------------------------------------------------------------------
    @staticmethod
    def _fetch(fn, *args, default=None, **kwargs):
        """Call *fn* and return its result, or *default* on any error."""
        try:
            result = fn(*args, **kwargs)
            if result is None:
                return default
            if isinstance(result, pd.DataFrame) and result.empty:
                return default if default is not None else result
            return result
        except Exception as exc:
            logger.warning("Data fetch failed (%s): %s", fn.__name__, exc)
            return default

    @staticmethod
    def _fetch_info(ticker: str) -> dict:
        try:
            return yf.Ticker(ticker).info or {}
        except Exception as exc:
            logger.warning("yfinance info fetch failed for %s: %s", ticker, exc)
            return {}

    # ------------------------------------------------------------------
    # Legacy scorers (preserved from original)
    # ------------------------------------------------------------------
    def _assess_financial_health(self, ratios: dict) -> dict:
        """Score financial health based on key ratios (0-6)."""
        score = 0
        reasons: list[str] = []

        cr = ratios.get("current_ratio")
        if cr is not None:
            if cr > 1.5:
                score += 2
                reasons.append(f"Strong current ratio: {cr:.2f}")
            elif cr > 1.0:
                score += 1
                reasons.append(f"Adequate current ratio: {cr:.2f}")
            else:
                reasons.append(f"Weak current ratio: {cr:.2f}")

        de = ratios.get("debt_to_equity")
        if de is not None:
            if de < 50:
                score += 2
                reasons.append(f"Low debt/equity: {de:.1f}")
            elif de < 100:
                score += 1
                reasons.append(f"Moderate debt/equity: {de:.1f}")
            else:
                reasons.append(f"High debt/equity: {de:.1f}")

        roe = ratios.get("roe")
        if roe is not None:
            if roe > 0.15:
                score += 2
                reasons.append(f"Strong ROE: {roe:.1%}")
            elif roe > 0.08:
                score += 1
                reasons.append(f"Adequate ROE: {roe:.1%}")
            else:
                reasons.append(f"Weak ROE: {roe:.1%}")

        return {"score": score, "max_score": 6, "reasons": reasons}

    def _assess_growth(self, ratios: dict) -> dict:
        """Score growth profile (0-4)."""
        score = 0
        reasons: list[str] = []

        rev_g = ratios.get("revenue_growth")
        if rev_g is not None:
            if rev_g > 0.15:
                score += 2
                reasons.append(f"Strong revenue growth: {rev_g:.1%}")
            elif rev_g > 0.05:
                score += 1
                reasons.append(f"Moderate revenue growth: {rev_g:.1%}")
            else:
                reasons.append(f"Low revenue growth: {rev_g:.1%}")

        earn_g = ratios.get("earnings_growth")
        if earn_g is not None:
            if earn_g > 0.15:
                score += 2
                reasons.append(f"Strong earnings growth: {earn_g:.1%}")
            elif earn_g > 0.05:
                score += 1
                reasons.append(f"Moderate earnings growth: {earn_g:.1%}")
            else:
                reasons.append(f"Low earnings growth: {earn_g:.1%}")

        return {"score": score, "max_score": 4, "reasons": reasons}

    def _assess_valuation(self, ratios: dict) -> dict:
        """Score relative valuation (0-4)."""
        score = 0
        reasons: list[str] = []

        pe = ratios.get("pe_forward")
        if pe is not None:
            if pe < 15:
                score += 2
                reasons.append(f"Low forward P/E: {pe:.1f}")
            elif pe < 25:
                score += 1
                reasons.append(f"Moderate forward P/E: {pe:.1f}")
            else:
                reasons.append(f"High forward P/E: {pe:.1f}")

        peg = ratios.get("peg_ratio")
        if peg is not None:
            if 0 < peg < 1:
                score += 2
                reasons.append(f"Undervalued PEG: {peg:.2f}")
            elif peg < 2:
                score += 1
                reasons.append(f"Fair PEG: {peg:.2f}")
            else:
                reasons.append(f"Expensive PEG: {peg:.2f}")

        return {"score": score, "max_score": 4, "reasons": reasons}

    # ------------------------------------------------------------------
    # 1. ROIC
    # ------------------------------------------------------------------
    def _calc_roic(self, income: pd.DataFrame, balance: pd.DataFrame) -> dict:
        """Return on Invested Capital = NOPAT / Invested Capital."""
        result = {"value": None, "nopat": None, "invested_capital": None,
                  "score": 0, "max_score": 3}
        try:
            if income.empty or balance.empty:
                return result

            op_income = _safe_get(income, "Operating Income")
            pretax = _safe_get(income, "Pretax Income")
            tax_prov = _safe_get(income, "Tax Provision")

            # Effective tax rate; fall back to statutory 25%
            if pretax and tax_prov and pretax > 0:
                tax_rate = tax_prov / pretax
            else:
                tax_rate = 0.25

            if op_income is None:
                return result

            nopat = op_income * (1 - tax_rate)

            total_equity = _safe_get(balance, "Stockholders Equity",
                                     fallbacks=["Total Equity Gross Minority Interest"])
            total_debt = _safe_get(balance, "Long Term Debt",
                                   fallbacks=["Total Debt"])
            cash = _safe_get(balance, "Cash And Cash Equivalents",
                             fallbacks=["Cash Cash Equivalents And Short Term Investments"])

            if total_equity is None or total_debt is None:
                return result

            invested_capital = total_equity + total_debt - (cash or 0)
            if invested_capital <= 0:
                return result

            roic = nopat / invested_capital

            # Score
            score = 0
            if roic > 0.20:
                score = 3
            elif roic > 0.12:
                score = 2
            elif roic > 0.08:
                score = 1

            result.update(value=round(roic, 4), nopat=round(nopat, 2),
                          invested_capital=round(invested_capital, 2), score=score)
        except Exception as exc:
            logger.warning("ROIC calculation failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 2. Piotroski F-Score
    # ------------------------------------------------------------------
    def _calc_piotroski(self, income: pd.DataFrame, balance: pd.DataFrame,
                        cashflow: pd.DataFrame, ratios: dict, info: dict) -> dict:
        """Piotroski F-Score: 9 binary tests of financial strength."""
        breakdown = {f"F{i}": False for i in range(1, 10)}
        result = {"score": 0, "max_score": 9, "breakdown": breakdown,
                  "signal": "WEAK"}
        try:
            has_two_years = (not income.empty and income.shape[1] >= 2
                            and not balance.empty and balance.shape[1] >= 2)

            # --- Profitability ---
            # F1: Net Income > 0
            ni_curr = _safe_get(income, "Net Income", col=0)
            if ni_curr is not None and ni_curr > 0:
                breakdown["F1"] = True

            # F2: ROA improving (or positive if only 1 year)
            total_assets_curr = _safe_get(balance, "Total Assets", col=0)
            roa_curr = _safe_div(ni_curr, total_assets_curr)
            if has_two_years:
                ni_prev = _safe_get(income, "Net Income", col=1)
                total_assets_prev = _safe_get(balance, "Total Assets", col=1)
                roa_prev = _safe_div(ni_prev, total_assets_prev)
                if roa_curr is not None and roa_prev is not None and roa_curr > roa_prev:
                    breakdown["F2"] = True
            else:
                if roa_curr is not None and roa_curr > 0:
                    breakdown["F2"] = True

            # F3: Operating Cash Flow > 0
            ocf_curr = _safe_get(cashflow, "Operating Cash Flow", col=0)
            if ocf_curr is not None and ocf_curr > 0:
                breakdown["F3"] = True

            # F4: OCF > Net Income (accruals check)
            if ocf_curr is not None and ni_curr is not None and ocf_curr > ni_curr:
                breakdown["F4"] = True

            # --- Leverage / Liquidity ---
            # F5: Long-term debt ratio decreased (or stayed zero)
            ltd_curr = _safe_get(balance, "Long Term Debt", col=0)
            if ltd_curr is not None:
                if has_two_years:
                    ltd_prev = _safe_get(balance, "Long Term Debt", col=1) or 0
                    if ltd_curr <= ltd_prev:
                        breakdown["F5"] = True
                else:
                    if ltd_curr == 0:
                        breakdown["F5"] = True

            # F6: Current ratio increased
            ca_curr = _safe_get(balance, "Current Assets", col=0)
            cl_curr = _safe_get(balance, "Current Liabilities", col=0)
            cr_curr = _safe_div(ca_curr, cl_curr)
            if has_two_years:
                ca_prev = _safe_get(balance, "Current Assets", col=1)
                cl_prev = _safe_get(balance, "Current Liabilities", col=1)
                cr_prev = _safe_div(ca_prev, cl_prev)
                if cr_curr is not None and cr_prev is not None and cr_curr > cr_prev:
                    breakdown["F6"] = True
            else:
                if cr_curr is not None and cr_curr > 1.0:
                    breakdown["F6"] = True

            # F7: No new share dilution
            # yfinance income_stmt sometimes has "Diluted Average Shares"
            diluted_curr = _safe_get(income, "Diluted Average Shares",
                                     fallbacks=["Basic Average Shares"], col=0)
            if has_two_years:
                diluted_prev = _safe_get(income, "Diluted Average Shares",
                                         fallbacks=["Basic Average Shares"], col=1)
                if diluted_curr is not None and diluted_prev is not None:
                    if diluted_curr <= diluted_prev:
                        breakdown["F7"] = True
            else:
                # Single year: only award if we have data confirming no dilution
                if diluted_curr is not None:
                    # Data exists for current year; no prior to compare, leave False
                    pass

            # --- Operating Efficiency ---
            # F8: Gross margin increased
            gp_curr = _safe_get(income, "Gross Profit", col=0)
            rev_curr = _safe_get(income, "Total Revenue", col=0)
            gm_curr = _safe_div(gp_curr, rev_curr)
            if has_two_years:
                gp_prev = _safe_get(income, "Gross Profit", col=1)
                rev_prev = _safe_get(income, "Total Revenue", col=1)
                gm_prev = _safe_div(gp_prev, rev_prev)
                if gm_curr is not None and gm_prev is not None and gm_curr > gm_prev:
                    breakdown["F8"] = True
            else:
                if gm_curr is not None and gm_curr > 0.3:
                    breakdown["F8"] = True

            # F9: Asset turnover increased
            at_curr = _safe_div(rev_curr, total_assets_curr)
            if has_two_years:
                rev_prev_val = _safe_get(income, "Total Revenue", col=1)
                at_prev = _safe_div(rev_prev_val, total_assets_prev)
                if at_curr is not None and at_prev is not None and at_curr > at_prev:
                    breakdown["F9"] = True
            else:
                if at_curr is not None and at_curr > 0.5:
                    breakdown["F9"] = True

            total = sum(1 for v in breakdown.values() if v)
            signal = "STRONG" if total >= 7 else ("MODERATE" if total >= 4 else "WEAK")
            result.update(score=total, breakdown=breakdown, signal=signal)

        except Exception as exc:
            logger.warning("Piotroski F-Score failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 3. DuPont Decomposition
    # ------------------------------------------------------------------
    def _calc_dupont(self, income: pd.DataFrame, balance: pd.DataFrame) -> dict:
        """3-way and 5-way DuPont decomposition of ROE."""
        three = {"profit_margin": None, "asset_turnover": None,
                 "equity_multiplier": None, "roe": None}
        five = {"tax_burden": None, "interest_burden": None,
                "ebit_margin": None, "asset_turnover": None,
                "equity_multiplier": None, "roe": None}
        result = {"three_way": three, "five_way": five}

        try:
            if income.empty or balance.empty:
                return result

            revenue = _safe_get(income, "Total Revenue")
            net_income = _safe_get(income, "Net Income")
            pretax_income = _safe_get(income, "Pretax Income")
            op_income = _safe_get(income, "Operating Income",
                                  fallbacks=["EBIT"])
            total_assets = _safe_get(balance, "Total Assets")
            equity = _safe_get(balance, "Stockholders Equity",
                               fallbacks=["Total Equity Gross Minority Interest"])

            # 3-way: ROE = Margin * Turnover * Leverage
            margin = _safe_div(net_income, revenue)
            turnover = _safe_div(revenue, total_assets)
            multiplier = _safe_div(total_assets, equity)

            if all(v is not None for v in [margin, turnover, multiplier]):
                three.update(
                    profit_margin=round(margin, 4),
                    asset_turnover=round(turnover, 4),
                    equity_multiplier=round(multiplier, 4),
                    roe=round(margin * turnover * multiplier, 4),
                )

            # 5-way: Tax * Interest * EBIT margin * Turnover * Leverage
            tax_burden = _safe_div(net_income, pretax_income)
            interest_burden = _safe_div(pretax_income, op_income)
            ebit_margin = _safe_div(op_income, revenue)

            if all(v is not None for v in
                   [tax_burden, interest_burden, ebit_margin, turnover, multiplier]):
                roe_5 = tax_burden * interest_burden * ebit_margin * turnover * multiplier
                five.update(
                    tax_burden=round(tax_burden, 4),
                    interest_burden=round(interest_burden, 4),
                    ebit_margin=round(ebit_margin, 4),
                    asset_turnover=round(turnover, 4),
                    equity_multiplier=round(multiplier, 4),
                    roe=round(roe_5, 4),
                )

        except Exception as exc:
            logger.warning("DuPont decomposition failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 4. Quality of Earnings
    # ------------------------------------------------------------------
    def _calc_earnings_quality(self, income: pd.DataFrame,
                               cashflow: pd.DataFrame,
                               balance: pd.DataFrame) -> dict:
        """Accruals ratio + FCF-to-NI quality assessment."""
        result = {"accruals_ratio": None, "fcf_ni_ratio": None,
                  "score": 0, "max_score": 3, "assessment": "N/A"}
        try:
            ni = _safe_get(income, "Net Income") if not income.empty else None
            ocf = _safe_get(cashflow, "Operating Cash Flow") if not cashflow.empty else None
            fcf = _safe_get(cashflow, "Free Cash Flow") if not cashflow.empty else None
            total_assets = _safe_get(balance, "Total Assets") if not balance.empty else None

            score = 0

            # Accruals ratio = (NI - OCF) / Total Assets
            accruals = None
            if ni is not None and ocf is not None and total_assets and total_assets > 0:
                accruals = (ni - ocf) / total_assets
                result["accruals_ratio"] = round(accruals, 4)
                # Low (negative) accruals = high quality
                if accruals < -0.05:
                    score += 2  # excellent — cash earnings exceed accrual earnings
                elif accruals < 0.05:
                    score += 1  # acceptable

            # FCF / Net Income ratio
            fcf_ni = _safe_div(fcf, ni)
            if fcf_ni is not None:
                result["fcf_ni_ratio"] = round(fcf_ni, 4)
                if fcf_ni > 1.0:
                    score += 1  # cash generation exceeds reported earnings

            result["score"] = score

            if score >= 3:
                result["assessment"] = "High quality — strong cash backing"
            elif score == 2:
                result["assessment"] = "Good quality — adequate cash backing"
            elif score == 1:
                result["assessment"] = "Moderate quality — some accrual concerns"
            else:
                result["assessment"] = "Low quality — earnings may not be cash-backed"

        except Exception as exc:
            logger.warning("Earnings quality calc failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 5. Cash Conversion Cycle
    # ------------------------------------------------------------------
    def _calc_cash_conversion_cycle(self, income: pd.DataFrame,
                                     balance: pd.DataFrame) -> dict:
        """DSO + DIO - DPO = CCC.  Lower / negative is better."""
        result = {"dso": None, "dio": None, "dpo": None, "ccc": None,
                  "assessment": "N/A"}
        try:
            if income.empty or balance.empty:
                return result

            revenue = _safe_get(income, "Total Revenue")
            cogs = _safe_get(income, "Cost Of Revenue",
                             fallbacks=["Reconciled Cost Of Revenue",
                                        "Cost Of Goods Sold"])

            ar = _safe_get(balance, "Accounts Receivable",
                           fallbacks=["Receivables", "Net Receivables",
                                      "Other Receivables"])
            inventory = _safe_get(balance, "Inventory",
                                  fallbacks=["Net Inventory"])
            ap = _safe_get(balance, "Accounts Payable",
                           fallbacks=["Payable", "Current Accrued Expenses",
                                      "Payables And Accrued Expenses"])

            dso = _safe_div(ar, revenue) * 365 if ar and revenue else None
            dio = _safe_div(inventory, cogs) * 365 if inventory and cogs else None
            dpo = _safe_div(ap, cogs) * 365 if ap and cogs else None

            # CCC = DSO + DIO - DPO (any component can be None)
            ccc = None
            if dso is not None:
                ccc = dso
                if dio is not None:
                    ccc += dio
                if dpo is not None:
                    ccc -= dpo
            elif dio is not None and dpo is not None:
                ccc = dio - dpo

            result["dso"] = round(dso, 1) if dso is not None else None
            result["dio"] = round(dio, 1) if dio is not None else None
            result["dpo"] = round(dpo, 1) if dpo is not None else None
            result["ccc"] = round(ccc, 1) if ccc is not None else None

            if ccc is not None:
                if ccc < 0:
                    result["assessment"] = f"Excellent — negative CCC ({ccc:.0f} days): paid by customers before paying suppliers"
                elif ccc < 30:
                    result["assessment"] = f"Good — short CCC ({ccc:.0f} days)"
                elif ccc < 90:
                    result["assessment"] = f"Average — CCC of {ccc:.0f} days"
                else:
                    result["assessment"] = f"Slow — CCC of {ccc:.0f} days; capital tied up in working cycle"

        except Exception as exc:
            logger.warning("Cash conversion cycle failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 6. Capital Allocation Scoring
    # ------------------------------------------------------------------
    def _calc_capital_allocation(self, income: pd.DataFrame,
                                 cashflow: pd.DataFrame,
                                 info: dict) -> dict:
        """R&D intensity, capex/depreciation, buybacks, debt direction."""
        result = {"rd_intensity": None, "capex_depr_ratio": None,
                  "buyback_yield": None, "net_debt_change": None,
                  "score": 0, "max_score": 4}
        try:
            score = 0

            # R&D intensity
            revenue = _safe_get(income, "Total Revenue") if not income.empty else None
            rd = _safe_get(income, "Research And Development",
                           fallbacks=["Research Development"]) if not income.empty else None

            if rd is not None and revenue and revenue > 0:
                rd_intensity = rd / revenue
                result["rd_intensity"] = round(rd_intensity, 4)
                # High R&D for tech = investing in moat
                if rd_intensity > 0.10:
                    score += 1

            # Capex / Depreciation
            if not cashflow.empty:
                capex = _safe_get(cashflow, "Capital Expenditure")
                depr = _safe_get(cashflow, "Depreciation And Amortization",
                                 fallbacks=["Depreciation Amortization Depletion"])
                # capex from yfinance is typically negative
                capex_abs = abs(capex) if capex is not None else None
                capex_depr = _safe_div(capex_abs, depr)
                if capex_depr is not None:
                    result["capex_depr_ratio"] = round(capex_depr, 2)
                    if capex_depr > 1.0:
                        score += 1  # investing more than maintaining

                # Buyback yield
                buyback = _safe_get(cashflow, "Repurchase Of Capital Stock")
                market_cap = info.get("marketCap")
                if buyback is not None and market_cap and market_cap > 0:
                    # Buyback value is typically negative in cash flow
                    bb_yield = abs(buyback) / market_cap if buyback < 0 else 0
                    result["buyback_yield"] = round(bb_yield, 4)
                    if bb_yield > 0.01:
                        score += 1  # meaningful return to shareholders

                # Net debt change (issuance - repayment)
                issued = _safe_get(cashflow, "Issuance Of Debt",
                                   fallbacks=["Long Term Debt Issuance"]) or 0
                repaid = _safe_get(cashflow, "Repayment Of Debt",
                                   fallbacks=["Long Term Debt Payments"]) or 0
                # Repayment is typically negative in yfinance
                net_debt = issued + repaid  # positive = net borrowing
                result["net_debt_change"] = round(net_debt, 2)
                if net_debt < 0:
                    score += 1  # paying down debt

            result["score"] = score

        except Exception as exc:
            logger.warning("Capital allocation calc failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 7. Multi-Quarter Trend Analysis
    # ------------------------------------------------------------------
    def _calc_quarterly_trends(self, income_q: pd.DataFrame) -> dict:
        """Analyse up to 8 most recent quarters for revenue/margin trends."""
        result = {"quarters": [], "revenue_trend": "N/A",
                  "margin_trend": "N/A", "qoq_growth": []}
        try:
            if income_q.empty:
                return result

            # Take up to 8 quarters (most recent first in yfinance)
            ncols = min(income_q.shape[1], 8)
            quarters: list[dict] = []
            revenues: list[float] = []
            margins: list[float | None] = []
            qoq: list[float | None] = []

            for i in range(ncols):
                col_date = income_q.columns[i]
                rev = _safe_get(income_q, "Total Revenue", col=i)
                gp = _safe_get(income_q, "Gross Profit", col=i)
                ni = _safe_get(income_q, "Net Income", col=i)
                op = _safe_get(income_q, "Operating Income", col=i)

                gm = _safe_div(gp, rev)
                om = _safe_div(op, rev)

                label = col_date.strftime("%Y-Q%q") if hasattr(col_date, "strftime") else str(col_date)
                # pandas Timestamp doesn't have %q; compute quarter manually
                if hasattr(col_date, "quarter"):
                    label = f"{col_date.year}-Q{col_date.quarter}"

                quarters.append({
                    "period": label,
                    "revenue": round(rev, 2) if rev is not None else None,
                    "gross_margin": round(gm, 4) if gm is not None else None,
                    "operating_margin": round(om, 4) if om is not None else None,
                    "net_income": round(ni, 2) if ni is not None else None,
                })

                if rev is not None:
                    revenues.append(rev)
                margins.append(gm)

            # QoQ revenue growth (most recent pair first)
            for i in range(len(revenues) - 1):
                prev = revenues[i + 1]
                curr = revenues[i]
                if prev and prev != 0:
                    qoq.append(round((curr - prev) / abs(prev), 4))
                else:
                    qoq.append(None)

            # Revenue trend via simple linear regression on reversed list
            rev_trend = "N/A"
            if len(revenues) >= 3:
                # revenues[0] is most recent; reverse so index 0 = oldest
                rev_ordered = list(reversed(revenues))
                x = np.arange(len(rev_ordered))
                slope = np.polyfit(x, rev_ordered, 1)[0]
                avg_rev = np.mean(rev_ordered)
                if avg_rev != 0:
                    norm_slope = slope / abs(avg_rev)
                    if norm_slope > 0.02:
                        rev_trend = "Expanding"
                    elif norm_slope < -0.02:
                        rev_trend = "Contracting"
                    else:
                        rev_trend = "Stable"

            # Margin trend
            margin_trend = "N/A"
            valid_margins = [m for m in margins if m is not None]
            if len(valid_margins) >= 3:
                mg_ordered = list(reversed(valid_margins))
                x = np.arange(len(mg_ordered))
                slope_m = np.polyfit(x, mg_ordered, 1)[0]
                if slope_m > 0.005:
                    margin_trend = "Expanding"
                elif slope_m < -0.005:
                    margin_trend = "Contracting"
                else:
                    margin_trend = "Stable"

            result.update(quarters=quarters, revenue_trend=rev_trend,
                          margin_trend=margin_trend, qoq_growth=qoq)

        except Exception as exc:
            logger.warning("Quarterly trend analysis failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # 8. SG&A Efficiency
    # ------------------------------------------------------------------
    def _calc_sga_efficiency(self, income: pd.DataFrame) -> dict:
        """SG&A / Revenue ratio and operating-leverage check."""
        result = {"sga_revenue_ratio": None, "trend": "N/A",
                  "operating_leverage": None}
        try:
            if income.empty:
                return result

            sga_curr = _safe_get(income, "Selling General And Administration",
                                 fallbacks=["Selling General And Administrative"],
                                 col=0)
            rev_curr = _safe_get(income, "Total Revenue", col=0)

            if sga_curr is not None and rev_curr and rev_curr > 0:
                result["sga_revenue_ratio"] = round(sga_curr / rev_curr, 4)

            # Trend: compare current vs previous year
            if income.shape[1] >= 2:
                sga_prev = _safe_get(income, "Selling General And Administration",
                                     fallbacks=["Selling General And Administrative"],
                                     col=1)
                rev_prev = _safe_get(income, "Total Revenue", col=1)

                if (sga_curr is not None and sga_prev is not None
                        and rev_curr and rev_prev and rev_prev > 0
                        and sga_prev > 0):
                    ratio_curr = sga_curr / rev_curr
                    ratio_prev = sga_prev / rev_prev

                    if ratio_curr < ratio_prev - 0.005:
                        result["trend"] = "Improving"
                    elif ratio_curr > ratio_prev + 0.005:
                        result["trend"] = "Deteriorating"
                    else:
                        result["trend"] = "Stable"

                    # Operating leverage: revenue growing faster than SG&A
                    rev_growth = (rev_curr - rev_prev) / abs(rev_prev)
                    sga_growth = (sga_curr - sga_prev) / abs(sga_prev)
                    result["operating_leverage"] = rev_growth > sga_growth

        except Exception as exc:
            logger.warning("SG&A efficiency calc failed: %s", exc)

        return result


# ===========================================================================
# Plugin adapter for pipeline
# ===========================================================================
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer  # noqa: E402


class FundamentalAnalyzerPlugin(_BaseAnalyzer):
    """Pipeline adapter — wraps FundamentalAnalyzer and produces a 0-100 score.

    Weight breakdown (sums to 1.0):
        health           0.20
        growth           0.15
        valuation        0.15
        roic             0.15
        piotroski        0.15
        earnings_quality 0.10
        capital_alloc    0.10
    """
    name = "fundamental"
    default_weight = 0.25

    _WEIGHTS = {
        "health":           0.20,
        "growth":           0.15,
        "valuation":        0.15,
        "roic":             0.15,
        "piotroski":        0.15,
        "earnings_quality": 0.10,
        "capital_alloc":    0.10,
    }

    def __init__(self):
        self._analyzer = FundamentalAnalyzer()

    def analyze(self, ticker, ctx):
        result = self._analyzer.analyze(ticker)

        # Normalise every sub-score to 0-1 range
        def _norm(section_key: str) -> float:
            section = result.get(section_key, {})
            s = section.get("score", 0)
            m = section.get("max_score", 1)
            return s / max(m, 1)

        health_n = _norm("health")
        growth_n = _norm("growth")
        val_n = _norm("valuation")
        roic_n = _norm("roic")
        piotroski_n = _norm("piotroski")
        eq_n = _norm("earnings_quality")
        ca_n = _norm("capital_allocation")

        composite = (
            health_n       * self._WEIGHTS["health"]
            + growth_n     * self._WEIGHTS["growth"]
            + val_n        * self._WEIGHTS["valuation"]
            + roic_n       * self._WEIGHTS["roic"]
            + piotroski_n  * self._WEIGHTS["piotroski"]
            + eq_n         * self._WEIGHTS["earnings_quality"]
            + ca_n         * self._WEIGHTS["capital_alloc"]
        ) * 100

        result["score"] = round(composite, 1)
        return result
