"""Composite stock scoring system - combines all analyses into a single score."""

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
            health = fund_result["health"]["score"] / fund_result["health"]["max_score"]
            growth = fund_result["growth"]["score"] / fund_result["growth"]["max_score"]
            val_score = fund_result["valuation"]["score"] / fund_result["valuation"]["max_score"]
            scores["fundamental"] = (health * 0.4 + growth * 0.3 + val_score * 0.3) * 100
            details["fundamental"] = fund_result
        except Exception as e:
            logger.error("Fundamental analysis failed: %s", e)
            scores["fundamental"] = 50  # neutral fallback

        # Valuation score (0-100)
        try:
            dcf = self.val.dcf_valuation(ticker)
            mos = dcf.get("margin_of_safety_pct", 0)
            scores["valuation"] = max(0, min(100, 50 + mos))
            details["valuation"] = dcf
        except Exception as e:
            logger.error("Valuation analysis failed: %s", e)
            scores["valuation"] = 50

        # Technical score (0-100)
        try:
            df = self.market.get_price_history(ticker)
            signals = self.tech.get_signals(df)
            buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
            total = len(signals) or 1
            scores["technical"] = (buy_count / total) * 100
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

        return {
            "ticker": ticker,
            "composite_score": round(composite, 1),
            "recommendation": recommendation,
            "component_scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": self.WEIGHTS,
            "details": details,
        }
