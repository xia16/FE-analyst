"""Sentiment data collector and aggregator.

Gathers raw data from news, Reddit, analyst recommendations, and insider
trades into a structured format. Sentiment interpretation is performed
by the analyst (Claude) when reading the output — no NLP model or API
call is needed.

The data collector scores a simple heuristic baseline (analyst consensus
+ insider net buy/sell) for the pipeline composite, but the real analysis
happens when Claude reads the raw data during report generation.
"""

from src.data_sources.news_sentiment import NewsSentimentClient
from src.data_sources.alternative_data import AlternativeDataClient
from src.utils.logger import setup_logger

logger = setup_logger("sentiment_analysis")


class SentimentAnalyzer:
    """Gather multi-source sentiment data for analyst interpretation."""

    def __init__(self):
        self.news_client = NewsSentimentClient()
        self.alt_client = AlternativeDataClient()

    def analyze(self, ticker: str) -> dict:
        """Gather all sentiment data sources into a structured result.

        Returns a dict with raw data from each source, plus a simple
        heuristic score for the pipeline composite. The raw data is
        designed to be read and interpreted by Claude during analysis.
        """
        logger.info("Gathering sentiment data for %s", ticker)

        # 1. Fetch news headlines
        news = []
        try:
            news = self.news_client.get_company_news(ticker)
        except Exception as e:
            logger.warning("  News fetch failed: %s", e)
        logger.info("  News articles: %d", len(news))

        # 2. Fetch Reddit posts from multiple subreddits
        reddit_posts = []
        subreddits = ["wallstreetbets", "stocks", "investing"]
        for sub in subreddits:
            try:
                posts = self.alt_client.get_reddit_sentiment(
                    ticker, subreddit=sub, limit=20
                )
                for p in posts:
                    p["subreddit"] = sub
                reddit_posts.extend(posts)
            except Exception as e:
                logger.warning("  Reddit r/%s fetch failed: %s", sub, e)
        logger.info("  Reddit posts: %d", len(reddit_posts))

        # 3. Fetch analyst recommendations
        analyst_recs = []
        try:
            recs_df = self.alt_client.get_analyst_recommendations(ticker)
            if recs_df is not None and not recs_df.empty:
                analyst_recs = recs_df.iloc[:10].to_dict("records")
        except Exception as e:
            logger.warning("  Analyst recs fetch failed: %s", e)
        logger.info("  Analyst recommendations: %d", len(analyst_recs))

        # 4. Fetch insider trades
        insider_trades = []
        try:
            insider_trades = self.alt_client.get_insider_trades(ticker)
        except Exception as e:
            logger.warning("  Insider trades fetch failed: %s", e)
        logger.info("  Insider trades: %d", len(insider_trades))

        # 5. Fetch institutional ownership
        institutional = []
        try:
            inst_df = self.alt_client.get_institutional_ownership(ticker)
            if inst_df is not None and not inst_df.empty:
                institutional = inst_df.iloc[:10].to_dict("records")
        except Exception as e:
            logger.warning("  Institutional ownership fetch failed: %s", e)
        logger.info("  Institutional holders: %d", len(institutional))

        # Build heuristic score for pipeline composite
        heuristic_score = self._compute_heuristic(analyst_recs, insider_trades)

        return {
            "ticker": ticker,
            "overall_score": heuristic_score,
            "overall_label": self._label_from_score(heuristic_score),
            # Raw data for Claude to interpret
            "raw_data": {
                "news": news[:30],  # cap to keep context manageable
                "reddit_posts": reddit_posts[:30],
                "analyst_recommendations": analyst_recs,
                "insider_trades": insider_trades[:20],
                "institutional_holders": institutional,
            },
            "source_counts": {
                "news_articles": len(news),
                "reddit_posts": len(reddit_posts),
                "analyst_recommendations": len(analyst_recs),
                "insider_trades": len(insider_trades),
                "institutional_holders": len(institutional),
            },
        }

    @staticmethod
    def _compute_heuristic(analyst_recs: list[dict], insider_trades: list[dict]) -> float:
        """Simple heuristic score from analyst consensus + insider activity.

        This provides a baseline for the pipeline composite score. The
        real sentiment analysis happens when Claude reads the raw data.

        Returns float from -1.0 to 1.0.
        """
        scores = []

        # Analyst consensus heuristic
        if analyst_recs:
            grade_map = {
                "Strong Buy": 1.0, "Buy": 0.5, "Overweight": 0.4,
                "Outperform": 0.4, "Market Outperform": 0.3,
                "Hold": 0.0, "Neutral": 0.0, "Equal-Weight": 0.0,
                "Market Perform": 0.0, "Sector Perform": 0.0,
                "Underweight": -0.3, "Underperform": -0.4,
                "Sell": -0.5, "Strong Sell": -1.0, "Reduce": -0.4,
            }
            grades = []
            for rec in analyst_recs:
                grade = rec.get("To Grade", rec.get("toGrade", ""))
                if grade in grade_map:
                    grades.append(grade_map[grade])
            if grades:
                scores.append(sum(grades) / len(grades))

        # Insider trade heuristic (net buy = bullish, net sell = bearish)
        if insider_trades:
            net_change = sum(t.get("change", 0) for t in insider_trades[:20])
            if net_change > 0:
                scores.append(0.3)
            elif net_change < 0:
                scores.append(-0.2)
            else:
                scores.append(0.0)

        if scores:
            return round(sum(scores) / len(scores), 3)
        return 0.0

    @staticmethod
    def _label_from_score(score: float) -> str:
        if score > 0.2:
            return "BULLISH"
        elif score < -0.2:
            return "BEARISH"
        elif score == 0.0:
            return "NO DATA"
        return "NEUTRAL"


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class SentimentAnalyzerPlugin(_BaseAnalyzer):
    name = "sentiment"
    default_weight = 0.10

    def __init__(self):
        self._analyzer = SentimentAnalyzer()

    def analyze(self, ticker, ctx):
        result = self._analyzer.analyze(ticker)
        # Convert -1..1 score to 0-100 scale for composite scoring
        overall = result.get("overall_score", 0)
        score = max(0, min(100, 50 + overall * 100))
        result["score"] = round(score, 1)
        return result
