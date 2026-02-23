"""Composite stock scoring system - combines all analyses into a single score.

Produces a composite score (0-100) from 5 analysis engines, plus a
conviction meta-score that measures agreement across dimensions.
"""

import numpy as np

from src.analysis.technical import TechnicalAnalyzer
from src.analysis.fundamental import FundamentalAnalyzer
from src.analysis.valuation import ValuationAnalyzer
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.risk import RiskAnalyzer
from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("scoring")


class StockScorer:
    """Generate a composite investment score (0-100) for a stock."""

    WEIGHTS = {
        "fundamental": 0.30,
        "valuation": 0.25,
        "technical": 0.20,
        "sentiment": 0.10,
        "risk": 0.15,
    }

    def __init__(self):
        self.market = MarketDataClient()
        self.tech = TechnicalAnalyzer()
        self.fund = FundamentalAnalyzer()
        self.val = ValuationAnalyzer()
        self.sent = SentimentAnalyzer()
        self.risk = RiskAnalyzer()

    def score(self, ticker: str) -> dict:
        """Compute composite score for a stock."""
        logger.info("Scoring %s", ticker)
        scores = {}
        details = {}

        # Fundamental score (0-100)
        try:
            fund_result = self.fund.analyze(ticker)
            health = fund_result["health"]["score"] / max(fund_result["health"]["max_score"], 1)
            growth = fund_result["growth"]["score"] / max(fund_result["growth"]["max_score"], 1)
            val_score = fund_result["valuation"]["score"] / max(fund_result["valuation"]["max_score"], 1)

            # Incorporate new metrics if available
            sub_scores = [health * 0.25, growth * 0.20, val_score * 0.15]
            sub_total_weight = 0.60

            # ROIC
            roic = fund_result.get("roic", {})
            if roic.get("score") is not None and roic.get("max_score"):
                roic_pct = roic["score"] / roic["max_score"]
                sub_scores.append(roic_pct * 0.15)
                sub_total_weight += 0.15

            # Piotroski F-Score
            piotroski = fund_result.get("piotroski", {})
            if piotroski.get("score") is not None:
                pio_pct = piotroski["score"] / 9.0
                sub_scores.append(pio_pct * 0.10)
                sub_total_weight += 0.10

            # Earnings quality
            eq = fund_result.get("earnings_quality", {})
            if eq.get("score") is not None and eq.get("max_score"):
                eq_pct = eq["score"] / eq["max_score"]
                sub_scores.append(eq_pct * 0.08)
                sub_total_weight += 0.08

            # Capital allocation
            ca = fund_result.get("capital_allocation", {})
            if ca.get("score") is not None and ca.get("max_score"):
                ca_pct = ca["score"] / ca["max_score"]
                sub_scores.append(ca_pct * 0.07)
                sub_total_weight += 0.07

            # Normalize to 100
            scores["fundamental"] = (sum(sub_scores) / sub_total_weight) * 100 if sub_total_weight > 0 else 50
            details["fundamental"] = fund_result
        except Exception as e:
            logger.error("Fundamental analysis failed: %s", e)
            scores["fundamental"] = 50

        # Valuation score (0-100): Composite DCF 60% + Comps 25% + Quality 15%
        try:
            dcf = self.val.dcf_valuation(ticker)
            comps = self.val.comparable_valuation(ticker)

            # Multi-method composite fair value
            composite = {}
            try:
                composite = self.val.composite_fair_value(ticker)
                dcf["composite"] = composite
            except Exception as e:
                logger.warning("Composite valuation failed for %s: %s", ticker, e)

            # Use composite MOS for scoring if available, else fall back to FCF DCF
            if composite.get("margin_of_safety_pct") is not None:
                mos = composite["margin_of_safety_pct"]
            else:
                mos = dcf.get("margin_of_safety_pct", 0)

            mos = max(-50, min(50, mos))  # Clamp MOS so score stays 0-100 without extremes
            dcf_score = max(0, min(100, 50 + mos))

            # Comps score (25% weight)
            comps_score = 50
            if comps.get("comparison"):
                premiums = [v["premium_pct"] for v in comps["comparison"].values()
                            if v.get("premium_pct") is not None]
                if premiums:
                    avg_premium = sum(premiums) / len(premiums)
                    comps_score = max(0, min(100, 50 - avg_premium))

            # Quality score (15% weight) — reuse fundamental health
            quality_score = scores.get("fundamental", 50)

            scores["valuation"] = dcf_score * 0.60 + comps_score * 0.25 + quality_score * 0.15
            details["valuation"] = {
                "dcf": dcf,
                "comparables": comps,
                "dcf_score": round(dcf_score, 1),
                "comps_score": round(comps_score, 1),
                "quality_score": round(quality_score, 1),
            }
        except Exception as e:
            logger.error("Valuation analysis failed: %s", e)
            scores["valuation"] = 50

        # Technical score (0-100)
        try:
            df = self.market.get_price_history(ticker)
            signals = self.tech.get_signals(df)
            signal_sum = sum(
                1.0 if s.get("signal") == "BUY" else 0.5 if s.get("signal") == "HOLD" else 0.0
                for s in signals.values()
            )
            total = len(signals) or 1
            scores["technical"] = (signal_sum / total) * 100
            details["technical"] = signals
        except Exception as e:
            logger.error("Technical analysis failed: %s", e)
            scores["technical"] = 50

        # Sentiment score (0-100)
        try:
            sent = self.sent.analyze(ticker)
            scores["sentiment"] = max(0, min(100, 50 + sent["overall_score"] * 100))
            details["sentiment"] = sent
        except Exception as e:
            logger.error("Sentiment analysis failed: %s", e)
            scores["sentiment"] = 50

        # Risk score (0-100, higher = less risky = better)
        try:
            risk = self.risk.analyze(ticker)
            vol = risk.get("volatility", 0.3)
            scores["risk"] = max(0, min(100, (1 - vol) * 100))
            details["risk"] = risk
        except Exception as e:
            logger.error("Risk analysis failed: %s", e)
            scores["risk"] = 50

        # Composite
        composite = sum(
            scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )

        # Recommendation
        if composite >= 75:
            recommendation = "STRONG BUY"
        elif composite >= 60:
            recommendation = "BUY"
        elif composite >= 45:
            recommendation = "HOLD"
        elif composite >= 30:
            recommendation = "SELL"
        else:
            recommendation = "STRONG SELL"

        # Conviction meta-score
        conviction = self._compute_conviction(scores, details)

        return {
            "ticker": ticker,
            "composite_score": round(composite, 1),
            "recommendation": recommendation,
            "component_scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": self.WEIGHTS,
            "conviction": conviction,
            "details": details,
        }

    @staticmethod
    def _compute_conviction(scores: dict, details: dict) -> dict:
        """Compute conviction level — how much agreement is there across dimensions.

        High conviction = most dimensions agree (all bullish or all bearish).
        Low conviction = mixed signals across dimensions.
        """
        # Normalize all scores to -1 (bearish) to +1 (bullish)
        normalized = {}
        for k, v in scores.items():
            normalized[k] = (v - 50) / 50  # maps 0-100 → -1 to +1

        vals = list(normalized.values())
        if len(vals) < 2:
            return {"level": "LOW", "score": 0, "detail": "Insufficient data"}

        std = float(np.std(vals))
        mean = float(np.mean(vals))
        # Low std = high agreement = high conviction
        agreement = max(0, 1 - std * 2)  # 0-1 scale
        extremity = abs(mean)  # 0-1 scale

        conviction_score = round((agreement * 0.6 + extremity * 0.4) * 100, 1)

        # Directional signals
        bullish_count = sum(1 for v in vals if v > 0.1)
        bearish_count = sum(1 for v in vals if v < -0.1)

        # Check for specific high-conviction patterns
        boosters = []

        # Piotroski confirmation
        piotroski = details.get("fundamental", {}).get("piotroski", {})
        if piotroski.get("score") is not None:
            if piotroski["score"] >= 7:
                boosters.append("Piotroski F-Score confirms strength")
                conviction_score = min(100, conviction_score + 5)
            elif piotroski["score"] <= 2:
                boosters.append("Piotroski F-Score confirms weakness")
                conviction_score = min(100, conviction_score + 5)

        # Insider + analyst alignment
        sent = details.get("sentiment", {})
        insider_pct = sent.get("ownership", {}).get("insider_pct")
        analyst_targets = sent.get("analyst_targets", {})
        if insider_pct and insider_pct > 0.05 and analyst_targets.get("upside_pct", 0) > 15:
            boosters.append("Insiders hold significant stake + analysts see upside")
            conviction_score = min(100, conviction_score + 5)

        # DCF + comps alignment
        val_details = details.get("valuation", {})
        dcf_mos = val_details.get("dcf", {}).get("margin_of_safety_pct", 0)
        comps_premium = 0
        comps_data = val_details.get("comparables", {}).get("comparison", {})
        if comps_data:
            premiums = [v.get("premium_pct", 0) for v in comps_data.values() if v.get("premium_pct") is not None]
            comps_premium = sum(premiums) / len(premiums) if premiums else 0
        if dcf_mos > 15 and comps_premium < -10:
            boosters.append("DCF and comps both signal undervaluation")
            conviction_score = min(100, conviction_score + 5)
        elif dcf_mos < -15 and comps_premium > 10:
            boosters.append("DCF and comps both signal overvaluation")
            conviction_score = min(100, conviction_score + 5)

        # Earnings quality confirmation
        eq = details.get("fundamental", {}).get("earnings_quality", {})
        if eq.get("fcf_ni_ratio") is not None and eq["fcf_ni_ratio"] > 1.2:
            boosters.append("High earnings quality (FCF > Net Income)")
            conviction_score = min(100, conviction_score + 3)

        if conviction_score >= 70:
            level = "HIGH"
        elif conviction_score >= 45:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "level": level,
            "score": conviction_score,
            "bullish_dimensions": bullish_count,
            "bearish_dimensions": bearish_count,
            "agreement": round(agreement, 3),
            "boosters": boosters,
        }
