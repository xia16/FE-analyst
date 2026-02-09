"""Fundamental analysis engine."""

import pandas as pd

from src.data_sources.fundamentals import FundamentalsClient
from src.utils.logger import setup_logger

logger = setup_logger("fundamental_analysis")


class FundamentalAnalyzer:
    """Analyze company fundamentals for investment decisions."""

    def __init__(self):
        self.client = FundamentalsClient()

    def analyze(self, ticker: str) -> dict:
        """Run full fundamental analysis on a company."""
        ratios = self.client.get_key_ratios(ticker)
        profile = self.client.get_company_profile(ticker)

        health = self._assess_financial_health(ratios)
        growth = self._assess_growth(ratios)
        valuation = self._assess_valuation(ratios)

        return {
            "ticker": ticker,
            "company": profile.get("name"),
            "sector": profile.get("sector"),
            "health": health,
            "growth": growth,
            "valuation": valuation,
            "ratios": ratios,
        }

    def _assess_financial_health(self, ratios: dict) -> dict:
        """Score financial health based on key ratios."""
        score = 0
        reasons = []

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
        """Score growth profile."""
        score = 0
        reasons = []

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
            else:
                reasons.append(f"Low earnings growth: {earn_g:.1%}")

        return {"score": score, "max_score": 4, "reasons": reasons}

    def _assess_valuation(self, ratios: dict) -> dict:
        """Score relative valuation."""
        score = 0
        reasons = []

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
