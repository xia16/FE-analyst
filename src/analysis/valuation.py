"""Valuation models - DCF, comparables, dividend discount."""

import numpy as np
import pandas as pd

from src.data_sources.fundamentals import FundamentalsClient
from src.data_sources.macro_data import MacroDataClient
from src.utils.logger import setup_logger

logger = setup_logger("valuation")


class ValuationAnalyzer:
    """Estimate intrinsic value using multiple methods."""

    def __init__(self):
        self.fundamentals = FundamentalsClient()
        self.macro = MacroDataClient()

    def dcf_valuation(
        self,
        ticker: str,
        growth_rate: float = 0.08,
        terminal_growth: float = 0.025,
        discount_rate: float | None = None,
        projection_years: int = 5,
    ) -> dict:
        """Simple discounted cash flow valuation.

        Args:
            ticker: Stock symbol
            growth_rate: Expected FCF growth rate
            terminal_growth: Long-term terminal growth rate
            discount_rate: WACC / required return (auto-calculated if None)
            projection_years: Years to project
        """
        cf = self.fundamentals.get_cash_flow(ticker)
        if cf.empty:
            return {"error": "No cash flow data available"}

        # Get most recent free cash flow
        fcf_row = cf.loc["Free Cash Flow"] if "Free Cash Flow" in cf.index else None
        if fcf_row is None:
            return {"error": "Free Cash Flow not found in statements"}

        current_fcf = float(fcf_row.iloc[0])

        if discount_rate is None:
            risk_free = self.macro.get_risk_free_rate()
            discount_rate = risk_free + 0.06  # risk free + equity premium

        # Project future FCFs
        projected_fcf = []
        for year in range(1, projection_years + 1):
            fcf = current_fcf * (1 + growth_rate) ** year
            projected_fcf.append(fcf)

        # Terminal value
        terminal_value = (
            projected_fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        )

        # Discount back to present
        pv_fcfs = sum(
            fcf / (1 + discount_rate) ** i for i, fcf in enumerate(projected_fcf, 1)
        )
        pv_terminal = terminal_value / (1 + discount_rate) ** projection_years
        enterprise_value = pv_fcfs + pv_terminal

        # Get shares outstanding
        import yfinance as yf

        info = yf.Ticker(ticker).info
        shares = info.get("sharesOutstanding", 1)
        intrinsic_per_share = enterprise_value / shares
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))

        margin_of_safety = (
            (intrinsic_per_share - current_price) / intrinsic_per_share * 100
            if intrinsic_per_share > 0
            else 0
        )

        return {
            "current_fcf": current_fcf,
            "discount_rate": discount_rate,
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "enterprise_value": enterprise_value,
            "intrinsic_per_share": round(intrinsic_per_share, 2),
            "current_price": current_price,
            "margin_of_safety_pct": round(margin_of_safety, 2),
            "verdict": (
                "UNDERVALUED" if margin_of_safety > 15
                else "FAIR" if margin_of_safety > -10
                else "OVERVALUED"
            ),
        }

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
