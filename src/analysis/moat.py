"""Competitive moat scoring framework for AI supply chain companies.

Evaluates companies on 6 moat dimensions critical to AI production:
1. Market Dominance - market share in their niche
2. Switching Costs - how hard to replace
3. Technology Lock-in - proprietary tech/IP
4. Supply Chain Criticality - bottleneck position
5. Pricing Power - margin trends
6. Barriers to Entry - capital/knowledge/regulatory
"""

import pandas as pd
import numpy as np

from src.data_sources.fundamentals import FundamentalsClient
from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("moat_analysis")


class MoatAnalyzer:
    """Score competitive moats for AI supply chain companies."""

    MOAT_WEIGHTS = {
        "market_dominance": 0.20,
        "switching_costs": 0.15,
        "technology_lockin": 0.15,
        "supply_chain_criticality": 0.20,
        "pricing_power": 0.15,
        "barriers_to_entry": 0.15,
    }

    def __init__(self):
        self.fundamentals = FundamentalsClient()
        self.market = MarketDataClient()

    def score_moat(self, ticker: str, moat_overrides: dict | None = None) -> dict:
        """Compute moat score for a company.

        Args:
            ticker: Stock ticker
            moat_overrides: Manual overrides for qualitative scores (0-100).
                Keys: market_dominance, switching_costs, technology_lockin,
                      supply_chain_criticality, barriers_to_entry
        """
        overrides = moat_overrides or {}
        scores = {}

        # --- Quantitative: Pricing Power (from financials) ---
        scores["pricing_power"] = self._score_pricing_power(ticker)

        # --- Quantitative: Barriers to Entry (R&D + capex intensity) ---
        barriers_quant = self._score_barriers_quantitative(ticker)

        # --- Quantitative: Switching Costs proxy (revenue stability + customer stickiness) ---
        switching_quant = self._score_switching_costs_quantitative(ticker)

        # --- Qualitative scores (from overrides or quantitative estimates) ---
        for dim in [
            "market_dominance",
            "switching_costs",
            "technology_lockin",
            "supply_chain_criticality",
            "barriers_to_entry",
        ]:
            if dim in overrides:
                scores[dim] = overrides[dim]
            elif dim == "barriers_to_entry":
                scores[dim] = barriers_quant
            elif dim == "switching_costs":
                scores[dim] = switching_quant
            else:
                scores[dim] = 50  # default neutral if not provided

        # Weighted composite
        composite = sum(
            scores[k] * self.MOAT_WEIGHTS[k] for k in self.MOAT_WEIGHTS
        )

        # Moat classification
        if composite >= 80:
            moat_class = "WIDE MOAT"
        elif composite >= 60:
            moat_class = "NARROW MOAT"
        elif composite >= 40:
            moat_class = "WEAK MOAT"
        else:
            moat_class = "NO MOAT"

        return {
            "ticker": ticker,
            "composite_moat_score": round(composite, 1),
            "moat_classification": moat_class,
            "dimension_scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": self.MOAT_WEIGHTS,
        }

    def _score_pricing_power(self, ticker: str) -> float:
        """Score pricing power from gross/operating margin trends."""
        try:
            ratios = self.fundamentals.get_key_ratios(ticker)
            income = self.fundamentals.get_income_statement(ticker)

            score = 50.0  # base

            # Gross margin level
            gm = ratios.get("profit_margin")
            if gm is not None:
                if gm > 0.40:
                    score += 25
                elif gm > 0.25:
                    score += 15
                elif gm > 0.15:
                    score += 5

            # Operating margin level
            om = ratios.get("operating_margin")
            if om is not None:
                if om > 0.30:
                    score += 15
                elif om > 0.20:
                    score += 10
                elif om > 0.10:
                    score += 5

            # Margin trend (expanding = pricing power)
            if not income.empty and "Gross Profit" in income.index and "Total Revenue" in income.index:
                gp = income.loc["Gross Profit"]
                rev = income.loc["Total Revenue"]
                margins = (gp / rev).dropna()
                if len(margins) >= 2:
                    trend = margins.iloc[0] - margins.iloc[-1]  # recent - oldest
                    if trend > 0.03:
                        score += 10
                    elif trend < -0.03:
                        score -= 10

            return min(100, max(0, score))
        except Exception as e:
            logger.warning("Pricing power score failed for %s: %s", ticker, e)
            return 50.0

    def _score_barriers_quantitative(self, ticker: str) -> float:
        """Score barriers to entry from R&D intensity + capex requirements."""
        try:
            income = self.fundamentals.get_income_statement(ticker)
            cashflow = self.fundamentals.get_cash_flow(ticker)

            score = 50.0

            if not income.empty:
                revenue = None
                rd = None
                if "Total Revenue" in income.index:
                    revenue = income.loc["Total Revenue"].iloc[0]
                    if pd.notna(revenue):
                        revenue = float(revenue)
                if "Research And Development" in income.index:
                    rd = income.loc["Research And Development"].iloc[0]
                    if pd.notna(rd):
                        rd = float(rd)

                # High R&D intensity = high barriers (competitors can't easily replicate)
                if rd and revenue and revenue > 0:
                    rd_pct = rd / revenue
                    if rd_pct > 0.20:
                        score += 25  # Very high R&D (pharma, deep tech)
                    elif rd_pct > 0.10:
                        score += 15  # High R&D (semis, software)
                    elif rd_pct > 0.05:
                        score += 5

            if not cashflow.empty and "Capital Expenditure" in cashflow.index:
                capex = cashflow.loc["Capital Expenditure"].iloc[0]
                if pd.notna(capex):
                    capex = abs(float(capex))
                    # Large absolute capex = capital-intensive = harder to enter
                    if capex > 10e9:
                        score += 15  # >$10B capex (fabs, data centers)
                    elif capex > 3e9:
                        score += 10
                    elif capex > 1e9:
                        score += 5

            return min(100, max(0, score))
        except Exception as e:
            logger.warning("Barriers quantitative score failed for %s: %s", ticker, e)
            return 50.0

    def _score_switching_costs_quantitative(self, ticker: str) -> float:
        """Score switching costs proxy from revenue stability + gross margin."""
        try:
            income = self.fundamentals.get_income_statement(ticker)
            score = 50.0

            if income.empty or "Total Revenue" not in income.index:
                return score

            rev_row = income.loc["Total Revenue"].dropna()
            revenues = [float(v) for v in rev_row if pd.notna(v)]

            if len(revenues) < 3:
                return score

            # Revenue stability (low variance = sticky customers)
            mean_rev = np.mean(revenues)
            if mean_rev > 0:
                cv = np.std(revenues) / mean_rev
                if cv < 0.10:
                    score += 20  # Very stable (enterprise software, utilities)
                elif cv < 0.20:
                    score += 10  # Stable
                elif cv > 0.40:
                    score -= 10  # Volatile (cyclical, low switching costs)

            # Consistent revenue growth = customers keep coming back
            all_growing = all(revenues[i] >= revenues[i + 1] * 0.95 for i in range(len(revenues) - 1))
            if all_growing:
                score += 10

            # High gross margins = pricing power = customers can't easily switch
            if "Gross Profit" in income.index:
                gp = income.loc["Gross Profit"].iloc[0]
                rev = income.loc["Total Revenue"].iloc[0]
                if pd.notna(gp) and pd.notna(rev) and float(rev) > 0:
                    gm = float(gp) / float(rev)
                    if gm > 0.60:
                        score += 15  # Software-like margins
                    elif gm > 0.40:
                        score += 5

            return min(100, max(0, score))
        except Exception as e:
            logger.warning("Switching costs quantitative score failed for %s: %s", ticker, e)
            return 50.0

    def compare_moats(self, companies: list[dict]) -> pd.DataFrame:
        """Compare moat scores across multiple companies.

        Args:
            companies: List of dicts with 'ticker' and optional moat override keys.
                Example: [
                    {"ticker": "8035.T", "market_dominance": 85, "switching_costs": 90},
                    {"ticker": "ASML", "market_dominance": 95, "switching_costs": 95},
                ]
        """
        results = []
        for comp in companies:
            ticker = comp.pop("ticker")
            result = self.score_moat(ticker, moat_overrides=comp)
            results.append(result)

        rows = []
        for r in results:
            row = {"ticker": r["ticker"], "moat_score": r["composite_moat_score"],
                   "classification": r["moat_classification"]}
            row.update(r["dimension_scores"])
            rows.append(row)

        df = pd.DataFrame(rows).sort_values("moat_score", ascending=False)
        return df


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class MoatAnalyzerPlugin(_BaseAnalyzer):
    name = "moat"
    default_weight = 0.10

    def __init__(self):
        self._analyzer = MoatAnalyzer()

    def analyze(self, ticker, ctx):
        overrides = ctx.company_meta.get(ticker, {})
        result = self._analyzer.score_moat(ticker, moat_overrides=overrides)
        result["score"] = result["composite_moat_score"]
        return result
