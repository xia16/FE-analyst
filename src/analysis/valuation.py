"""Valuation models - Multi-stage DCF, comparables, dividend discount, Monte Carlo."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from src.data_sources.fundamentals import FundamentalsClient
from src.data_sources.macro_data import MacroDataClient
from src.utils.logger import setup_logger

logger = setup_logger("valuation")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_EQUITY_RISK_PREMIUM = 0.055  # Long-run US ERP (Damodaran)
_DEFAULT_TERMINAL_GROWTH = 0.025
_DEFAULT_TAX_RATE = 0.21  # US corporate statutory rate
_MONTE_CARLO_SIMS = 5000


# ---------------------------------------------------------------------------
# Helper: safe extraction from yfinance info dict
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns *default* when denominator is zero / near-zero."""
    if abs(denominator) < 1e-12:
        return default
    return numerator / denominator


def _extract_row(df: pd.DataFrame, names: list[str]) -> float | None:
    """Try several row labels and return the first hit's most-recent value."""
    for name in names:
        if name in df.index:
            val = df.loc[name].iloc[0]
            if pd.notna(val):
                return float(val)
    return None


# ===================================================================
# Core Valuation Engine
# ===================================================================

class ValuationAnalyzer:
    """Institutional-quality intrinsic value estimation.

    Methods
    -------
    dcf_valuation          Multi-stage DCF with proper WACC & EV-to-equity bridge
    sensitivity_analysis    Growth-rate x discount-rate matrix
    monte_carlo_dcf         Probabilistic DCF via simulation
    comparable_valuation    Peer-multiple relative valuation
    dividend_discount_model Gordon Growth / two-stage DDM
    """

    def __init__(self) -> None:
        self.fundamentals = FundamentalsClient()
        self.macro = MacroDataClient()

    # ------------------------------------------------------------------
    # Market / ticker info helper (cached per call-site)
    # ------------------------------------------------------------------

    def _get_ticker_info(self, ticker: str) -> dict:
        """Fetch yfinance .info dict with error handling."""
        try:
            return yf.Ticker(ticker).info or {}
        except Exception as exc:
            logger.warning("Failed to fetch ticker info for %s: %s", ticker, exc)
            return {}

    # ------------------------------------------------------------------
    # WACC calculation
    # ------------------------------------------------------------------

    def calculate_wacc(self, ticker: str, info: dict | None = None) -> dict:
        """Compute Weighted Average Cost of Capital.

        CAPM cost of equity: Rf + beta * ERP
        After-tax cost of debt: (Interest Expense / Total Debt) * (1 - tax)
        Weights from market-cap based capital structure.

        Returns dict with wacc and all intermediate components.
        """
        if info is None:
            info = self._get_ticker_info(ticker)

        # --- Risk-free rate ---
        risk_free_rate = self.macro.get_risk_free_rate()

        # --- Beta ---
        beta = _safe_float(info.get("beta"), default=1.0)
        beta = max(0.2, min(beta, 3.0))  # clamp to reasonable range

        # --- Cost of equity (CAPM) ---
        cost_of_equity = risk_free_rate + beta * _DEFAULT_EQUITY_RISK_PREMIUM

        # --- Cost of debt ---
        income = self.fundamentals.get_income_statement(ticker)
        balance = self.fundamentals.get_balance_sheet(ticker)

        interest_expense = 0.0
        total_debt = 0.0

        if not income.empty:
            interest_expense = abs(
                _safe_float(
                    _extract_row(income, ["Interest Expense", "Interest Expense Non Operating"])
                )
            )

        if not balance.empty:
            total_debt = _safe_float(
                _extract_row(balance, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
            )

        pre_tax_cost_of_debt = _safe_div(interest_expense, total_debt, default=0.05)
        # Clamp cost of debt to reasonable range
        pre_tax_cost_of_debt = max(0.01, min(pre_tax_cost_of_debt, 0.20))
        after_tax_cost_of_debt = pre_tax_cost_of_debt * (1 - _DEFAULT_TAX_RATE)

        # --- Capital structure weights ---
        market_cap = _safe_float(info.get("marketCap"), default=0.0)

        if market_cap <= 0:
            # Fallback: estimate from price * shares
            price = _safe_float(
                info.get("currentPrice", info.get("regularMarketPrice")), default=0.0
            )
            shares = _safe_float(info.get("sharesOutstanding"), default=0.0)
            market_cap = price * shares

        total_capital = market_cap + total_debt
        weight_equity = _safe_div(market_cap, total_capital, default=1.0)
        weight_debt = 1.0 - weight_equity

        wacc = weight_equity * cost_of_equity + weight_debt * after_tax_cost_of_debt

        # Floor WACC at a sensible minimum
        wacc = max(wacc, 0.05)

        return {
            "wacc": round(wacc, 6),
            "cost_of_equity": round(cost_of_equity, 6),
            "cost_of_debt_pretax": round(pre_tax_cost_of_debt, 6),
            "cost_of_debt_aftertax": round(after_tax_cost_of_debt, 6),
            "risk_free_rate": round(risk_free_rate, 6),
            "beta": round(beta, 4),
            "equity_risk_premium": _DEFAULT_EQUITY_RISK_PREMIUM,
            "tax_rate": _DEFAULT_TAX_RATE,
            "market_cap": market_cap,
            "total_debt": total_debt,
            "weight_equity": round(weight_equity, 4),
            "weight_debt": round(weight_debt, 4),
        }

    # ------------------------------------------------------------------
    # Multi-stage DCF
    # ------------------------------------------------------------------

    def dcf_valuation(
        self,
        ticker: str,
        growth_rate: float = 0.08,
        terminal_growth: float = _DEFAULT_TERMINAL_GROWTH,
        discount_rate: float | None = None,
        stage1_years: int = 5,
        stage2_years: int = 5,
        stage1_margin: float | None = None,
        stage2_margin: float | None = None,
        terminal_margin: float | None = None,
    ) -> dict:
        """Three-stage discounted cash flow valuation.

        Stage 1 (years 1 .. stage1_years):
            Explicit high-growth at *growth_rate* with optional margin override.
        Stage 2 (years stage1_years+1 .. stage1_years+stage2_years):
            Growth linearly decays from *growth_rate* to *terminal_growth*.
        Stage 3:
            Terminal value via Gordon growth model.

        Enterprise Value = PV(Stage 1 FCFs) + PV(Stage 2 FCFs) + PV(Terminal Value)
        Equity Value     = EV - Net Debt  (total_debt - cash)
        Intrinsic / shr  = Equity Value / Shares Outstanding

        Parameters
        ----------
        ticker : str
        growth_rate : float  Stage-1 FCF growth rate
        terminal_growth : float  Perpetuity growth rate
        discount_rate : float | None  Override WACC (auto-calculated when None)
        stage1_years : int  Length of high-growth period
        stage2_years : int  Length of transition period
        stage1_margin, stage2_margin, terminal_margin : float | None
            FCF margin adjustments (multiplier, e.g. 1.05 = +5 pp expansion).
            None means no margin adjustment (margins stay constant).
        """
        # --- Fetch cash flow ---
        cf = self.fundamentals.get_cash_flow(ticker)
        if cf.empty:
            return {"error": "No cash flow data available"}

        current_fcf = _extract_row(cf, ["Free Cash Flow"])
        if current_fcf is None:
            return {"error": "Free Cash Flow not found in statements"}

        # --- Ticker info ---
        info = self._get_ticker_info(ticker)

        # --- WACC ---
        wacc_details: dict = {}
        if discount_rate is None:
            wacc_details = self.calculate_wacc(ticker, info=info)
            discount_rate = wacc_details["wacc"]

        if discount_rate <= terminal_growth:
            return {"error": f"Discount rate ({discount_rate:.4f}) must exceed terminal growth ({terminal_growth:.4f})"}

        # --- Project FCFs ---
        projected_fcfs: list[float] = []
        stages: list[int] = []

        # Stage 1 - high growth
        margin_mult_1 = stage1_margin if stage1_margin is not None else 1.0
        for year in range(1, stage1_years + 1):
            fcf = current_fcf * ((1 + growth_rate) ** year) * margin_mult_1
            projected_fcfs.append(fcf)
            stages.append(1)

        # Stage 2 - linear decay from growth_rate to terminal_growth
        margin_mult_2 = stage2_margin if stage2_margin is not None else 1.0
        for i in range(stage2_years):
            # Linear interpolation of growth rate
            blend = (i + 1) / (stage2_years + 1)
            decayed_growth = growth_rate * (1 - blend) + terminal_growth * blend
            # Base is the last projected FCF
            prev_fcf = projected_fcfs[-1] if projected_fcfs else current_fcf
            fcf = prev_fcf * (1 + decayed_growth) * margin_mult_2
            projected_fcfs.append(fcf)
            stages.append(2)

        # Terminal value (Gordon growth on last projected FCF)
        margin_mult_t = terminal_margin if terminal_margin is not None else 1.0
        final_fcf = projected_fcfs[-1] if projected_fcfs else current_fcf
        terminal_fcf = final_fcf * (1 + terminal_growth) * margin_mult_t
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)

        total_years = stage1_years + stage2_years

        # --- Discount to present ---
        pv_fcfs = sum(
            fcf / (1 + discount_rate) ** yr
            for yr, fcf in enumerate(projected_fcfs, 1)
        )
        pv_terminal = terminal_value / (1 + discount_rate) ** total_years

        enterprise_value = pv_fcfs + pv_terminal

        # --- EV to Equity bridge ---
        balance = self.fundamentals.get_balance_sheet(ticker)
        total_debt = 0.0
        cash = 0.0
        if not balance.empty:
            total_debt = _safe_float(
                _extract_row(balance, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
            )
            cash = _safe_float(
                _extract_row(balance, [
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash Financial",
                ])
            )

        net_debt = total_debt - cash
        equity_value = enterprise_value - net_debt

        # --- Per-share ---
        shares_outstanding = _safe_float(info.get("sharesOutstanding"), default=1.0)
        if shares_outstanding <= 0:
            shares_outstanding = 1.0

        intrinsic_per_share = equity_value / shares_outstanding
        current_price = _safe_float(
            info.get("currentPrice", info.get("regularMarketPrice")), default=0.0
        )

        margin_of_safety = (
            (intrinsic_per_share - current_price) / intrinsic_per_share * 100
            if intrinsic_per_share > 0
            else 0.0
        )

        verdict = (
            "UNDERVALUED" if margin_of_safety > 15
            else "FAIR" if margin_of_safety > -10
            else "OVERVALUED"
        )

        return {
            "model": "multi_stage_dcf",
            "current_fcf": current_fcf,
            "discount_rate": round(discount_rate, 6),
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "stage1_years": stage1_years,
            "stage2_years": stage2_years,
            "projected_fcfs": [round(f, 2) for f in projected_fcfs],
            "pv_fcfs": round(pv_fcfs, 2),
            "terminal_value": round(terminal_value, 2),
            "pv_terminal": round(pv_terminal, 2),
            "enterprise_value": round(enterprise_value, 2),
            "total_debt": round(total_debt, 2),
            "cash": round(cash, 2),
            "net_debt": round(net_debt, 2),
            "equity_value": round(equity_value, 2),
            "shares_outstanding": shares_outstanding,
            "intrinsic_per_share": round(intrinsic_per_share, 2),
            "current_price": current_price,
            "margin_of_safety_pct": round(margin_of_safety, 2),
            "verdict": verdict,
            "wacc_details": wacc_details,
        }

    # ------------------------------------------------------------------
    # Internal: stripped-down DCF for Monte Carlo / sensitivity
    # ------------------------------------------------------------------

    def _dcf_intrinsic_per_share(
        self,
        current_fcf: float,
        growth_rate: float,
        discount_rate: float,
        terminal_growth: float,
        stage1_years: int,
        stage2_years: int,
        net_debt: float,
        shares_outstanding: float,
    ) -> float:
        """Fast inner DCF returning only intrinsic value per share.

        Used by sensitivity_analysis and monte_carlo_dcf to avoid redundant
        I/O in tight loops.
        """
        if discount_rate <= terminal_growth:
            return 0.0

        projected_fcfs: list[float] = []

        # Stage 1
        for year in range(1, stage1_years + 1):
            projected_fcfs.append(current_fcf * ((1 + growth_rate) ** year))

        # Stage 2 - linear decay
        for i in range(stage2_years):
            blend = (i + 1) / (stage2_years + 1)
            decayed_growth = growth_rate * (1 - blend) + terminal_growth * blend
            prev_fcf = projected_fcfs[-1] if projected_fcfs else current_fcf
            projected_fcfs.append(prev_fcf * (1 + decayed_growth))

        total_years = stage1_years + stage2_years
        final_fcf = projected_fcfs[-1] if projected_fcfs else current_fcf
        terminal_value = final_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)

        pv_fcfs = sum(
            fcf / (1 + discount_rate) ** yr
            for yr, fcf in enumerate(projected_fcfs, 1)
        )
        pv_terminal = terminal_value / (1 + discount_rate) ** total_years

        enterprise_value = pv_fcfs + pv_terminal
        equity_value = enterprise_value - net_debt

        return equity_value / shares_outstanding if shares_outstanding > 0 else 0.0

    # ------------------------------------------------------------------
    # Sensitivity Analysis
    # ------------------------------------------------------------------

    def sensitivity_analysis(
        self,
        ticker: str,
        base_growth: float | None = None,
        base_wacc: float | None = None,
        terminal_growth: float = _DEFAULT_TERMINAL_GROWTH,
        growth_step: float = 0.01,
        growth_spread: float = 0.02,
        wacc_step: float = 0.005,
        wacc_spread: float = 0.02,
        stage1_years: int = 5,
        stage2_years: int = 5,
    ) -> dict:
        """Generate a growth-rate x discount-rate sensitivity matrix.

        Rows:  base_growth +/- growth_spread in growth_step increments
        Cols:  base_wacc   +/- wacc_spread  in wacc_step   increments

        Each cell contains the intrinsic value per share.

        Returns
        -------
        dict with keys: matrix (nested dict), growth_rates, discount_rates,
                        base_growth, base_wacc, current_price
        """
        # --- Fetch fundamentals once ---
        cf = self.fundamentals.get_cash_flow(ticker)
        if cf.empty:
            return {"error": "No cash flow data available"}
        current_fcf = _extract_row(cf, ["Free Cash Flow"])
        if current_fcf is None:
            return {"error": "Free Cash Flow not found"}

        info = self._get_ticker_info(ticker)

        if base_wacc is None:
            wacc_details = self.calculate_wacc(ticker, info=info)
            base_wacc = wacc_details["wacc"]
        if base_growth is None:
            base_growth = 0.08

        # Net debt
        balance = self.fundamentals.get_balance_sheet(ticker)
        total_debt = 0.0
        cash = 0.0
        if not balance.empty:
            total_debt = _safe_float(
                _extract_row(balance, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
            )
            cash = _safe_float(
                _extract_row(balance, [
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash Financial",
                ])
            )
        net_debt = total_debt - cash

        shares = _safe_float(info.get("sharesOutstanding"), default=1.0)
        if shares <= 0:
            shares = 1.0
        current_price = _safe_float(
            info.get("currentPrice", info.get("regularMarketPrice")), default=0.0
        )

        # --- Build axes ---
        growth_rates = np.arange(
            base_growth - growth_spread,
            base_growth + growth_spread + growth_step / 2,
            growth_step,
        ).tolist()
        discount_rates = np.arange(
            base_wacc - wacc_spread,
            base_wacc + wacc_spread + wacc_step / 2,
            wacc_step,
        ).tolist()

        # Filter out non-positive discount rates and rates below terminal growth
        discount_rates = [r for r in discount_rates if r > terminal_growth + 0.005]

        # --- Compute matrix ---
        matrix: dict[str, dict[str, float]] = {}
        for g in growth_rates:
            g_key = f"{g:.4f}"
            matrix[g_key] = {}
            for d in discount_rates:
                d_key = f"{d:.4f}"
                iv = self._dcf_intrinsic_per_share(
                    current_fcf=current_fcf,
                    growth_rate=g,
                    discount_rate=d,
                    terminal_growth=terminal_growth,
                    stage1_years=stage1_years,
                    stage2_years=stage2_years,
                    net_debt=net_debt,
                    shares_outstanding=shares,
                )
                matrix[g_key][d_key] = round(iv, 2)

        return {
            "ticker": ticker,
            "matrix": matrix,
            "growth_rates": [round(g, 4) for g in growth_rates],
            "discount_rates": [round(d, 4) for d in discount_rates],
            "base_growth": round(base_growth, 4),
            "base_wacc": round(base_wacc, 4),
            "terminal_growth": terminal_growth,
            "current_price": current_price,
        }

    # ------------------------------------------------------------------
    # Monte Carlo DCF
    # ------------------------------------------------------------------

    def monte_carlo_dcf(
        self,
        ticker: str,
        growth_mean: float | None = None,
        growth_std: float = 0.02,
        wacc_mean: float | None = None,
        wacc_std: float = 0.01,
        terminal_growth_mean: float = _DEFAULT_TERMINAL_GROWTH,
        terminal_growth_std: float = 0.005,
        n_simulations: int = _MONTE_CARLO_SIMS,
        stage1_years: int = 5,
        stage2_years: int = 5,
    ) -> dict:
        """Probabilistic DCF via Monte Carlo simulation.

        Draws *n_simulations* sets of (growth_rate, wacc, terminal_growth)
        from normal distributions, computes intrinsic value for each, and
        returns distributional statistics.

        Parameters
        ----------
        growth_mean / growth_std : growth rate distribution
        wacc_mean / wacc_std     : discount rate distribution
        terminal_growth_mean/std : terminal growth distribution
        n_simulations            : number of simulation runs (default 5000)

        Returns
        -------
        dict with mean, median, percentiles (p10..p90), probability of
        undervaluation, and histogram bucket counts.
        """
        # --- Fetch fundamentals once ---
        cf = self.fundamentals.get_cash_flow(ticker)
        if cf.empty:
            return {"error": "No cash flow data available"}
        current_fcf = _extract_row(cf, ["Free Cash Flow"])
        if current_fcf is None:
            return {"error": "Free Cash Flow not found"}

        info = self._get_ticker_info(ticker)

        if wacc_mean is None:
            wacc_details = self.calculate_wacc(ticker, info=info)
            wacc_mean = wacc_details["wacc"]
        if growth_mean is None:
            growth_mean = 0.08

        # Net debt
        balance = self.fundamentals.get_balance_sheet(ticker)
        total_debt = 0.0
        cash = 0.0
        if not balance.empty:
            total_debt = _safe_float(
                _extract_row(balance, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
            )
            cash = _safe_float(
                _extract_row(balance, [
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash Financial",
                ])
            )
        net_debt = total_debt - cash

        shares = _safe_float(info.get("sharesOutstanding"), default=1.0)
        if shares <= 0:
            shares = 1.0
        current_price = _safe_float(
            info.get("currentPrice", info.get("regularMarketPrice")), default=0.0
        )

        # --- Draw random parameters ---
        rng = np.random.default_rng()
        sim_growth = rng.normal(growth_mean, growth_std, n_simulations)
        sim_wacc = rng.normal(wacc_mean, wacc_std, n_simulations)
        sim_tg = rng.normal(terminal_growth_mean, terminal_growth_std, n_simulations)

        # Clamp: wacc must exceed terminal growth by at least 50 bps
        sim_wacc = np.clip(sim_wacc, 0.03, 0.25)
        sim_tg = np.clip(sim_tg, 0.005, 0.05)

        # --- Run simulations ---
        results = np.empty(n_simulations, dtype=np.float64)
        for i in range(n_simulations):
            g = float(sim_growth[i])
            d = float(sim_wacc[i])
            tg = float(sim_tg[i])
            # Enforce discount > terminal growth
            if d <= tg + 0.005:
                d = tg + 0.005
            results[i] = self._dcf_intrinsic_per_share(
                current_fcf=current_fcf,
                growth_rate=g,
                discount_rate=d,
                terminal_growth=tg,
                stage1_years=stage1_years,
                stage2_years=stage2_years,
                net_debt=net_debt,
                shares_outstanding=shares,
            )

        # Filter out non-positive / extreme outliers for stats
        valid = results[np.isfinite(results)]

        if len(valid) == 0:
            return {"error": "All simulations produced invalid results"}

        prob_undervalued = float(np.mean(valid > current_price) * 100) if current_price > 0 else 0.0

        return {
            "ticker": ticker,
            "n_simulations": n_simulations,
            "current_price": current_price,
            "mean": round(float(np.mean(valid)), 2),
            "median": round(float(np.median(valid)), 2),
            "std": round(float(np.std(valid)), 2),
            "p10": round(float(np.percentile(valid, 10)), 2),
            "p25": round(float(np.percentile(valid, 25)), 2),
            "p75": round(float(np.percentile(valid, 75)), 2),
            "p90": round(float(np.percentile(valid, 90)), 2),
            "min": round(float(np.min(valid)), 2),
            "max": round(float(np.max(valid)), 2),
            "probability_undervalued_pct": round(prob_undervalued, 2),
            "parameters": {
                "growth_mean": growth_mean,
                "growth_std": growth_std,
                "wacc_mean": wacc_mean,
                "wacc_std": wacc_std,
                "terminal_growth_mean": terminal_growth_mean,
                "terminal_growth_std": terminal_growth_std,
            },
        }

    # ------------------------------------------------------------------
    # Comparable (Relative) Valuation
    # ------------------------------------------------------------------

    def comparable_valuation(self, ticker: str, peers: list[str] | None = None) -> dict:
        """Valuation by comparing multiples to peers.

        Computes premium/discount on P/E, P/B, EV/EBITDA, P/S, EV/Revenue
        and derives implied values from each peer-median multiple.

        Returns
        -------
        dict with per-metric comparison, implied values, and summary range.
        """
        ratios = self.fundamentals.get_key_ratios(ticker)
        info = self._get_ticker_info(ticker)

        if peers is None:
            peers = self.fundamentals.get_peers(ticker)[:5]
        if not peers:
            return {"error": "No peer companies available"}

        # Remove self from peers if present
        peers = [p for p in peers if p.upper() != ticker.upper()]
        if not peers:
            return {"error": "Peer list only contained the target ticker"}

        peer_ratios_list: list[dict] = []
        for p in peers:
            try:
                pr = self.fundamentals.get_key_ratios(p)
                peer_ratios_list.append(pr)
            except Exception:
                continue

        if not peer_ratios_list:
            return {"error": "Could not fetch peer data"}

        current_price = _safe_float(
            info.get("currentPrice", info.get("regularMarketPrice")), default=0.0
        )
        shares = _safe_float(info.get("sharesOutstanding"), default=1.0)
        if shares <= 0:
            shares = 1.0
        market_cap = _safe_float(info.get("marketCap"), default=current_price * shares)

        # Company financial metrics needed for implied value
        # EPS = price / PE, Book/share = price / PB, etc.
        eps = _safe_div(current_price, _safe_float(ratios.get("pe_forward"))) if ratios.get("pe_forward") else 0.0
        book_per_share = _safe_div(current_price, _safe_float(ratios.get("pb_ratio"))) if ratios.get("pb_ratio") else 0.0
        revenue_per_share = _safe_div(current_price, _safe_float(ratios.get("ps_ratio"))) if ratios.get("ps_ratio") else 0.0

        # For EV-based multiples, we need enterprise value and EBITDA
        ev_ebitda_company = _safe_float(ratios.get("ev_ebitda"))
        enterprise_value = _safe_float(info.get("enterpriseValue"), default=0.0)
        ebitda = _safe_div(enterprise_value, ev_ebitda_company) if ev_ebitda_company > 0 else 0.0

        # Revenue for EV/Revenue
        total_revenue = _safe_float(info.get("totalRevenue"), default=0.0)
        ev_revenue_company = _safe_div(enterprise_value, total_revenue) if total_revenue > 0 else 0.0

        # Net debt for EV -> equity bridge
        balance = self.fundamentals.get_balance_sheet(ticker)
        total_debt_val = 0.0
        cash_val = 0.0
        if not balance.empty:
            total_debt_val = _safe_float(
                _extract_row(balance, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
            )
            cash_val = _safe_float(
                _extract_row(balance, [
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash Financial",
                ])
            )
        net_debt = total_debt_val - cash_val

        # Metric definitions: (ratio_key, company_metric_per_share, is_ev_based)
        metric_defs: list[tuple[str, str, float, bool]] = [
            ("P/E", "pe_forward", eps, False),
            ("P/B", "pb_ratio", book_per_share, False),
            ("EV/EBITDA", "ev_ebitda", ebitda, True),
            ("P/S", "ps_ratio", revenue_per_share, False),
            ("EV/Revenue", "_ev_revenue", total_revenue, True),
        ]

        comparison: dict[str, dict] = {}
        implied_values: dict[str, float | None] = {}

        for label, ratio_key, company_metric, is_ev_based in metric_defs:
            # Get company value
            if ratio_key == "_ev_revenue":
                company_val = ev_revenue_company
            else:
                company_val = _safe_float(ratios.get(ratio_key)) if ratios.get(ratio_key) is not None else None

            # Get peer values
            if ratio_key == "_ev_revenue":
                # Must compute EV/Revenue for each peer
                peer_vals: list[float] = []
                for pr in peer_ratios_list:
                    pr_info = self._get_ticker_info(pr.get("ticker", ""))
                    pr_ev = _safe_float(pr_info.get("enterpriseValue"))
                    pr_rev = _safe_float(pr_info.get("totalRevenue"))
                    if pr_ev > 0 and pr_rev > 0:
                        peer_vals.append(pr_ev / pr_rev)
            else:
                peer_vals = [
                    _safe_float(pr.get(ratio_key))
                    for pr in peer_ratios_list
                    if pr.get(ratio_key) is not None and _safe_float(pr.get(ratio_key)) > 0
                ]

            if not peer_vals:
                comparison[label] = {"company": company_val, "peer_median": None, "premium_pct": None}
                implied_values[label] = None
                continue

            median_val = float(np.median(peer_vals))

            premium_pct = (
                round((company_val / median_val - 1) * 100, 2)
                if company_val is not None and company_val > 0 and median_val > 0
                else None
            )

            comparison[label] = {
                "company": round(company_val, 2) if company_val is not None else None,
                "peer_median": round(median_val, 2),
                "premium_pct": premium_pct,
            }

            # Implied value from peer median multiple
            if company_metric > 0 and median_val > 0:
                if is_ev_based:
                    # implied EV -> subtract net debt -> divide by shares
                    implied_ev = median_val * company_metric
                    implied_equity = implied_ev - net_debt
                    implied_per_share = implied_equity / shares
                else:
                    implied_per_share = median_val * company_metric
                implied_values[label] = round(implied_per_share, 2)
            else:
                implied_values[label] = None

        # Summary range
        valid_implied = [v for v in implied_values.values() if v is not None and v > 0]
        summary_range = {
            "low": round(min(valid_implied), 2) if valid_implied else None,
            "high": round(max(valid_implied), 2) if valid_implied else None,
            "median": round(float(np.median(valid_implied)), 2) if valid_implied else None,
        }

        # Average premium/discount across all metrics
        valid_premiums = [
            v["premium_pct"]
            for v in comparison.values()
            if v.get("premium_pct") is not None
        ]
        avg_premium = round(float(np.mean(valid_premiums)), 2) if valid_premiums else None

        return {
            "ticker": ticker,
            "peers": peers,
            "current_price": current_price,
            "comparison": comparison,
            "implied_values": implied_values,
            "implied_value_range": summary_range,
            "average_premium_pct": avg_premium,
        }

    # ------------------------------------------------------------------
    # Dividend Discount Model
    # ------------------------------------------------------------------

    def dividend_discount_model(
        self,
        ticker: str,
        cost_of_equity: float | None = None,
        high_growth_rate: float | None = None,
        high_growth_years: int = 5,
        terminal_growth: float = _DEFAULT_TERMINAL_GROWTH,
    ) -> dict:
        """Dividend Discount Model.

        If the company pays no dividend, returns a skip notice.

        For stable-growth payers (dividend growth < 4%), uses Gordon Growth
        Model: P = D1 / (ke - g).

        For higher-growth payers, uses a two-stage DDM:
            Stage 1: Explicit high-growth dividends discounted back.
            Stage 2: Gordon growth on the final dividend.

        Parameters
        ----------
        cost_of_equity : float | None  Override (auto-calculated via CAPM)
        high_growth_rate : float | None  Override stage-1 dividend growth
        high_growth_years : int  Years of high growth before reversion
        terminal_growth : float  Long-run dividend growth rate
        """
        info = self._get_ticker_info(ticker)

        # --- Check if company pays dividends ---
        dividend_rate = _safe_float(info.get("dividendRate"), default=0.0)
        trailing_annual_dividend = _safe_float(info.get("trailingAnnualDividendRate"), default=0.0)
        current_dividend = max(dividend_rate, trailing_annual_dividend)

        if current_dividend <= 0:
            return {
                "model": "ddm",
                "ticker": ticker,
                "skipped": True,
                "reason": "Company does not pay dividends",
            }

        current_price = _safe_float(
            info.get("currentPrice", info.get("regularMarketPrice")), default=0.0
        )

        # --- Cost of equity ---
        if cost_of_equity is None:
            wacc_data = self.calculate_wacc(ticker, info=info)
            cost_of_equity = wacc_data["cost_of_equity"]

        if cost_of_equity <= terminal_growth:
            return {"error": f"Cost of equity ({cost_of_equity:.4f}) must exceed terminal growth ({terminal_growth:.4f})"}

        # --- Estimate dividend growth ---
        # Use 5-year dividend growth if available, else earnings growth
        five_yr_div_growth = _safe_float(info.get("fiveYearAvgDividendYield"), default=0.0)
        earnings_growth = _safe_float(info.get("earningsGrowth"), default=0.0)
        payout_ratio = _safe_float(info.get("payoutRatio"), default=0.0)

        # Sustainable growth = ROE * (1 - payout)
        roe = _safe_float(info.get("returnOnEquity"), default=0.0)
        sustainable_growth = roe * (1 - payout_ratio) if roe > 0 and 0 < payout_ratio < 1 else 0.0

        # Use the best available growth estimate
        if high_growth_rate is not None:
            estimated_growth = high_growth_rate
        elif earnings_growth > 0:
            estimated_growth = min(earnings_growth, 0.25)  # cap at 25%
        elif sustainable_growth > 0:
            estimated_growth = min(sustainable_growth, 0.25)
        else:
            estimated_growth = terminal_growth

        # --- Model selection ---
        stable_threshold = 0.04  # Use Gordon Growth if growth < 4%
        use_gordon = estimated_growth <= stable_threshold

        if use_gordon:
            # Gordon Growth Model: P = D1 / (ke - g)
            d1 = current_dividend * (1 + estimated_growth)
            intrinsic_value = d1 / (cost_of_equity - estimated_growth)

            model_used = "gordon_growth"
            stage_details = {
                "d0": round(current_dividend, 4),
                "d1": round(d1, 4),
                "growth_rate": round(estimated_growth, 4),
            }
        else:
            # Two-stage DDM
            projected_dividends: list[float] = []
            for year in range(1, high_growth_years + 1):
                d = current_dividend * ((1 + estimated_growth) ** year)
                projected_dividends.append(d)

            # PV of stage 1 dividends
            pv_stage1 = sum(
                d / (1 + cost_of_equity) ** yr
                for yr, d in enumerate(projected_dividends, 1)
            )

            # Terminal value at end of high-growth period
            final_div = projected_dividends[-1]
            terminal_div = final_div * (1 + terminal_growth)
            terminal_value = terminal_div / (cost_of_equity - terminal_growth)
            pv_terminal = terminal_value / (1 + cost_of_equity) ** high_growth_years

            intrinsic_value = pv_stage1 + pv_terminal

            model_used = "two_stage_ddm"
            stage_details = {
                "d0": round(current_dividend, 4),
                "high_growth_rate": round(estimated_growth, 4),
                "high_growth_years": high_growth_years,
                "terminal_growth": round(terminal_growth, 4),
                "projected_dividends": [round(d, 4) for d in projected_dividends],
                "pv_stage1": round(pv_stage1, 2),
                "terminal_value": round(terminal_value, 2),
                "pv_terminal": round(pv_terminal, 2),
            }

        margin_of_safety = (
            (intrinsic_value - current_price) / intrinsic_value * 100
            if intrinsic_value > 0
            else 0.0
        )

        return {
            "model": model_used,
            "ticker": ticker,
            "skipped": False,
            "intrinsic_value": round(intrinsic_value, 2),
            "current_price": current_price,
            "current_dividend": round(current_dividend, 4),
            "cost_of_equity": round(cost_of_equity, 6),
            "margin_of_safety_pct": round(margin_of_safety, 2),
            "verdict": (
                "UNDERVALUED" if margin_of_safety > 15
                else "FAIR" if margin_of_safety > -10
                else "OVERVALUED"
            ),
            "stage_details": stage_details,
        }


# ===================================================================
# Plugin adapter for pipeline
# ===================================================================
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class ValuationAnalyzerPlugin(_BaseAnalyzer):
    """Pipeline-compatible valuation analyzer.

    Runs multi-stage DCF, Monte Carlo simulation, comparable valuation,
    and DDM, then synthesises a composite score (0-100).

    Score composition
    -----------------
    - DCF margin of safety        : 40 % weight
    - Monte Carlo P(undervalued)  : 30 % weight
    - Comparable premium/discount : 20 % weight
    - DDM margin of safety        : 10 % weight  (0 if no dividend)
    """

    name = "valuation"
    default_weight = 0.20

    def __init__(self) -> None:
        self._analyzer = ValuationAnalyzer()

    # ------------------------------------------------------------------ #
    # Scoring helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _score_margin_of_safety(mos_pct: float) -> float:
        """Map margin-of-safety percentage to a 0-100 score.

        -50 % or worse  ->   0
          0 %           ->  50
        +50 % or better -> 100
        Linear between breakpoints.
        """
        return max(0.0, min(100.0, 50.0 + mos_pct))

    @staticmethod
    def _score_mc_probability(prob_pct: float) -> float:
        """Map Monte Carlo undervaluation probability (0-100 %) to a 0-100 score.

          0 % probability ->   0
        100 % probability -> 100
        """
        return max(0.0, min(100.0, prob_pct))

    @staticmethod
    def _score_comparable_premium(avg_premium_pct: float | None) -> float:
        """Map average peer premium/discount to a 0-100 score.

        Trading at -40 % discount vs peers -> 90
        Trading at   0 % (in-line)         -> 50
        Trading at +40 % premium vs peers  -> 10
        """
        if avg_premium_pct is None:
            return 50.0  # neutral if unavailable
        return max(0.0, min(100.0, 50.0 - avg_premium_pct))

    # ------------------------------------------------------------------ #
    # Main analyse entry point
    # ------------------------------------------------------------------ #

    def analyze(self, ticker: str, ctx: Any = None) -> dict:
        """Run all valuation models and produce a composite score.

        Parameters
        ----------
        ticker : str
        ctx : PipelineContext (unused directly; maintained for interface)

        Returns
        -------
        dict with ``score`` key (0-100) and all sub-model results.
        """
        results: dict[str, Any] = {"ticker": ticker}

        # --- DCF ---
        try:
            dcf = self._analyzer.dcf_valuation(ticker)
        except Exception as exc:
            logger.error("DCF failed for %s: %s", ticker, exc)
            dcf = {"error": f"DCF failed: {exc}"}
        results["dcf"] = dcf

        # --- Monte Carlo ---
        try:
            mc = self._analyzer.monte_carlo_dcf(ticker)
        except Exception as exc:
            logger.error("Monte Carlo failed for %s: %s", ticker, exc)
            mc = {"error": f"Monte Carlo failed: {exc}"}
        results["monte_carlo"] = mc

        # --- Comparables ---
        try:
            comps = self._analyzer.comparable_valuation(ticker)
        except Exception as exc:
            logger.error("Comparable valuation failed for %s: %s", ticker, exc)
            comps = {"error": f"Comparable valuation failed: {exc}"}
        results["comparable"] = comps

        # --- DDM ---
        try:
            ddm = self._analyzer.dividend_discount_model(ticker)
        except Exception as exc:
            logger.error("DDM failed for %s: %s", ticker, exc)
            ddm = {"error": f"DDM failed: {exc}"}
        results["ddm"] = ddm

        # --- Composite score ---
        # DCF score (40 % weight)
        dcf_mos = dcf.get("margin_of_safety_pct", 0.0) if "error" not in dcf else 0.0
        dcf_score = self._score_margin_of_safety(dcf_mos)

        # Monte Carlo score (30 % weight)
        mc_prob = mc.get("probability_undervalued_pct", 50.0) if "error" not in mc else 50.0
        mc_score = self._score_mc_probability(mc_prob)

        # Comparable score (20 % weight)
        comp_premium = comps.get("average_premium_pct") if "error" not in comps else None
        comp_score = self._score_comparable_premium(comp_premium)

        # DDM score (10 % weight, reallocated to DCF if no dividend)
        ddm_available = "error" not in ddm and not ddm.get("skipped", False)
        if ddm_available:
            ddm_mos = ddm.get("margin_of_safety_pct", 0.0)
            ddm_score = self._score_margin_of_safety(ddm_mos)
            w_dcf, w_mc, w_comp, w_ddm = 0.40, 0.30, 0.20, 0.10
        else:
            ddm_score = 0.0
            # Reallocate DDM weight to DCF
            w_dcf, w_mc, w_comp, w_ddm = 0.50, 0.30, 0.20, 0.00

        composite = (
            w_dcf * dcf_score
            + w_mc * mc_score
            + w_comp * comp_score
            + w_ddm * ddm_score
        )

        results["component_scores"] = {
            "dcf_score": round(dcf_score, 2),
            "monte_carlo_score": round(mc_score, 2),
            "comparable_score": round(comp_score, 2),
            "ddm_score": round(ddm_score, 2) if ddm_available else None,
            "weights": {"dcf": w_dcf, "monte_carlo": w_mc, "comparable": w_comp, "ddm": w_ddm},
        }
        results["score"] = round(max(0.0, min(100.0, composite)), 1)

        return results
